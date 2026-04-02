from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_DATA_DIR = Path("data")
DEFAULT_IGNORED_FILES = {"feedback_log.csv"}

LABEL_COLUMN_CANDIDATES = (
    "label",
    "v1",
    "category",
    "target",
    "class",
    "spam",
    "is_spam",
    "actual_label",
)

TEXT_COLUMN_CANDIDATES = (
    "text",
    "v2",
    "message",
    "body",
    "content",
    "mail",
    "email",
    "email_text",
    "message_text",
)

SUBJECT_COLUMN_CANDIDATES = (
    "subject",
    "title",
    "header",
)


def normalize_label(value):
    if pd.isna(value):
        return np.nan

    normalized = str(value).strip().lower()

    if normalized in {"spam", "1", "junk", "phishing", "yes", "true", "спам"}:
        return 1
    if normalized in {
        "ham",
        "0",
        "not spam",
        "not_spam",
        "legit",
        "legitimate",
        "no",
        "false",
        "не спам",
        "не_спам",
        "звичайний",
        "безпечний",
    }:
        return 0

    try:
        numeric = int(float(normalized))
    except (TypeError, ValueError):
        return np.nan

    return numeric if numeric in (0, 1) else np.nan


def normalize_column_name(column_name):
    return (
        str(column_name)
        .replace("\ufeff", "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def read_csv_safe(path):
    try:
        return pd.read_csv(
            path,
            encoding="utf-8",
            sep=None,
            engine="python",
            on_bad_lines="skip",
        )
    except UnicodeDecodeError:
        return pd.read_csv(
            path,
            encoding="latin-1",
            sep=None,
            engine="python",
            on_bad_lines="skip",
        )


def find_matching_column(columns, candidates):
    normalized_map = {
        normalize_column_name(column_name): column_name for column_name in columns
    }

    for candidate in candidates:
        if candidate in normalized_map:
            return normalized_map[candidate]

    return None


def normalize_text_series(series):
    return (
        series.fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def standardize_dataset_frame(df, source_name):
    label_column = find_matching_column(df.columns, LABEL_COLUMN_CANDIDATES)
    text_column = find_matching_column(df.columns, TEXT_COLUMN_CANDIDATES)
    subject_column = find_matching_column(df.columns, SUBJECT_COLUMN_CANDIDATES)

    if label_column is None:
        raise ValueError(
            f"Не знайдено колонку мітки. Доступні колонки: {list(df.columns)}"
        )

    if text_column is None and subject_column is None:
        raise ValueError(
            f"Не знайдено текстову колонку. Доступні колонки: {list(df.columns)}"
        )

    if text_column and subject_column and text_column != subject_column:
        subject_text = normalize_text_series(df[subject_column])
        body_text = normalize_text_series(df[text_column])
        text = (
            "subject " + subject_text + " body " + body_text
        ).str.strip()
    else:
        active_text_column = text_column or subject_column
        text = normalize_text_series(df[active_text_column])

    prepared = pd.DataFrame(
        {
            "label": df[label_column].map(normalize_label),
            "text": text,
            "source": source_name,
        }
    )

    prepared = prepared.dropna(subset=["label"])
    prepared = prepared[prepared["text"].str.len() >= 5].copy()
    prepared["label"] = prepared["label"].astype(int)

    return prepared.reset_index(drop=True)


def prepare_feedback_frame(df, label_column="label", text_column="text", source_name="user_feedback"):
    if df.empty:
        return pd.DataFrame(columns=["label", "text", "source"])

    if label_column not in df.columns or text_column not in df.columns:
        raise ValueError(
            f"Очікували колонки '{label_column}' та '{text_column}', отримано: {list(df.columns)}"
        )

    prepared = pd.DataFrame(
        {
            "label": df[label_column].map(normalize_label),
            "text": normalize_text_series(df[text_column]),
            "source": source_name,
        }
    )

    prepared = prepared.dropna(subset=["label"])
    prepared = prepared[prepared["text"].str.len() >= 5].copy()
    prepared["label"] = prepared["label"].astype(int)

    return prepared.reset_index(drop=True)


def discover_dataset_files(data_dir=DEFAULT_DATA_DIR, ignored_filenames=None):
    data_dir = Path(data_dir)
    ignored = {name.lower() for name in (ignored_filenames or DEFAULT_IGNORED_FILES)}

    return sorted(
        path for path in data_dir.glob("*.csv") if path.name.lower() not in ignored
    )


def load_training_corpora(data_dir=DEFAULT_DATA_DIR, ignored_filenames=None):
    dataset_files = discover_dataset_files(
        data_dir=data_dir,
        ignored_filenames=ignored_filenames,
    )

    if not dataset_files:
        raise FileNotFoundError("Не знайдено CSV-файлів у папці data/")

    frames = []

    for path in dataset_files:
        frame = standardize_dataset_frame(read_csv_safe(path), source_name=path.name)
        frames.append(frame)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["text"]).reset_index(drop=True)

    return combined


def combine_training_data(base_df, feedback_df=None, feedback_weight=1):
    frames = [base_df]

    if feedback_df is not None and not feedback_df.empty:
        frames.extend([feedback_df.copy()] * max(int(feedback_weight), 1))

    combined = pd.concat(frames, ignore_index=True)
    combined["text"] = normalize_text_series(combined["text"])
    combined = combined.dropna(subset=["label"])
    combined = combined[combined["text"].str.len() >= 5].reset_index(drop=True)
    combined["label"] = combined["label"].astype(int)

    return combined
