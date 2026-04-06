import unittest

from api import (
    build_analysis_cache_key,
    clear_analysis_cache,
    get_cached_analysis,
    resolve_decision_threshold,
    set_cached_analysis,
    should_include_explainability,
)


class ApiPerformanceTests(unittest.TestCase):
    def setUp(self):
        clear_analysis_cache()

    def tearDown(self):
        clear_analysis_cache()

    def test_low_risk_ham_defers_explainability(self):
        include_details, reason = should_include_explainability(
            score=0.08,
            threshold=0.55,
            decision_source="model",
            force=False,
        )

        self.assertFalse(include_details)
        self.assertEqual(reason, "deferred_low_risk_ham")

    def test_borderline_prediction_keeps_explainability(self):
        include_details, reason = should_include_explainability(
            score=0.49,
            threshold=0.55,
            decision_source="model",
            force=False,
        )

        self.assertTrue(include_details)
        self.assertEqual(reason, "near_threshold")

    def test_analysis_cache_roundtrip(self):
        cache_key = build_analysis_cache_key("Invoice ready for download", False)
        payload = {"spam_score": 0.07, "decision_source": "model"}

        set_cached_analysis(cache_key, payload)
        cached = get_cached_analysis(cache_key)

        self.assertIsNotNone(cached)
        self.assertEqual(cached["spam_score"], 0.07)
        self.assertEqual(cached["decision_source"], "model")

    def test_decision_threshold_has_minimum_floor(self):
        self.assertEqual(resolve_decision_threshold(0.17), 0.5)
        self.assertEqual(resolve_decision_threshold(0.73), 0.73)


if __name__ == "__main__":
    unittest.main()
