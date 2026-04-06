from __future__ import annotations

import re


URL_PATTERN = re.compile(r"(http|https)://\S+|www\.\S+", flags=re.IGNORECASE)

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


def detect_safe_business_rule(text: str):
    normalized_text = str(text or "").strip()
    lowered_text = normalized_text.lower()

    if len(lowered_text) < 12:
        return None

    suspicious_matches = _collect_pattern_matches(lowered_text, SUSPICIOUS_PATTERNS)
    has_url = bool(URL_PATTERN.search(normalized_text))

    if suspicious_matches:
        return None

    for profile in SAFE_BUSINESS_PROFILES:
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
