from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


DEFAULT_THRESHOLD = 0.5


def find_best_threshold(y_true, scores):
    if pd.Series(y_true).nunique() < 2:
        return DEFAULT_THRESHOLD

    precision, recall, thresholds = precision_recall_curve(y_true, scores)
    if len(thresholds) == 0:
        return DEFAULT_THRESHOLD

    f1_scores = 2 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1] + 1e-12)
    best_idx = int(np.argmax(f1_scores))
    return float(thresholds[best_idx])


def evaluate_scores(y_true, scores, threshold):
    pred = (scores >= threshold).astype(int)
    metrics = {
        "accuracy": float(accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "positive_rate_pred": float(pred.mean()),
    }

    if pd.Series(y_true).nunique() >= 2:
        metrics["roc_auc"] = float(roc_auc_score(y_true, scores))
        metrics["pr_auc"] = float(average_precision_score(y_true, scores))
    else:
        metrics["roc_auc"] = None
        metrics["pr_auc"] = None

    return metrics


def evaluate_subset(subset_df, pipeline, threshold, segment_name):
    if subset_df.empty:
        return None

    scores = pipeline.predict_proba(subset_df["text"])[:, 1]
    metrics = evaluate_scores(subset_df["label"], scores, threshold)

    return {
        "segment": segment_name,
        "support_total": int(len(subset_df)),
        "support_spam": int((subset_df["label"] == 1).sum()),
        "support_ham": int((subset_df["label"] == 0).sum()),
        **metrics,
    }


def build_segment_report(subset_df, pipeline, threshold, prefix, spam_subset_df, ham_subset_df):
    if subset_df.empty:
        return pd.DataFrame()

    rows = []
    aggregate_segments = [
        (f"{prefix}_all_sources_auto_retrain", subset_df),
        (f"{prefix}_spam_sources_auto_retrain", spam_subset_df),
        (f"{prefix}_ham_sources_auto_retrain", ham_subset_df),
    ]

    for segment_name, segment_df in aggregate_segments:
        row = evaluate_subset(segment_df, pipeline, threshold, segment_name)
        if row is not None:
            rows.append(row)

    for source_name, source_df in subset_df.groupby("source"):
        row = evaluate_subset(source_df, pipeline, threshold, source_name)
        if row is not None:
            rows.append(row)

    report_df = pd.DataFrame(rows)
    preferred_order = {
        f"{prefix}_all_sources_auto_retrain": 0,
        f"{prefix}_spam_sources_auto_retrain": 1,
        f"{prefix}_ham_sources_auto_retrain": 2,
    }
    report_df["sort_key"] = report_df["segment"].map(preferred_order).fillna(100)
    report_df = report_df.sort_values(["sort_key", "segment"]).drop(columns=["sort_key"])
    return report_df.reset_index(drop=True)


def dataframe_to_meta_payload(report_df):
    if report_df.empty:
        return {"columns": [], "rows": []}

    cleaned = report_df.replace({np.nan: None})
    rows = []

    for row in cleaned.to_dict(orient="records"):
        normalized_row = {}
        for key, value in row.items():
            if isinstance(value, np.integer):
                normalized_row[key] = int(value)
            elif isinstance(value, np.floating):
                normalized_row[key] = float(value)
            else:
                normalized_row[key] = value
        rows.append(normalized_row)

    return {
        "columns": list(report_df.columns),
        "rows": rows,
    }


def build_compact_summary(overall_metrics, ukrainian_report_df, english_report_df):
    summary = {
        "test_accuracy": overall_metrics["accuracy"],
        "test_precision": overall_metrics["precision"],
        "test_recall": overall_metrics["recall"],
        "test_f1": overall_metrics["f1"],
        "test_roc_auc": overall_metrics["roc_auc"],
        "test_pr_auc": overall_metrics["pr_auc"],
    }

    def add_segment(prefix, report_df, segment_name):
        if report_df.empty:
            return
        match = report_df[report_df["segment"] == segment_name]
        if match.empty:
            return
        row = match.iloc[0].replace({np.nan: None}).to_dict()
        for source_key, target_key in {
            "accuracy": "accuracy",
            "precision": "precision",
            "recall": "recall",
            "f1": "f1",
            "support_total": "support_total",
            "support_spam": "support_spam",
            "support_ham": "support_ham",
            "roc_auc": "roc_auc",
            "pr_auc": "pr_auc",
        }.items():
            value = row.get(source_key)
            if value is not None:
                summary[f"{prefix}_{target_key}"] = value

    add_segment("ua", ukrainian_report_df, "ukrainian_spam_sources_auto_retrain")
    add_segment("en", english_report_df, "english_spam_sources_auto_retrain")

    return summary


def build_dashboard_summary(model_name, threshold, evaluation_summary):
    def pct(value):
        if value is None:
            return None
        return round(float(value) * 100, 2)

    return {
        "best_model_name": model_name,
        "threshold": round(float(threshold), 6),
        "overall_accuracy_pct": pct(evaluation_summary.get("test_accuracy")),
        "overall_precision_pct": pct(evaluation_summary.get("test_precision")),
        "overall_recall_pct": pct(evaluation_summary.get("test_recall")),
        "overall_f1_pct": pct(evaluation_summary.get("test_f1")),
        "ua_spam_recall_pct": pct(evaluation_summary.get("ua_recall")),
        "ua_spam_f1_pct": pct(evaluation_summary.get("ua_f1")),
        "ua_spam_precision_pct": pct(evaluation_summary.get("ua_precision")),
        "ua_spam_support": evaluation_summary.get("ua_support_total"),
        "ua_spam_positive_support": evaluation_summary.get("ua_support_spam"),
        "en_spam_recall_pct": pct(evaluation_summary.get("en_recall")),
        "en_spam_f1_pct": pct(evaluation_summary.get("en_f1")),
        "en_spam_precision_pct": pct(evaluation_summary.get("en_precision")),
        "en_spam_support": evaluation_summary.get("en_support_total"),
        "en_spam_positive_support": evaluation_summary.get("en_support_spam"),
    }


def refresh_runtime_metadata(
    pipeline,
    evaluation_df,
    threshold,
    previous_meta=None,
    train_size=0,
    validation_size=0,
    test_size=None,
    total_samples_trained=None,
    evaluation_scope="auto_retrain_holdout",
):
    previous_meta = dict(previous_meta or {})

    if evaluation_df.empty:
        raise ValueError("Неможливо порахувати метрики на порожньому evaluation_df.")

    scores = pipeline.predict_proba(evaluation_df["text"])[:, 1]
    overall_metrics = evaluate_scores(evaluation_df["label"], scores, threshold)

    ukrainian_df = evaluation_df[
        evaluation_df["source"].str.startswith("ukrainian_", na=False)
    ].copy()
    english_df = evaluation_df[evaluation_df["source"].eq("spam.csv")].copy()

    ukrainian_report_df = build_segment_report(
        subset_df=ukrainian_df,
        pipeline=pipeline,
        threshold=threshold,
        prefix="ukrainian",
        spam_subset_df=ukrainian_df[ukrainian_df["source"].str.startswith("ukrainian_spam", na=False)],
        ham_subset_df=ukrainian_df[ukrainian_df["source"].str.startswith("ukrainian_ham", na=False)],
    )
    english_report_df = build_segment_report(
        subset_df=english_df,
        pipeline=pipeline,
        threshold=threshold,
        prefix="english",
        spam_subset_df=english_df[english_df["label"] == 1],
        ham_subset_df=english_df[english_df["label"] == 0],
    )

    evaluation_summary = build_compact_summary(
        overall_metrics=overall_metrics,
        ukrainian_report_df=ukrainian_report_df,
        english_report_df=english_report_df,
    )
    dashboard_summary = build_dashboard_summary(
        model_name=previous_meta.get("model_name", pipeline.named_steps["clf"].__class__.__name__),
        threshold=threshold,
        evaluation_summary=evaluation_summary,
    )

    previous_meta.update(
        {
            "threshold": float(threshold),
            "last_retrain": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_samples_trained": int(
                total_samples_trained if total_samples_trained is not None else train_size
            ),
            "train_size": int(train_size),
            "validation_size": int(validation_size),
            "test_size": int(test_size if test_size is not None else len(evaluation_df)),
            "evaluation_scope": evaluation_scope,
            "test_metrics": overall_metrics,
            "evaluation_summary": evaluation_summary,
            "dashboard_summary": dashboard_summary,
            "evaluation_reports": {
                "ukrainian_test": {
                    **dataframe_to_meta_payload(ukrainian_report_df),
                    "artifacts": {},
                },
                "english_test": {
                    **dataframe_to_meta_payload(english_report_df),
                    "artifacts": {},
                },
            },
        }
    )

    return previous_meta
