import re

from scipy.sparse import hstack
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


class SpamPreprocessor(BaseEstimator, TransformerMixin):
    def __init__(
        self,
        max_word_features=25000,
        max_char_features=45000,
        max_char_features_dense=25000,
        min_df=1,
        word_min_df=2,
        char_min_df=1,
        max_df=0.98
    ):
        self.max_word_features = max_word_features
        self.max_char_features = max_char_features
        self.max_char_features_dense = max_char_features_dense
        self.min_df = min_df
        self.word_min_df = word_min_df
        self.char_min_df = char_min_df
        self.max_df = max_df

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

        text = re.sub(r"<[^>]+>", " htmltoken ", text)
        text = re.sub(r"(http|https)://\S+|www\.\S+", " urltoken ", text)
        text = PHONE_PATTERN.sub(" phonetoken ", text)
        text = re.sub(
            r"\b[\w\.-]+@[\w\.-]+\.\w+\b",
            " emailtoken ",
            text,
            flags=re.UNICODE,
        )
        text = re.sub(r"[$€£₴¥]+", " currencytoken ", text)
        text = re.sub(r"\b\d+[%]\b|\b\d+\s*відсотк\w*\b", " percenttoken ", text)
        text = re.sub(r"\d+", " numtoken ", text)

        text = re.sub(r"[^\w\s!?%'\-]", " ", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip()

        return text

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

        return hstack([x_word, x_char_wb, x_char_dense]).tocsr()

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)
