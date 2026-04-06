from __future__ import annotations

import re
from urllib.parse import urlparse


URL_PATTERN = re.compile(r"(http|https)://\S+|www\.\S+", flags=re.IGNORECASE)
SENDER_HEADER_PATTERN = re.compile(r"(?im)^\s*(?:from|sender|x-sender)\s*:\s*(.+)$")
SENDER_DOMAIN_HEADER_PATTERN = re.compile(r"(?im)^\s*x-sender-domain\s*:\s*(.+)$")
EMAIL_PATTERN = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", re.IGNORECASE)
ANGLE_EMAIL_PATTERN = re.compile(r"<\s*([\w\.-]+@[\w\.-]+\.\w+)\s*>")
METADATA_HEADER_PATTERN = re.compile(
    r"(?im)^\s*x-(?:sender|sender-domain)\s*:\s*.+(?:\r?\n)?"
)

SUSPICIOUS_PATTERNS = {
    "loan_offer": re.compile(r"\b(credit|loan|cash advance|кредит|позика)\b", re.IGNORECASE),
    "money_claim": re.compile(r"\b(claim|winner|bonus|prize|виграл|бонус)\b", re.IGNORECASE),
    "urgent_marketing": re.compile(r"\b(urgent|act now|limited time|тільки сьогодні|терміново)\b", re.IGNORECASE),
    "suspicious_finance": re.compile(r"\b(crypto|investment|подвоїти|заробіток)\b", re.IGNORECASE),
}

SAFE_BUSINESS_PROFILES = (
    {
        "name": "order_shipment",
        "label": "Order / Shipment Update",
        "requires": (
            re.compile(r"\b(order|замовлен)\b", re.IGNORECASE),
            re.compile(r"\b(shipped|shipping|delivery|track|tracking|доставк|відправлен)\b", re.IGNORECASE),
        ),
    },
    {
        "name": "invoice_receipt",
        "label": "Invoice / Receipt",
        "requires": (
            re.compile(r"\b(invoice|receipt|чек|рахунок)\b", re.IGNORECASE),
            re.compile(r"\b(order|purchase|payment|thank you|дякуємо|оплат)\b", re.IGNORECASE),
        ),
    },
    {
        "name": "verification_code",
        "label": "Verification Code",
        "requires": (
            re.compile(r"\b(code|otp|password|verification|verify|код)\b", re.IGNORECASE),
            re.compile(r"\b(account|login|security|sign in|вхід|безпек)\b", re.IGNORECASE),
        ),
        "forbid_url": True,
    },
    {
        "name": "booking_confirmation",
        "label": "Booking / Reservation Confirmation",
        "requires": (
            re.compile(r"\b(booking|reservation|itinerary|ticket|бронюван|резервац)\b", re.IGNORECASE),
            re.compile(r"\b(confirm|confirmed|details|check-in|підтверджен|детал)\b", re.IGNORECASE),
        ),
    },
    {
        "name": "freelance_project_negotiation",
        "label": "Freelance / Project Negotiation",
        "requires": (
            re.compile(r"\b(project|про[еє]кт|task|assignment|завдан|client|клієнт)\b", re.IGNORECASE),
            re.compile(r"\b(payment|budget|invoice|payoneer|usdt|crypto|оплат|бюджет|крипт)\b", re.IGNORECASE),
            re.compile(r"\b(code|review|sprint|deadline|deliver|тестов|код|спринт|починаємо)\b", re.IGNORECASE),
        ),
        "allow_suspicious_patterns": {"suspicious_finance"},
    },
)

LOOKALIKE_BRAND_DOMAINS = {
    "Google": ("google.com", "accounts.google.com", "support.google.com"),
    "Microsoft": ("microsoft.com", "login.microsoftonline.com", "account.microsoft.com"),
    "PayPal": ("paypal.com", "www.paypal.com"),
    "Apple": ("apple.com", "idmsa.apple.com", "icloud.com"),
    "Amazon": ("amazon.com", "amazonaws.com"),
    "Facebook": ("facebook.com", "meta.com"),
    "Instagram": ("instagram.com",),
}

LOOKALIKE_KEYWORDS = {
    "secure",
    "support",
    "verify",
    "update",
    "login",
    "signin",
    "account",
    "billing",
    "auth",
    "wallet",
    "pay",
}

LEET_TRANSLATION = str.maketrans(
    {
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "6": "g",
        "7": "t",
        "8": "b",
        "9": "g",
        "$": "s",
        "@": "a",
    }
)


def _collect_pattern_matches(text, patterns_map):
    matches = []
    for name, pattern in patterns_map.items():
        if pattern.search(text):
            matches.append(name)
    return matches


def _extract_required_signals(text, patterns):
    signals = []
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            signals.append(match.group(0))
    return signals


def _normalize_domain(value):
    domain = str(value or "").strip().lower()
    domain = domain.strip(" <>[](){}\"'")
    if "@" in domain:
        domain = domain.rsplit("@", 1)[-1]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.rstrip(".,;:/")


def _strip_metadata_headers(text):
    return METADATA_HEADER_PATTERN.sub("", str(text or "")).strip()


