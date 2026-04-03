import re

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.utils.validation import check_is_fitted


UKRAINIAN_STOP_WORDS = {
    "а",
    "або",
    "але",
    "без",
    "би",
    "був",
    "була",
    "були",
    "було",
    "бути",
    "в",
    "вам",
    "вас",
    "ви",
    "від",
    "він",
    "вона",
    "вони",
    "все",
    "всіх",
    "де",
    "для",
    "до",
    "дуже",
    "є",
    "ж",
    "за",
    "з",
    "із",
    "і",
    "й",
    "її",
    "їм",
    "їх",
    "його",
    "коли",
    "ми",
    "мій",
    "може",
    "моя",
    "на",
    "над",
    "нам",
    "нас",
    "не",
    "ні",
    "них",
    "ну",
    "о",
    "ось",
    "по",
    "під",
    "при",
    "про",
    "саме",
    "свої",
    "себе",
    "та",
    "так",
    "також",
    "те",
    "ти",
    "того",
    "той",
    "тою",
    "тут",
    "у",
    "цей",
    "це",
    "ця",
    "ці",
    "чи",
    "що",
    "щоб",
    "як",
}

TOKEN_PATTERN = re.compile(r"(?u)[^\W\d_]+(?:['’`-][^\W\d_]+)*")
PHONE_PATTERN = re.compile(r"\+?\d[\d\-\(\)\s]{7,}\d")
URL_PATTERN = re.compile(r"(http|https)://\S+|www\.\S+", flags=re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", flags=re.UNICODE)
HTML_PATTERN = re.compile(r"<[^>]+>")
CURRENCY_PATTERN = re.compile(r"[$€£₴¥]+")
PERCENT_PATTERN = re.compile(r"\b\d+\s*%|\b\d+\s*відсотк\w*\b", flags=re.IGNORECASE)
REPEATED_PUNCT_PATTERN = re.compile(r"([!?])\1{1,}")
UPPERCASE_WORD_PATTERN = re.compile(r"\b[A-ZА-ЯІЇЄҐ]{2,}\b")

PROTECTED_TOKENS = {
    "htmltoken",
    "urltoken",
    "emailtoken",
    "currencytoken",
    "numtoken",
    "phonetoken",
    "percenttoken",
}

UKRAINIAN_SUFFIXES = (
    "ування",
    "ювання",
    "ення",
    "ання",
    "істі",
    "ість",
    "овий",
    "евий",
    "ового",
    "евого",
    "ими",
    "іми",
    "ого",
    "ому",
    "ами",
    "ями",
    "ові",
    "еві",
    "єю",
    "ою",
    "ий",
    "ій",
    "а",
    "я",
    "у",
    "ю",
    "і",
    "ї",
    "е",
    "о",
)

ENGLISH_SUFFIXES = (
    "ization",
    "ation",
    "ments",
    "ment",
    "ingly",
    "edly",
    "ingly",
    "less",
    "ness",
    "tion",
    "sion",
    "ings",
    "edly",
    "ing",
    "ers",
    "ies",
    "ied",
    "ed",
    "es",
    "s",
)


def _light_stem(token, suffixes, min_root_len):
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) - len(suffix) >= min_root_len:
            return token[: -len(suffix)]
    return token


def _normalize_stop_words(words):
    normalized = set()
    for word in words:
        token = str(word).strip().lower()
        token = token.replace("’", "'").replace("`", "'")
        token = _light_stem(token, UKRAINIAN_SUFFIXES, min_root_len=3)
        token = _light_stem(token, ENGLISH_SUFFIXES, min_root_len=3)
        normalized.add(token)
    return normalized


MULTILINGUAL_STOP_WORDS = sorted(
    _normalize_stop_words(ENGLISH_STOP_WORDS.union(UKRAINIAN_STOP_WORDS))
)

SPAM_HINT_KEYWORDS = (
    "urgent",
    "winner",
    "claim",
    "bonus",
    "free",
    "offer",
    "limited time",
    "act now",
    "verify",
    "account suspended",
    "click",
    "crypto",
    "loan",
    "кредит",
    "позика",
    "акція",
    "знижка",
    "виграли",
    "терміново",
    "підтверд",
    "перейдіть",
    "без довідок",
    "на карту",
    "гарантовано",
)

STRUCTURAL_FEATURE_NAMES = (
    "char_len_log",
    "token_count_log",
    "url_count_log",
    "email_count_log",
    "phone_count_log",
    "currency_count_log",
    "percent_count_log",
    "digit_ratio",
    "uppercase_ratio",
    "exclamation_count_log",
    "question_count_log",
    "line_break_count_log",
    "repeated_punct_count_log",
    "uppercase_word_ratio",
    "long_token_ratio",
    "unique_token_ratio",
    "spam_keyword_hits_log",
)


