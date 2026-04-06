import unittest

from safe_mail_rules import detect_safe_business_rule


class SafeMailRulesRegressionTests(unittest.TestCase):
    def test_order_shipment_message_is_whitelisted_as_ham(self):
        text = (
            "Your order #12345 has been shipped and is expected to arrive by Friday. "
            "You can track your package using the link provided in your account dashboard."
        )

        result = detect_safe_business_rule(text)

        self.assertIsNotNone(result)
        self.assertEqual(result["decision_source"], "safe_business_rule")
        self.assertEqual(result["predicted_label"], "ham")
        self.assertEqual(result["rule_name"], "order_shipment")
        self.assertIn("order", result["matched_signals"])
        self.assertTrue(any(signal in {"shipped", "track"} for signal in result["matched_signals"]))

    def test_invoice_receipt_message_is_whitelisted_as_ham(self):
        text = (
            "Thank you for your purchase. Your invoice INV-2048 is attached and "
            "your payment receipt is now available in the account portal."
        )

        result = detect_safe_business_rule(text)

        self.assertIsNotNone(result)
        self.assertEqual(result["predicted_label"], "ham")
        self.assertEqual(result["rule_name"], "invoice_receipt")

    def test_verification_code_with_url_is_not_whitelisted(self):
        text = (
            "Your verification code is 904321. Sign in here immediately: "
            "https://example.com/verify"
        )

        result = detect_safe_business_rule(text)

        self.assertIsNone(result)

    def test_loan_spam_is_not_whitelisted(self):
        text = (
            "Вам схвалено кредит на суму 50 000 грн під 0%! Отримайте гроші на карту "
            "за 5 хвилин без довідок про доходи. Переходьте за посиланням прямо зараз."
        )

        result = detect_safe_business_rule(text)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