def _extract_url_domains(text):
    domains = []
    for match in URL_PATTERN.finditer(str(text or "")):
        raw_url = match.group(0).strip().rstrip(".,);]")
        parsed_url = raw_url if re.match(r"^https?://", raw_url, flags=re.IGNORECASE) else f"http://{raw_url}"
        try:
            host = urlparse(parsed_url).hostname or ""
        except ValueError:
            host = ""
        host = _normalize_domain(host)
        if host:
            domains.append(host)
    return domains


def _extract_sender_domains(text):
    raw_text = str(text or "")
    domains = []

    sender_domain_match = SENDER_DOMAIN_HEADER_PATTERN.search(raw_text)
    if sender_domain_match:
        sender_domain = _normalize_domain(sender_domain_match.group(1))
        if sender_domain:
            domains.append(sender_domain)

    sender_match = SENDER_HEADER_PATTERN.search(raw_text)
    if sender_match:
        sender_value = sender_match.group(1).strip()
        angle_match = ANGLE_EMAIL_PATTERN.search(sender_value)
        if angle_match:
            domains.append(_normalize_domain(angle_match.group(1)))
        else:
            email_match = EMAIL_PATTERN.search(sender_value)
            if email_match:
                domains.append(_normalize_domain(email_match.group(0)))

    return [domain for domain in domains if domain]


def _normalize_label(label):
    normalized = re.sub(r"[^a-z0-9]", "", str(label or "").lower())
    return normalized.translate(LEET_TRANSLATION)


def _is_official_domain(domain, official_domains):
    domain = _normalize_domain(domain)
    return any(domain == official or domain.endswith(f".{official}") for official in official_domains)


def _find_lookalike_brand(domain):
    normalized_domain = _normalize_domain(domain)
    labels = [label for label in normalized_domain.split(".")[:-1] if label]

    for brand, official_domains in LOOKALIKE_BRAND_DOMAINS.items():
        official_labels = {
            _normalize_label(official.split(".")[0])
            for official in official_domains
        }
        if _is_official_domain(normalized_domain, official_domains):
            continue

        for label in labels:
            normalized_label = _normalize_label(label)
            compact_label = re.sub(r"[^a-z]", "", normalized_label)
            for official_label in official_labels:
                if not official_label:
                    continue
                if normalized_label == official_label and label.lower() != official_label:
                    return brand
                if official_label in compact_label and compact_label != official_label:
                    suffix = compact_label.replace(official_label, "")
                    if suffix and any(keyword in compact_label for keyword in LOOKALIKE_KEYWORDS):
                        return brand

    return None


def detect_lookalike_domain_rule(text: str):
    normalized_text = str(text or "").strip()
    content_text = _strip_metadata_headers(normalized_text)
    candidate_domains = []

    for domain in _extract_sender_domains(normalized_text):
        candidate_domains.append(("sender", domain))
    for domain in _extract_url_domains(content_text):
        candidate_domains.append(("url", domain))

    findings = []
    seen_pairs = set()
    for source, domain in candidate_domains:
        pair = (source, domain)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        brand = _find_lookalike_brand(domain)
        if brand:
            findings.append((source, domain, brand))

    if not findings:
        return None

    matched_signals = [f"{source} domain: {domain}" for source, domain, _ in findings]
    impersonated_brands = []
    for _, _, brand in findings:
        if brand not in impersonated_brands:
            impersonated_brands.append(brand)

    return {
        "predicted_label": "spam",
        "is_spam_predicted": True,
        "score": 0.995,
        "decision_source": "phishing_domain_rule",
        "reason": "Detected a lookalike domain that appears to impersonate a trusted brand.",
        "rule_name": "lookalike_domain",
        "rule_label": "Lookalike Domain / Brand Impersonation",
        "rule_matches": impersonated_brands,
        "matched_signals": matched_signals + [f"brand impersonation: {brand}" for brand in impersonated_brands],
    }


def detect_safe_business_rule(text: str):
    normalized_text = str(text or "").strip()
    lowered_text = _strip_metadata_headers(normalized_text).lower()

    if len(lowered_text) < 12:
        return None

    has_url = bool(URL_PATTERN.search(normalized_text))

    for profile in SAFE_BUSINESS_PROFILES:
        suspicious_matches = _collect_pattern_matches(lowered_text, SUSPICIOUS_PATTERNS)
        allowed_suspicious = set(profile.get("allow_suspicious_patterns", set()))
        blocking_suspicious = [
            match for match in suspicious_matches if match not in allowed_suspicious
        ]

        if blocking_suspicious:
            continue

        if all(pattern.search(lowered_text) for pattern in profile["requires"]):
            if profile.get("forbid_url") and has_url:
                continue
            matched_signals = _extract_required_signals(lowered_text, profile["requires"])

            return {
                "predicted_label": "ham",
                "is_spam_predicted": False,
                "score": 0.01,
                "decision_source": "safe_business_rule",
                "reason": "Matched safe-business whitelist profile.",
                "rule_name": profile["name"],
                "rule_label": profile["label"],
                "rule_matches": [profile["label"]],
                "matched_signals": matched_signals,
            }

    return None
