import joblib

from config import RETRAIN_THRESHOLD
from retrain_utils import load_feedback_rows_from_db, run_holdout_retrain


DB_PATH = "data/feedback.db"
MODEL_PATH = "models/spam_pipeline.pkl"
META_PATH = "models/model_meta.pkl"


def main():
    feedback_rows = load_feedback_rows_from_db(DB_PATH)
    if len(feedback_rows) < RETRAIN_THRESHOLD:
        print(
            f"[SKIP] Для retrain потрібно щонайменше {RETRAIN_THRESHOLD} feedback-записів. "
            f"Зараз: {len(feedback_rows)}."
        )
        return

    pipeline = joblib.load(MODEL_PATH)
    meta = joblib.load(META_PATH)
    result = run_holdout_retrain(
        pipeline=pipeline,
        previous_meta=meta,
        db_path=DB_PATH,
        data_dir="data",
    )

    if result is None:
        print("[SKIP] Після holdout-фільтрації не залишилось feedback-прикладів для retrain.")
        return

    joblib.dump(result["pipeline"], MODEL_PATH)
    joblib.dump(result["meta"], META_PATH)

    print("[OK] Holdout retrain завершено.")
    print(f"Threshold: {result['meta']['threshold']:.6f}")
    print(
        "Feedback used for train: "
        f"{result['meta'].get('feedback_training_size', 0)} | "
        "feedback excluded from holdout: "
        f"{result['meta'].get('feedback_holdout_excluded', 0)}"
    )
    print(
        "Test F1: "
        f"{result['meta'].get('test_metrics', {}).get('f1', 0.0):.6f}"
    )


if __name__ == "__main__":
    main()