class SpamPreprocessor(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        max_word_features=25000,
        max_char_features=45000,
        max_char_features_dense=25000,
        min_df=1,
        word_min_df=2,
        char_min_df=1,
        max_df=0.98,
        include_structural_features=True,
    ):
        self.max_word_features = max_word_features
        self.max_char_features = max_char_features
        self.max_char_features_dense = max_char_features_dense
        self.min_df = min_df
        self.word_min_df = word_min_df
        self.char_min_df = char_min_df
        self.max_df = max_df
        self.include_structural_features = include_structural_features

    def normalize_token(self, token):
        token = str(token).strip().lower()
        token = token.replace("’", "'").replace("`", "'")

        if token in PROTECTED_TOKENS:
            return token

        if len(token) >= 6:
            token = _light_stem(token, UKRAINIAN_SUFFIXES, min_root_len=3)
            token = _light_stem(token, ENGLISH_SUFFIXES, min_root_len=3)

        return token

    def multilingual_tokenize(self, text):
        return [self.normalize_token(token) for token in TOKEN_PATTERN.findall(text)]

    def clean_text(self, text):
        text = str(text).lower().strip()
        text = text.replace("’", "'").replace("`", "'")

        text = HTML_PATTERN.sub(" htmltoken ", text)
        text = URL_PATTERN.sub(" urltoken ", text)
        text = PHONE_PATTERN.sub(" phonetoken ", text)
        text = EMAIL_PATTERN.sub(" emailtoken ", text)
        text = CURRENCY_PATTERN.sub(" currencytoken ", text)
        text = PERCENT_PATTERN.sub(" percenttoken ", text)
        text = re.sub(r"\d+", " numtoken ", text)

        text = re.sub(r"[^\w\s!?%'\-]", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def structural_feature_names(self):
        return STRUCTURAL_FEATURE_NAMES

    def extract_structural_features(self, text):
        raw_text = str(text or "").strip()
        lowered_text = raw_text.lower()
        cleaned_text = self.clean_text(raw_text)
        tokens = self.multilingual_tokenize(cleaned_text)

        letter_count = sum(char.isalpha() for char in raw_text)
        uppercase_count = sum(char.isupper() for char in raw_text if char.isalpha())
        digit_count = sum(char.isdigit() for char in raw_text)
        token_count = len(tokens)
        long_token_count = sum(len(token) >= 12 for token in tokens)
        unique_token_ratio = (len(set(tokens)) / token_count) if token_count else 0.0
        uppercase_word_count = len(UPPERCASE_WORD_PATTERN.findall(raw_text))
        keyword_hits = sum(1 for keyword in SPAM_HINT_KEYWORDS if keyword in lowered_text)

        return np.array(
            [
                np.log1p(len(raw_text)),
                np.log1p(token_count),
                np.log1p(len(URL_PATTERN.findall(raw_text))),
                np.log1p(len(EMAIL_PATTERN.findall(raw_text))),
                np.log1p(len(PHONE_PATTERN.findall(raw_text))),
                np.log1p(len(CURRENCY_PATTERN.findall(raw_text))),
                np.log1p(len(PERCENT_PATTERN.findall(lowered_text))),
                digit_count / max(len(raw_text), 1),
                uppercase_count / max(letter_count, 1),
                np.log1p(raw_text.count("!")),
                np.log1p(raw_text.count("?")),
                np.log1p(raw_text.count("\n")),
                np.log1p(len(REPEATED_PUNCT_PATTERN.findall(raw_text))),
                uppercase_word_count / max(token_count, 1),
                long_token_count / max(token_count, 1),
                unique_token_ratio,
                np.log1p(keyword_hits),
            ],
            dtype=float,
        )

    def fit(self, X, y=None):
        cleaned = [self.clean_text(x) for x in X]

        self.word_vectorizer_ = TfidfVectorizer(
            analyzer="word",
            lowercase=False,
            tokenizer=self.multilingual_tokenize,
            token_pattern=None,
            stop_words=MULTILINGUAL_STOP_WORDS,
            ngram_range=(1, 3),
            min_df=max(self.word_min_df, self.min_df),
            max_df=self.max_df,
            sublinear_tf=True,
            binary=True,
            strip_accents=None,
            max_features=self.max_word_features,
        )

        self.char_vectorizer_wb_ = TfidfVectorizer(
            analyzer="char_wb",
            lowercase=False,
            ngram_range=(2, 5),
            min_df=max(self.char_min_df, self.min_df),
            sublinear_tf=True,
            max_features=self.max_char_features,
        )

        # Raw char n-grams help catch glued spam phrases, URLs and obfuscation.
        self.char_vectorizer_dense_ = TfidfVectorizer(
            analyzer="char",
            lowercase=False,
            ngram_range=(3, 6),
            min_df=max(self.char_min_df, self.min_df),
            sublinear_tf=True,
            max_features=self.max_char_features_dense,
        )

        self.word_vectorizer_.fit(cleaned)
        self.char_vectorizer_wb_.fit(cleaned)
        self.char_vectorizer_dense_.fit(cleaned)
        self.include_structural_features_ = bool(self.include_structural_features)
        self.structural_feature_names_ = self.structural_feature_names()
        return self

    def transform(self, X):
        check_is_fitted(
            self,
            ["word_vectorizer_", "char_vectorizer_wb_", "char_vectorizer_dense_"],
        )

        cleaned = [self.clean_text(x) for x in X]
        x_word = self.word_vectorizer_.transform(cleaned)
        x_char_wb = self.char_vectorizer_wb_.transform(cleaned)
        x_char_dense = self.char_vectorizer_dense_.transform(cleaned)

        parts = [x_word, x_char_wb, x_char_dense]

        # Older pickled preprocessors do not have this flag and must keep
        # their original feature dimensionality when loaded from disk.
        if getattr(self, "include_structural_features_", False):
            x_structural = csr_matrix(
                np.vstack([self.extract_structural_features(text) for text in X])
            )
            parts.append(x_structural)

        return hstack(parts).tocsr()

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)
