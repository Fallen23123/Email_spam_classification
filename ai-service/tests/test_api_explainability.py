import unittest

from api import compose_analysis_text, extract_metadata_signals, extract_subject_body_signals


class ApiExplainabilityTests(unittest.TestCase):
    def test_extract_subject_body_signals_returns_sectioned_lists(self):
        text = (
            "subjecttoken Verify your account now "
            "bodytoken Click the secure link to verify your account and restore access."
        )

        result = extract_subject_body_signals(text)

        self.assertIn("subject_signals", result)
        self.assertIn("body_signals", result)
        self.assertIn("subject_safe_signals", result)
        self.assertIn("body_safe_signals", result)
        self.assertIsInstance(result["subject_signals"], list)
        self.assertIsInstance(result["body_signals"], list)
        self.assertIsInstance(result["subject_safe_signals"], list)
        self.assertIsInstance(result["body_safe_signals"], list)

    def test_plain_text_subject_header_is_supported(self):
        text = (
            "Subject: Delivery update\n"
            "Your order has been shipped and your tracking details are available."
        )

        result = extract_subject_body_signals(text)

        self.assertIn("subject_signals", result)
        self.assertIn("body_signals", result)
        self.assertIn("subject_safe_signals", result)
        self.assertIn("body_safe_signals", result)

    def test_metadata_signals_capture_sender_domain_mismatch(self):
        text = compose_analysis_text(
            text="Please confirm your account via http://bit.ly/reset-access immediately.",
            sender="alerts@secure-payments.xyz",
        )

        result = extract_metadata_signals(text)

        self.assertTrue(any("sender domain" in signal for signal in result))
        self.assertTrue(any("shortened URL" in signal for signal in result))


if __name__ == "__main__":
    unittest.main()
