import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline

from dataset_loader import load_training_corpora, split_base_dataframe
from preprocessor import SpamPreprocessor
from retrain_utils import run_holdout_retrain


def build_pipeline():
    return Pipeline(
        [
            (
                "prep",
                SpamPreprocessor(
                    max_word_features=300,
                    max_char_features=300,
                    max_char_features_dense=200,
                ),
            ),
            ("clf", ComplementNB(alpha=0.6)),
        ]
    )


class HoldoutRetrainTests(unittest.TestCase):
    def test_run_holdout_retrain_excludes_feedback_that_hits_holdout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            data_dir = temp_path / "data"
            data_dir.mkdir()
            db_path = temp_path / "feedback.db"

            ham_rows = [
                {"label": "ham", "text": f"Order update number {idx} shipped successfully and available in dashboard"}
                for idx in range(30)
            ]
            spam_rows = [
                {"label": "spam", "text": f"Claim bonus prize now urgent credit offer {idx}"}
                for idx in range(30)
            ]
            dataset_df = pd.DataFrame(ham_rows + spam_rows)
            dataset_df.to_csv(data_dir / "spam.csv", index=False)

            base_df = load_training_corpora(data_dir=data_dir, ignored_filenames={"feedback_log.csv"})
            _, val_df, test_df = split_base_dataframe(base_df)
            holdout_text = val_df.iloc[0]["text"]
            unique_feedback_text = "Receipt available for your purchase in the account dashboard"

            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    "CREATE TABLE feedback (timestamp TEXT, text TEXT, actual_label TEXT, predicted_label TEXT, user_is_correct BOOLEAN)"
                )
                conn.execute(
                    "INSERT INTO feedback VALUES (?, ?, ?, ?, ?)",
                    ("2026-04-06 10:00:00", holdout_text, "ham", "spam", 0),
                )
                conn.execute(
                    "INSERT INTO feedback VALUES (?, ?, ?, ?, ?)",
                    ("2026-04-06 10:01:00", unique_feedback_text, "ham", "spam", 0),
                )
                conn.commit()
            finally:
                conn.close()

            result = run_holdout_retrain(
                pipeline=build_pipeline(),
                previous_meta={"model_name": "ComplementNB"},
                db_path=str(db_path),
                data_dir=data_dir,
            )

            self.assertIsNotNone(result)
            self.assertEqual(result["meta"]["evaluation_scope"], "auto_retrain_holdout")
            self.assertEqual(result["meta"]["feedback_training_size"], 1)
            self.assertEqual(result["meta"]["feedback_holdout_excluded"], 1)
            self.assertNotIn(holdout_text, set(result["feedback_df"]["text"]))
            self.assertIn(unique_feedback_text, set(result["feedback_df"]["text"]))
            self.assertEqual(result["meta"]["test_size"], len(test_df))
            self.assertIn("f1", result["meta"]["test_metrics"])
            self.assertGreaterEqual(result["meta"]["threshold"], 0.0)
            self.assertLessEqual(result["meta"]["threshold"], 1.0)


if __name__ == "__main__":
    unittest.main()
