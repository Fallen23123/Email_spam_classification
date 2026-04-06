import re
from urllib.parse import urlparse

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
SUBJECT_HEADER_PATTERN = re.compile(
    r"^\s*subject\s*:\s*(.+?)(?:\r?\n|$)(.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)
SENDER_HEADER_PATTERN = re.compile(
    r"(?im)^\s*(?:from|sender|x-sender)\s*:\s*(.+)$"
)
SENDER_DOMAIN_HEADER_PATTERN = re.compile(
    r"(?im)^\s*x-sender-domain\s*:\s*(.+)$"
)
METADATA_HEADER_PATTERN = re.compile(
    r"(?im)^\s*x-(?:sender|sender-domain)\s*:\s*.+(?:\r?\n)?"
)
ANGLE_EMAIL_PATTERN = re.compile(r"<\s*([\w\.-]+@[\w\.-]+\.\w+)\s*>")
IP_HOST_PATTERN = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

PROTECTED_TOKENS = {
    "htmltoken",
    "urltoken",
    "emailtoken",
    "currencytoken",
    "numtoken",
    "phonetoken",
    "percenttoken",
    "subjecttoken",
    "bodytoken",
}

SUSPICIOUS_TLDS = {
    "click",
    "country",
    "gq",
    "info",
    "loan",
    "monster",
    "rest",
    "ru",
    "shop",
    "support",
    "top",
    "work",
    "xyz",
    "zip",
}

URL_SHORTENER_DOMAINS = {
    "bit.ly",
    "cutt.ly",
    "is.gd",
    "ow.ly",
    "rb.gy",
    "rebrand.ly",
    "shorturl.at",
    "tinyurl.com",
    "t.ly",
    "t.co",
}

FREE_MAIL_DOMAINS = {
    "aol.com",
    "gmail.com",
    "hotmail.com",
    "i.ua",
    "icloud.com",
    "mail.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "ukr.net",
    "yahoo.com",
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
    "has_explicit_subject_body",
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
    "subject_char_len_log",
    "body_char_len_log",
    "subject_token_count_log",
    "body_token_count_log",
    "subject_keyword_hits_log",
    "body_keyword_hits_log",
    "subject_has_url",
    "body_url_count_log",
    "sender_present",
    "sender_domain_present",
    "sender_domain_is_free_mail",
    "sender_domain_matches_url_domain",
    "sender_domain_differs_from_url_domain",
    "sender_domain_has_suspicious_tld",
    "url_domain_count_log",
    "suspicious_url_domain_count_log",
    "shortened_url_count_log",
    "ip_url_count_log",
    "punycode_url_count_log",
    "suspicious_url_tld_count_log",
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
        text = self.strip_metadata_headers(text)
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

    def split_subject_body_sections(self, text):
        raw_text = self.strip_metadata_headers(text)
        raw_text = str(raw_text or "").strip()
        subject = ""
        body = raw_text
        has_explicit_sections = False

        subject_match = re.search(r"\bsubjecttoken\b", raw_text, flags=re.IGNORECASE)
        body_match = re.search(r"\bbodytoken\b", raw_text, flags=re.IGNORECASE)
        if body_match:
            has_explicit_sections = True
            if subject_match and subject_match.start() < body_match.start():
                subject = raw_text[subject_match.end():body_match.start()].strip()
            body = raw_text[body_match.end():].strip()
            return subject, body, has_explicit_sections

        header_match = SUBJECT_HEADER_PATTERN.match(raw_text)
        if header_match:
            has_explicit_sections = True
            subject = header_match.group(1).strip()
            body = header_match.group(2).strip()

        return subject, body, has_explicit_sections

    def strip_metadata_headers(self, text):
        return METADATA_HEADER_PATTERN.sub("", str(text or "")).strip()

    def normalize_domain(self, value):
        domain = str(value or "").strip().lower()
        domain = domain.strip(" <>[](){}\"'")
        if domain.startswith("mailto:"):
            domain = domain.split("mailto:", 1)[1]
        if "@" in domain:
            domain = domain.rsplit("@", 1)[-1]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain.rstrip(".,;:/")

    def extract_sender_metadata(self, text):
        raw_text = str(text or "")
        sender_domain_match = SENDER_DOMAIN_HEADER_PATTERN.search(raw_text)
        sender_domain = self.normalize_domain(
            sender_domain_match.group(1) if sender_domain_match else ""
        )

        sender_match = SENDER_HEADER_PATTERN.search(raw_text)
        sender_value = sender_match.group(1).strip() if sender_match else ""
        sender_email = ""
        if sender_value:
            angle_match = ANGLE_EMAIL_PATTERN.search(sender_value)
            if angle_match:
                sender_email = angle_match.group(1).strip().lower()
            else:
                email_match = EMAIL_PATTERN.search(sender_value)
                if email_match:
                    sender_email = email_match.group(0).strip().lower()

        if not sender_domain and sender_email:
            sender_domain = self.normalize_domain(sender_email)

        return {
            "sender": sender_value,
            "sender_email": sender_email,
            "sender_domain": sender_domain,
        }

    def extract_url_domains(self, text):
        domains = []
        for match in URL_PATTERN.finditer(str(text or "")):
            raw_url = match.group(0).strip().rstrip(".,);]")
            parsed_url = raw_url if re.match(r"^https?://", raw_url, flags=re.IGNORECASE) else f"http://{raw_url}"
            try:
                host = urlparse(parsed_url).hostname or ""
            except ValueError:
                host = ""
            host = self.normalize_domain(host)
            if host:
                domains.append(host)
        return domains

    def extract_email_domains(self, text):
        return [
            self.normalize_domain(match.group(0))
            for match in EMAIL_PATTERN.finditer(str(text or ""))
        ]

    def is_shortener_domain(self, domain):
        domain = self.normalize_domain(domain)
        return any(domain == shortener or domain.endswith(f".{shortener}") for shortener in URL_SHORTENER_DOMAINS)

    def has_suspicious_tld(self, domain):
        domain = self.normalize_domain(domain)
        if "." not in domain:
            return False
        return domain.rsplit(".", 1)[-1] in SUSPICIOUS_TLDS

    def is_ip_host(self, domain):
        return bool(IP_HOST_PATTERN.match(self.normalize_domain(domain)))

    def extract_structural_features(self, text):
        raw_text = str(text or "").strip()
        metadata = self.extract_sender_metadata(raw_text)
        content_text = self.strip_metadata_headers(raw_text)
        lowered_text = content_text.lower()
        cleaned_text = self.clean_text(content_text)
        tokens = self.multilingual_tokenize(cleaned_text)
        subject_text, body_text, has_explicit_sections = self.split_subject_body_sections(content_text)
        cleaned_subject = self.clean_text(subject_text)
        cleaned_body = self.clean_text(body_text)
        subject_tokens = self.multilingual_tokenize(cleaned_subject)
        body_tokens = self.multilingual_tokenize(cleaned_body)

        sender_domain = metadata["sender_domain"]
        url_domains = self.extract_url_domains(content_text)
        email_domains = self.extract_email_domains(content_text)
        combined_domains = set(url_domains + email_domains)
        suspicious_url_domains = sum(self.has_suspicious_tld(domain) for domain in url_domains)
        shortened_url_domains = sum(self.is_shortener_domain(domain) for domain in url_domains)
        ip_url_domains = sum(self.is_ip_host(domain) for domain in url_domains)
        punycode_url_domains = sum("xn--" in domain for domain in url_domains)
        sender_matches_url_domain = bool(sender_domain and sender_domain in set(url_domains))
        sender_differs_from_url_domain = bool(sender_domain and url_domains and sender_domain not in set(url_domains))

        letter_count = sum(char.isalpha() for char in content_text)
        uppercase_count = sum(char.isupper() for char in content_text if char.isalpha())
        digit_count = sum(char.isdigit() for char in content_text)
        token_count = len(tokens)
        long_token_count = sum(len(token) >= 12 for token in tokens)
        unique_token_ratio = (len(set(tokens)) / token_count) if token_count else 0.0
        uppercase_word_count = len(UPPERCASE_WORD_PATTERN.findall(content_text))
        keyword_hits = sum(1 for keyword in SPAM_HINT_KEYWORDS if keyword in lowered_text)
        subject_keyword_hits = sum(1 for keyword in SPAM_HINT_KEYWORDS if keyword in subject_text.lower())
        body_keyword_hits = sum(1 for keyword in SPAM_HINT_KEYWORDS if keyword in body_text.lower())

        return np.array(
            [
                float(has_explicit_sections),
                np.log1p(len(content_text)),
                np.log1p(token_count),
                np.log1p(len(URL_PATTERN.findall(content_text))),
                np.log1p(len(EMAIL_PATTERN.findall(content_text))),
                np.log1p(len(PHONE_PATTERN.findall(content_text))),
                np.log1p(len(CURRENCY_PATTERN.findall(content_text))),
                np.log1p(len(PERCENT_PATTERN.findall(lowered_text))),
                digit_count / max(len(content_text), 1),
                uppercase_count / max(letter_count, 1),
                np.log1p(content_text.count("!")),
                np.log1p(content_text.count("?")),
                np.log1p(content_text.count("\n")),
                np.log1p(len(REPEATED_PUNCT_PATTERN.findall(content_text))),
                uppercase_word_count / max(token_count, 1),
                long_token_count / max(token_count, 1),
                unique_token_ratio,
                np.log1p(keyword_hits),
                np.log1p(len(subject_text)),
                np.log1p(len(body_text)),
                np.log1p(len(subject_tokens)),
                np.log1p(len(body_tokens)),
                np.log1p(subject_keyword_hits),
                np.log1p(body_keyword_hits),
                float(bool(URL_PATTERN.search(subject_text))),
                np.log1p(len(URL_PATTERN.findall(body_text))),
                float(bool(metadata["sender"] or metadata["sender_email"])),
                float(bool(sender_domain)),
                float(sender_domain in FREE_MAIL_DOMAINS) if sender_domain else 0.0,
                float(sender_matches_url_domain),
                float(sender_differs_from_url_domain),
                float(self.has_suspicious_tld(sender_domain)) if sender_domain else 0.0,
                np.log1p(len(set(url_domains))),
                np.log1p(suspicious_url_domains),
                np.log1p(shortened_url_domains),
                np.log1p(ip_url_domains),
                np.log1p(punycode_url_domains),
                np.log1p(sum(self.has_suspicious_tld(domain) for domain in combined_domains)),
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

        feature_parts = self.build_feature_parts(X)
        parts = [
            feature_parts["x_word"],
            feature_parts["x_char_wb"],
            feature_parts["x_char_dense"],
        ]

        if feature_parts["x_structural"] is not None:
            parts.append(feature_parts["x_structural"])

        return hstack(parts).tocsr()

    def fit_transform(self, X, y=None):
        return self.fit(X, y).transform(X)

    def build_feature_parts(self, X):
        check_is_fitted(
            self,
            ["word_vectorizer_", "char_vectorizer_wb_", "char_vectorizer_dense_"],
        )

        cleaned = [self.clean_text(x) for x in X]
        x_word = self.word_vectorizer_.transform(cleaned)
        x_char_wb = self.char_vectorizer_wb_.transform(cleaned)
        x_char_dense = self.char_vectorizer_dense_.transform(cleaned)

        x_structural = None
        if getattr(self, "include_structural_features_", False):
            structural_array = np.vstack([self.extract_structural_features(text) for text in X])
            fitted_structural_feature_count = len(
                getattr(self, "structural_feature_names_", self.structural_feature_names())
            )
            current_structural_feature_count = structural_array.shape[1]

            if current_structural_feature_count > fitted_structural_feature_count:
                structural_array = structural_array[:, :fitted_structural_feature_count]
            elif current_structural_feature_count < fitted_structural_feature_count:
                padding = np.zeros(
                    (structural_array.shape[0], fitted_structural_feature_count - current_structural_feature_count),
                    dtype=float,
                )
                structural_array = np.hstack([structural_array, padding])

            x_structural = csr_matrix(structural_array)

        return {
            "cleaned": cleaned,
            "x_word": x_word,
            "x_char_wb": x_char_wb,
            "x_char_dense": x_char_dense,
            "x_structural": x_structural,
        }
