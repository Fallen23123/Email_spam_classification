import unittest

import pandas as pd

from dataset_loader import BODY_MARKER, SUBJECT_MARKER, standardize_dataset_frame
from preprocessor import SpamPreprocessor


class SubjectBodyAwareFeatureTests(unittest.TestCase):
    def test_standardize_dataset_frame_preserves_subject_and_body_markers(self):
        frame = pd.DataFrame(
            {
                "label": ["ham"],
                "subject": ["Invoice #2048 ready"],
                "body": ["Thank you for your purchase. Receipt is attached."],
                "sender": ["billing@paypal.com"],
                "sender_domain": ["paypal.com"],
            }
        )

        prepared = standardize_dataset_frame(frame, source_name="sample.csv")

        self.assertEqual(prepared.iloc[0]["sender"], "billing@paypal.com")
        self.assertEqual(prepared.iloc[0]["sender_domain"], "paypal.com")
        self.assertEqual(prepared.iloc[0]["subject"], "Invoice #2048 ready")
        self.assertEqual(prepared.iloc[0]["body"], "Thank you for your purchase. Receipt is attached.")
        self.assertIn("X-Sender: billing@paypal.com", prepared.iloc[0]["text"])
        self.assertIn("X-Sender-Domain: paypal.com", prepared.iloc[0]["text"])
        self.assertIn(SUBJECT_MARKER, prepared.iloc[0]["text"])
        self.assertIn(BODY_MARKER, prepared.iloc[0]["text"])

    def test_preprocessor_extracts_subject_body_structural_features(self):
        preprocessor = SpamPreprocessor()
        text = (
            "subjecttoken Your invoice is ready "
            "bodytoken Thank you for your purchase. Receipt is attached."
        )

        features = preprocessor.extract_structural_features(text)
        feature_map = dict(zip(preprocessor.structural_feature_names(), features))

        self.assertEqual(feature_map["has_explicit_subject_body"], 1.0)
        self.assertGreater(feature_map["subject_char_len_log"], 0.0)
        self.assertGreater(feature_map["body_char_len_log"], 0.0)
        self.assertGreater(feature_map["subject_token_count_log"], 0.0)
        self.assertGreater(feature_map["body_token_count_log"], 0.0)

    def test_subject_header_fallback_is_detected_for_plain_text_input(self):
        preprocessor = SpamPreprocessor()
        text = "Subject: Delivery update\nYour order has been shipped and is on the way."

        subject, body, has_sections = preprocessor.split_subject_body_sections(text)

        self.assertTrue(has_sections)
        self.assertEqual(subject, "Delivery update")
        self.assertEqual(body, "Your order has been shipped and is on the way.")

    def test_preprocessor_extracts_sender_and_domain_features(self):
        preprocessor = SpamPreprocessor()
        text = (
            "X-Sender: alerts@secure-payments.xyz\n"
            "Subject: Verify account\n"
            "Please confirm your account here: http://bit.ly/reset-access https://pay-support.xyz/verify"
        )

        features = preprocessor.extract_structural_features(text)
        feature_map = dict(zip(preprocessor.structural_feature_names(), features))

        self.assertEqual(feature_map["sender_present"], 1.0)
        self.assertEqual(feature_map["sender_domain_present"], 1.0)
        self.assertGreater(feature_map["shortened_url_count_log"], 0.0)
        self.assertGreater(feature_map["suspicious_url_domain_count_log"], 0.0)
        self.assertGreater(feature_map["sender_domain_has_suspicious_tld"], 0.0)


if __name__ == "__main__":
    unittest.main()
