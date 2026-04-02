import os
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    roc_curve,
    precision_recall_curve,
)
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_validate
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from dataset_loader import (
    combine_training_data,
    discover_dataset_files,
    prepare_feedback_frame,
    read_csv_safe,
    standardize_dataset_frame,
)
from preprocessor import SpamPreprocessor


RANDOM_STATE = 42


def ensure_directories():
    os.makedirs("data", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    os.makedirs("reports", exist_ok=True)


def load_corpora():
    files = discover_dataset_files("data", ignored_filenames={"feedback_log.csv"})

    if not files:
        raise FileNotFoundError("Не знайдено CSV-файлів у папці data/")

    frames = []

    for path in files:
        try:
            frame = standardize_dataset_frame(read_csv_safe(path), source_name=path.name)
            print(f"[OK] {path}: {frame.shape[0]} рядків")
            frames.append(frame)
        except Exception as exc:
            print(f"[SKIP] {path}: {exc}")

    if not frames:
        raise ValueError("Не вдалося завантажити жоден набір даних.")

    data = pd.concat(frames, ignore_index=True)
    data = data.drop_duplicates(subset=["text"]).reset_index(drop=True)

    return data


def find_best_threshold(y_true, scores):
    precision, recall, thresholds = precision_recall_curve(y_true, scores)

    if len(thresholds) == 0:
        return 0.5

    f1_scores = 2 * precision[:-1] * recall[:-1] / (precision[:-1] + recall[:-1] + 1e-12)
    best_idx = int(np.argmax(f1_scores))
    return float(thresholds[best_idx])


def evaluate_scores(y_true, scores, threshold):
    pred = (scores >= threshold).astype(int)

    return {
        "accuracy": accuracy_score(y_true, pred),
        "precision": precision_score(y_true, pred, zero_division=0),
        "recall": recall_score(y_true, pred, zero_division=0),
        "f1": f1_score(y_true, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, scores),
        "pr_auc": average_precision_score(y_true, scores),
        "pred": pred,
    }


def evaluate_subset(subset_df, pipeline, threshold, segment_name):
    if subset_df.empty:
        return None

    y_true = subset_df["label"]
    scores = pipeline.predict_proba(subset_df["text"])[:, 1]
    pred = (scores >= threshold).astype(int)

    row = {
        "segment": segment_name,
        "support_total": int(len(subset_df)),
        "support_spam": int((y_true == 1).sum()),
        "support_ham": int((y_true == 0).sum()),
        "accuracy": float(accuracy_score(y_true, pred)),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "positive_rate_pred": float(pred.mean()),
    }

    if y_true.nunique() >= 2:
        row["roc_auc"] = float(roc_auc_score(y_true, scores))
        row["pr_auc"] = float(average_precision_score(y_true, scores))
    else:
        row["roc_auc"] = np.nan
        row["pr_auc"] = np.nan

    return row


def build_segment_evaluation_report(
    subset_df,
    pipeline,
    threshold,
    report_prefix,
    spam_subset_df,
    ham_subset_df,
):
    if subset_df.empty:
        return pd.DataFrame()

    report_rows = []
    aggregate_segments = [
        (
            f"{report_prefix}_all_sources_test",
            subset_df,
        ),
        (
            f"{report_prefix}_spam_sources_test",
            spam_subset_df,
        ),
        (
            f"{report_prefix}_ham_sources_test",
            ham_subset_df,
        ),
    ]

    for segment_name, segment_df in aggregate_segments:
        row = evaluate_subset(segment_df, pipeline, threshold, segment_name)
        if row is not None:
            report_rows.append(row)

    for source_name, source_df in subset_df.groupby("source"):
        row = evaluate_subset(source_df, pipeline, threshold, source_name)
        if row is not None:
            report_rows.append(row)

    report_df = pd.DataFrame(report_rows)
    preferred_order = {
        f"{report_prefix}_all_sources_test": 0,
        f"{report_prefix}_spam_sources_test": 1,
        f"{report_prefix}_ham_sources_test": 2,
    }
    report_df["sort_key"] = report_df["segment"].map(preferred_order).fillna(100)
    report_df = report_df.sort_values(["sort_key", "segment"]).drop(columns=["sort_key"])

    return report_df.reset_index(drop=True)


def build_ukrainian_evaluation_report(test_df, pipeline, threshold):
    ukrainian_mask = test_df["source"].str.startswith("ukrainian_", na=False)
    ukrainian_df = test_df[ukrainian_mask].copy()

    return build_segment_evaluation_report(
        subset_df=ukrainian_df,
        pipeline=pipeline,
        threshold=threshold,
        report_prefix="ukrainian",
        spam_subset_df=ukrainian_df[
            ukrainian_df["source"].str.startswith("ukrainian_spam", na=False)
        ],
        ham_subset_df=ukrainian_df[
            ukrainian_df["source"].str.startswith("ukrainian_ham", na=False)
        ],
    )


def build_english_evaluation_report(test_df, pipeline, threshold):
    english_df = test_df[test_df["source"].isin(["spam.csv"])].copy()

    return build_segment_evaluation_report(
        subset_df=english_df,
        pipeline=pipeline,
        threshold=threshold,
        report_prefix="english",
        spam_subset_df=english_df[english_df["label"] == 1],
        ham_subset_df=english_df[english_df["label"] == 0],
    )


def save_html_metrics_report(report_df, title, output_path, image_paths=None):
    image_paths = image_paths or []

    rows_html = []
    for _, row in report_df.iterrows():
        cells = []
        for value in row.tolist():
            if pd.isna(value):
                display = ""
            elif isinstance(value, (float, np.floating)):
                display = f"{value:.6f}"
            else:
                display = str(value)
            cells.append(f"<td>{display}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    header_html = "".join(f"<th>{column}</th>" for column in report_df.columns)
    images_html = "".join(
        f"""
        <section class="card">
            <h2>{image_title}</h2>
            <img src="{image_file}" alt="{image_title}">
        </section>
        """
        for image_title, image_file in image_paths
    )

    html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 24px;
            color: #1f2937;
            background: #f8fafc;
        }}
        h1, h2 {{
            margin-bottom: 12px;
        }}
        .card {{
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th, td {{
            border: 1px solid #d1d5db;
            padding: 8px 10px;
            text-align: left;
        }}
        th {{
            background: #eef2ff;
        }}
        img {{
            max-width: 100%;
            height: auto;
            border-radius: 10px;
            border: 1px solid #d1d5db;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <section class="card">
        <h2>Метрики</h2>
        <table>
            <thead>
                <tr>{header_html}</tr>
            </thead>
            <tbody>
                {''.join(rows_html)}
            </tbody>
        </table>
    </section>
    {images_html}
</body>
</html>
"""

    Path(output_path).write_text(html, encoding="utf-8")


def dataframe_to_meta_payload(report_df):
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


def build_compact_summary(test_metrics, ukrainian_eval_df, english_eval_df):
    summary = {
        "test_accuracy": float(test_metrics["accuracy"]),
        "test_precision": float(test_metrics["precision"]),
        "test_recall": float(test_metrics["recall"]),
        "test_f1": float(test_metrics["f1"]),
        "test_roc_auc": float(test_metrics["roc_auc"]),
        "test_pr_auc": float(test_metrics["pr_auc"]),
    }

    def add_segment_metrics(prefix, report_df, segment_name):
        if report_df.empty:
            return

        match = report_df[report_df["segment"] == segment_name]
        if match.empty:
            return

        row = match.iloc[0].replace({np.nan: None}).to_dict()
        metric_map = {
            "accuracy": "accuracy",
            "precision": "precision",
            "recall": "recall",
            "f1": "f1",
            "support_total": "support_total",
            "support_spam": "support_spam",
            "support_ham": "support_ham",
            "roc_auc": "roc_auc",
            "pr_auc": "pr_auc",
        }

        for source_key, target_key in metric_map.items():
            value = row.get(source_key)
            if value is None:
                continue
            if isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, np.floating):
                value = float(value)
            summary[f"{prefix}_{target_key}"] = value

    add_segment_metrics("ua", ukrainian_eval_df, "ukrainian_spam_sources_test")
    add_segment_metrics("en", english_eval_df, "english_spam_sources_test")

    return summary


def build_dashboard_summary(model_name, threshold, evaluation_summary):
    def pct(value):
        if value is None:
            return None
        return round(float(value) * 100, 2)

    dashboard = {
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

    return dashboard


def save_confusion_matrix(y_true, y_pred, title, filename):
    cm = confusion_matrix(y_true, y_pred)

    plt.figure(figsize=(5, 4))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["Ham", "Spam"],
        yticklabels=["Ham", "Spam"],
    )
    plt.title(title)
    plt.ylabel("Фактичний клас")
    plt.xlabel("Передбачений клас")
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.close()


def save_roc_curve(y_true, scores, filename):
    fpr, tpr, _ = roc_curve(y_true, scores)
    auc_value = roc_auc_score(y_true, scores)

    plt.figure(figsize=(6, 4))
    plt.plot(fpr, tpr, label=f"ROC-AUC = {auc_value:.4f}")
    plt.plot([0, 1], [0, 1], linestyle="--")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("ROC-крива")
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.close()


def save_pr_curve(y_true, scores, filename):
    precision, recall, _ = precision_recall_curve(y_true, scores)
    ap_value = average_precision_score(y_true, scores)

    plt.figure(figsize=(6, 4))
    plt.plot(recall, precision, label=f"PR-AUC = {ap_value:.4f}")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall крива")
    plt.legend(loc="lower left")
    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.close()


def main():
    ensure_directories()

    print("1. Завантаження корпусів...")
    df = load_corpora()

    # =====================================================================
    # НОВИЙ БЛОК: Інтеграція відгуків користувачів (Active Learning)
    # =====================================================================
    feedback_file = "data/feedback_log.csv"
    if os.path.exists(feedback_file):
        print("\n[INFO] Знайдено файл з відгуками користувачів. Інтеграція нових знань...")
        try:
            feedback_raw = read_csv_safe(feedback_file)
            feedback_df = prepare_feedback_frame(
                feedback_raw,
                label_column="actual_label",
                text_column="text",
                source_name="user_feedback",
            )

            if not feedback_df.empty:
                weight_multiplier = 3
                df = combine_training_data(
                    df,
                    feedback_df=feedback_df,
                    feedback_weight=weight_multiplier,
                )
                print(f"[OK] Успішно додано {len(feedback_df)} унікальних виправлень.")
                print(f"[INFO] Вагу виправлень збільшено у {weight_multiplier} рази для кращого засвоєння.\n")
        except Exception as e:
            print(f"[WARN] Не вдалося обробити файл відгуків: {e}")
    # =====================================================================

    print(f"Загальний розмір вибірки: {df.shape[0]}")
    print("Розподіл класів:")
    print(df["label"].value_counts(normalize=True))

    train_val_df, test_df = train_test_split(
        df,
        test_size=0.15,
        random_state=RANDOM_STATE,
        stratify=df["label"],
    )

    train_df, val_df = train_test_split(
        train_val_df,
        test_size=0.1765,
        random_state=RANDOM_STATE,
        stratify=train_val_df["label"],
    )

    X_train, y_train = train_df["text"], train_df["label"]
    X_val, y_val = val_df["text"], val_df["label"]
    X_test, y_test = test_df["text"], test_df["label"]

    print(f"Train: {len(X_train)} | Validation: {len(X_val)} | Test: {len(X_test)}")

    models = {
        "ComplementNB": ComplementNB(alpha=0.6),
        "LogisticRegression": LogisticRegression(
            max_iter=4000,
            class_weight="balanced",
            solver="liblinear",
            random_state=RANDOM_STATE,
        ),
        "LinearSVM_Calibrated": CalibratedClassifierCV(
            LinearSVC(class_weight="balanced", random_state=RANDOM_STATE),
            method="sigmoid",
            cv=3,
        ),
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    scoring = {
        "precision": "precision",
        "recall": "recall",
        "f1": "f1",
        "roc_auc": "roc_auc",
    }

    results = []
    trained = {}

    print("\n2. Навчання та оцінювання моделей...")

    for name, classifier_template in models.items():
        print(f"\n>>> {name}")

        pipeline = Pipeline(
            [
                ("prep", SpamPreprocessor()),
                ("clf", clone(classifier_template)),
            ]
        )

        cv_scores = cross_validate(
            pipeline,
            X_train,
            y_train,
            cv=cv,
            scoring=scoring,
            n_jobs=1,
        )

        pipeline.fit(X_train, y_train)

        val_scores = pipeline.predict_proba(X_val)[:, 1]
        threshold = find_best_threshold(y_val, val_scores)
        val_metrics = evaluate_scores(y_val, val_scores, threshold)

        row = {
            "model": name,
            "threshold": threshold,
            "cv_precision_mean": cv_scores["test_precision"].mean(),
            "cv_recall_mean": cv_scores["test_recall"].mean(),
            "cv_f1_mean": cv_scores["test_f1"].mean(),
            "cv_roc_auc_mean": cv_scores["test_roc_auc"].mean(),
            "val_accuracy": val_metrics["accuracy"],
            "val_precision": val_metrics["precision"],
            "val_recall": val_metrics["recall"],
            "val_f1": val_metrics["f1"],
            "val_roc_auc": val_metrics["roc_auc"],
            "val_pr_auc": val_metrics["pr_auc"],
        }

        results.append(row)

        trained[name] = {
            "pipeline": pipeline,
            "threshold": threshold,
            "val_metrics": val_metrics,
        }

        print(f"CV F1: {row['cv_f1_mean']:.4f}")
        print(f"Validation F1: {row['val_f1']:.4f}")
        print(f"Validation Recall: {row['val_recall']:.4f}")
        print(f"Threshold: {threshold:.4f}")

    results_df = pd.DataFrame(results).sort_values(
        by=["val_f1", "val_recall", "cv_f1_mean", "cv_roc_auc_mean"],
        ascending=False,
    ).reset_index(drop=True)

    print("\n3. Порівняння моделей:")
    print(results_df)

    results_df.to_csv("reports/model_comparison.csv", index=False)

    best_name = results_df.loc[0, "model"]
    best_threshold = float(results_df.loc[0, "threshold"])
    best_pipeline = trained[best_name]["pipeline"]

    print(f"\n4. Найкраща модель: {best_name}")
    print(f"Оптимальний поріг: {best_threshold:.4f}")

    test_scores = best_pipeline.predict_proba(X_test)[:, 1]
    test_metrics = evaluate_scores(y_test, test_scores, best_threshold)

    print("\n5. Результати на тестовій вибірці:")
    print(f"Accuracy:  {test_metrics['accuracy']:.4f}")
    print(f"Precision: {test_metrics['precision']:.4f}")
    print(f"Recall:    {test_metrics['recall']:.4f}")
    print(f"F1-score:  {test_metrics['f1']:.4f}")
    print(f"ROC-AUC:   {test_metrics['roc_auc']:.4f}")
    print(f"PR-AUC:    {test_metrics['pr_auc']:.4f}")

    save_confusion_matrix(
        y_test,
        test_metrics["pred"],
        f"Матриця помилок - {best_name}",
        "reports/cm_best_model.png",
    )
    save_roc_curve(y_test, test_scores, "reports/roc_best_model.png")
    save_pr_curve(y_test, test_scores, "reports/pr_best_model.png")

    ukrainian_eval_df = build_ukrainian_evaluation_report(
        test_df=test_df,
        pipeline=best_pipeline,
        threshold=best_threshold,
    )
    english_eval_df = build_english_evaluation_report(
        test_df=test_df,
        pipeline=best_pipeline,
        threshold=best_threshold,
    )
    evaluation_reports_meta = {}
    if not ukrainian_eval_df.empty:
        ukrainian_test_df = test_df[test_df["source"].str.startswith("ukrainian_", na=False)].copy()
        ukrainian_scores = best_pipeline.predict_proba(ukrainian_test_df["text"])[:, 1]
        ukrainian_pred = (ukrainian_scores >= best_threshold).astype(int)

        ukrainian_eval_df.to_csv("reports/ukrainian_evaluation.csv", index=False)
        save_confusion_matrix(
            ukrainian_test_df["label"],
            ukrainian_pred,
            "Матриця помилок - Україномовний test subset",
            "reports/cm_ukrainian_test.png",
        )
        if ukrainian_test_df["label"].nunique() >= 2:
            save_roc_curve(
                ukrainian_test_df["label"],
                ukrainian_scores,
                "reports/roc_ukrainian_test.png",
            )
            save_pr_curve(
                ukrainian_test_df["label"],
                ukrainian_scores,
                "reports/pr_ukrainian_test.png",
            )
        save_html_metrics_report(
            ukrainian_eval_df,
            title="Україномовна оцінка моделі",
            output_path="reports/ukrainian_evaluation.html",
            image_paths=[
                (
                    "Confusion Matrix для українського test subset",
                    "cm_ukrainian_test.png",
                ),
                (
                    "ROC Curve для українського test subset",
                    "roc_ukrainian_test.png",
                ),
                (
                    "Precision-Recall Curve для українського test subset",
                    "pr_ukrainian_test.png",
                ),
            ],
        )
        evaluation_reports_meta["ukrainian_test"] = {
            **dataframe_to_meta_payload(ukrainian_eval_df),
            "artifacts": {
                "csv": "reports/ukrainian_evaluation.csv",
                "html": "reports/ukrainian_evaluation.html",
                "confusion_matrix": "reports/cm_ukrainian_test.png",
                "roc_curve": "reports/roc_ukrainian_test.png",
                "pr_curve": "reports/pr_ukrainian_test.png",
            },
        }
        print("\n5a. Україномовна оцінка на тестовій вибірці:")
        print(ukrainian_eval_df)

    if not english_eval_df.empty:
        english_test_df = test_df[test_df["source"].isin(["spam.csv"])].copy()
        english_scores = best_pipeline.predict_proba(english_test_df["text"])[:, 1]
        english_pred = (english_scores >= best_threshold).astype(int)

        english_eval_df.to_csv("reports/english_evaluation.csv", index=False)
        save_confusion_matrix(
            english_test_df["label"],
            english_pred,
            "Матриця помилок - Англомовний test subset",
            "reports/cm_english_test.png",
        )
        if english_test_df["label"].nunique() >= 2:
            save_roc_curve(
                english_test_df["label"],
                english_scores,
                "reports/roc_english_test.png",
            )
            save_pr_curve(
                english_test_df["label"],
                english_scores,
                "reports/pr_english_test.png",
            )
        save_html_metrics_report(
            english_eval_df,
            title="Англомовна оцінка моделі",
            output_path="reports/english_evaluation.html",
            image_paths=[
                (
                    "Confusion Matrix для англомовного test subset",
                    "cm_english_test.png",
                ),
                (
                    "ROC Curve для англомовного test subset",
                    "roc_english_test.png",
                ),
                (
                    "Precision-Recall Curve для англомовного test subset",
                    "pr_english_test.png",
                ),
            ],
        )
        evaluation_reports_meta["english_test"] = {
            **dataframe_to_meta_payload(english_eval_df),
            "artifacts": {
                "csv": "reports/english_evaluation.csv",
                "html": "reports/english_evaluation.html",
                "confusion_matrix": "reports/cm_english_test.png",
                "roc_curve": "reports/roc_english_test.png",
                "pr_curve": "reports/pr_english_test.png",
            },
        }
        print("\n5b. Англомовна оцінка на тестовій вибірці:")
        print(english_eval_df)

    compact_summary = build_compact_summary(
        test_metrics=test_metrics,
        ukrainian_eval_df=ukrainian_eval_df,
        english_eval_df=english_eval_df,
    )
    dashboard_summary = build_dashboard_summary(
        model_name=best_name,
        threshold=best_threshold,
        evaluation_summary=compact_summary,
    )

    print("\n6. Навчання фінальної pipeline на train+validation...")
    X_full_train = pd.concat([X_train, X_val], axis=0)
    y_full_train = pd.concat([y_train, y_val], axis=0)

    final_pipeline = Pipeline(
        [
            ("prep", SpamPreprocessor()),
            ("clf", clone(models[best_name])),
        ]
    )

    final_pipeline.fit(X_full_train, y_full_train)

    joblib.dump(final_pipeline, "models/spam_pipeline.pkl")
    joblib.dump(
        {
            "model_name": best_name,
            "threshold": best_threshold,
            "train_size": int(len(X_train)),
            "validation_size": int(len(X_val)),
            "test_size": int(len(X_test)),
            "evaluation_scope": "full_offline_eval",
            "test_metrics": {
                "accuracy": float(test_metrics["accuracy"]),
                "precision": float(test_metrics["precision"]),
                "recall": float(test_metrics["recall"]),
                "f1": float(test_metrics["f1"]),
                "roc_auc": float(test_metrics["roc_auc"]),
                "pr_auc": float(test_metrics["pr_auc"]),
            },
            "evaluation_summary": compact_summary,
            "dashboard_summary": dashboard_summary,
            "evaluation_reports": evaluation_reports_meta,
        },
        "models/model_meta.pkl",
    )

    print("\nГотово. Збережено:")
    print("- models/spam_pipeline.pkl")
    print("- models/model_meta.pkl")
    print("- reports/model_comparison.csv")
    if not ukrainian_eval_df.empty:
        print("- reports/ukrainian_evaluation.csv")
        print("- reports/ukrainian_evaluation.html")
        print("- reports/cm_ukrainian_test.png")
        if test_df[test_df["source"].str.startswith("ukrainian_", na=False)]["label"].nunique() >= 2:
            print("- reports/roc_ukrainian_test.png")
            print("- reports/pr_ukrainian_test.png")
    if not english_eval_df.empty:
        print("- reports/english_evaluation.csv")
        print("- reports/english_evaluation.html")
        print("- reports/cm_english_test.png")
        if test_df[test_df["source"].isin(["spam.csv"])]["label"].nunique() >= 2:
            print("- reports/roc_english_test.png")
            print("- reports/pr_english_test.png")
    print("- reports/cm_best_model.png")
    print("- reports/roc_best_model.png")
    print("- reports/pr_best_model.png")

if __name__ == "__main__":
    main()
