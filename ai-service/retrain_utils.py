from __future__ import annotations

import sqlite3

import pandas as pd

from config import (
    AUTO_RETRAIN_EVALUATION_SCOPE,
    AUTO_RETRAIN_FEEDBACK_WEIGHT,
)
from dataset_loader import (
    combine_training_data,
    filter_feedback_for_training,
    load_training_corpora,
    prepare_feedback_frame,
    split_base_dataframe,
)
from runtime_metadata import find_best_threshold, refresh_runtime_metadata


def load_feedback_rows_from_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(
            "SELECT timestamp, text, actual_label as label FROM feedback",
            conn,
        )
    finally:
        conn.close()


def run_holdout_retrain(
    pipeline,
    previous_meta,
    db_path,
    data_dir="data",
    ignored_filenames=None,
    feedback_weight=AUTO_RETRAIN_FEEDBACK_WEIGHT,
):
    base_df = load_training_corpora(
        data_dir=data_dir,
        ignored_filenames=ignored_filenames or {"feedback_log.csv"},
    )
    train_df, val_df, test_df = split_base_dataframe(base_df)

    feedback_rows_df = load_feedback_rows_from_db(db_path)
    raw_feedback_df = prepare_feedback_frame(
        feedback_rows_df,
        label_column="label",
        text_column="text",
        source_name="user_feedback_db",
    )
    feedback_df = filter_feedback_for_training(
        raw_feedback_df,
        holdout_frames=[val_df, test_df],
    )

    if feedback_df.empty:
        return None

    train_feedback_df = combine_training_data(
        train_df,
        feedback_df=feedback_df,
        feedback_weight=feedback_weight,
    )
    full_train_df = combine_training_data(
        pd.concat([train_df, val_df], ignore_index=True),
        feedback_df=feedback_df,
        feedback_weight=feedback_weight,
    )

    pipeline.fit(
        train_feedback_df["text"].astype(str),
        train_feedback_df["label"].astype(int),
    )
    val_scores = pipeline.predict_proba(val_df["text"].astype(str))[:, 1]
    threshold = find_best_threshold(val_df["label"], val_scores)

    pipeline.fit(
        full_train_df["text"].astype(str),
        full_train_df["label"].astype(int),
    )
    meta = refresh_runtime_metadata(
        pipeline,
        evaluation_df=test_df,
        threshold=threshold,
        previous_meta=previous_meta,
        train_size=len(full_train_df),
        validation_size=len(val_df),
        test_size=len(test_df),
        total_samples_trained=len(full_train_df),
        evaluation_scope=AUTO_RETRAIN_EVALUATION_SCOPE,
    )
    meta["feedback_training_size"] = int(len(feedback_df))
    meta["feedback_holdout_excluded"] = int(len(raw_feedback_df) - len(feedback_df))

    return {
        "pipeline": pipeline,
        "meta": meta,
        "threshold": threshold,
        "base_df": base_df,
        "train_df": train_df,
        "validation_df": val_df,
        "test_df": test_df,
        "raw_feedback_df": raw_feedback_df,
        "feedback_df": feedback_df,
        "full_train_df": full_train_df,
    }
