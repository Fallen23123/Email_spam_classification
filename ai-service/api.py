from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import sqlite3
import pandas as pd
import numpy as np
import os
import threading
from datetime import datetime

from config import DEFAULT_THRESHOLD, RETRAIN_THRESHOLD
from retrain_utils import load_feedback_rows_from_db, run_holdout_retrain

app = FastAPI()

# Конфігурація
DB_PATH = "data/feedback.db"
MODEL_PATH = "models/spam_pipeline.pkl"
META_PATH = "models/model_meta.pkl"

# Глобальні змінні для моделі
pipeline = joblib.load(MODEL_PATH)
meta = joblib.load(META_PATH)
MODEL_LOCK = threading.RLock()
RETRAIN_LOCK = threading.Lock()

class TextRequest(BaseModel):
    text: str

class LearnRequest(BaseModel):
    text: str
    is_spam_predicted: bool
    is_correct: bool

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (timestamp TEXT, text TEXT, actual_label TEXT, predicted_label TEXT, user_is_correct BOOLEAN)''')
    conn.commit()
    conn.close()

init_db()

def reload_model():
    """Оновлює модель у пам'яті сервера"""
    global pipeline, meta
    with MODEL_LOCK:
        pipeline = joblib.load(MODEL_PATH)
        meta = joblib.load(META_PATH)


def get_current_threshold():
    with MODEL_LOCK:
        return float(meta.get("threshold", DEFAULT_THRESHOLD))


def extract_spam_feature_weights(classifier):
    """Повертає ваги ознак для класу spam, якщо модель це підтримує."""
    if hasattr(classifier, "coef_"):
        return np.asarray(classifier.coef_[0]).ravel()

    calibrated = getattr(classifier, "calibrated_classifiers_", None)
    if calibrated:
        coefs = []
        for calibrated_clf in calibrated:
            estimator = getattr(calibrated_clf, "estimator", None)
            if estimator is not None and hasattr(estimator, "coef_"):
                coefs.append(np.asarray(estimator.coef_[0]).ravel())

        if coefs:
            return np.mean(np.vstack(coefs), axis=0)

    if hasattr(classifier, "feature_log_prob_") and len(classifier.feature_log_prob_) >= 2:
        return np.asarray(classifier.feature_log_prob_[1] - classifier.feature_log_prob_[0]).ravel()

    return None


def extract_keywords(text: str):
    """Знаходить слова/фрази, які найбільше тягнуть повідомлення в бік spam."""
    try:
        with MODEL_LOCK:
            preprocessor = pipeline.named_steps["prep"]
            classifier = pipeline.named_steps["clf"]

            weights = extract_spam_feature_weights(classifier)
            if weights is None:
                return []

            cleaned_text = preprocessor.clean_text(text)
            word_features = preprocessor.word_vectorizer_.transform([cleaned_text])
            feature_names = preprocessor.word_vectorizer_.get_feature_names_out()

            # У pipeline word-фічі йдуть першими, тому беремо тільки їхню частину ваг.
            word_feature_count = len(feature_names)
            word_weights = weights[:word_feature_count]

            important_words = []
            for idx, tfidf_value in zip(word_features.indices, word_features.data):
                contribution = float(word_weights[idx] * tfidf_value)
                if contribution > 0:
                    important_words.append(
                        {"word": feature_names[idx], "weight": contribution}
                    )

        important_words.sort(key=lambda item: item["weight"], reverse=True)

        keywords = []
        seen = set()
        for item in important_words:
            word = item["word"]
            if word in seen:
                continue
            seen.add(word)
            keywords.append(word)
            if len(keywords) == 7:
                break

        return keywords
    except Exception as exc:
        print(f"Keyword extraction error: {exc}")
        return []

def retrain_logic():
    """Перенавчає модель на всіх базових CSV та нових відгуках."""
    global pipeline, meta

    if not RETRAIN_LOCK.acquire(blocking=False):
        print("Retrain skipped: another retrain is already in progress.")
        return False

    try:
        feedback_rows = load_feedback_rows_from_db(DB_PATH)
        if feedback_rows.empty:
            return False

        with MODEL_LOCK:
            result = run_holdout_retrain(
                pipeline=pipeline,
                previous_meta=meta,
                db_path=DB_PATH,
                data_dir="data",
            )
            if result is None:
                return False
            pipeline = result["pipeline"]
            meta = result["meta"]
            
            # Зберігаємо на диск
            joblib.dump(pipeline, MODEL_PATH)
            joblib.dump(meta, META_PATH)
            
            # Перезавантажуємо в оперативну пам'ять
            pipeline = joblib.load(MODEL_PATH)
            meta = joblib.load(META_PATH)
        return True
    except Exception as e:
        print(f"Retrain Error: {e}")
        return False
    finally:
        RETRAIN_LOCK.release()

@app.post("/analyze")
def analyze_text(request: TextRequest):
    text = request.text
    threshold = get_current_threshold()
    
    # 1. Спершу перевіряємо "Гарячу пам'ять" (SQLite)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT actual_label FROM feedback WHERE text = ? ORDER BY timestamp DESC LIMIT 1", (text,))
    row = c.fetchone()
    conn.close()

    if row:
        # Якщо ти вже виправляв цей текст, повертаємо твій результат миттєво
        actual = row[0]
        score = 0.99 if actual == 'spam' else 0.01
        keywords = []
        print(f"Using hot memory for: {text[:30]}...")
    else:
        # 2. Якщо тексту немає в базі — питаємо ШІ
        with MODEL_LOCK:
            features = pipeline.named_steps["prep"].transform([text])
            score = float(pipeline.named_steps["clf"].predict_proba(features)[0][1])
        keywords = extract_keywords(text)

    is_spam_predicted = score >= threshold

    return {
        "spam_score": score,
        "base_threshold": threshold,
        "threshold_used": threshold,
        "is_spam_predicted": is_spam_predicted,
        "predicted_label": "spam" if is_spam_predicted else "ham",
        "keywords": keywords,
    }


@app.get("/model-meta")
def get_model_meta():
    with MODEL_LOCK:
        return {
            "model_name": meta.get("model_name"),
            "threshold": meta.get("threshold"),
            "last_retrain": meta.get("last_retrain"),
            "evaluation_scope": meta.get("evaluation_scope"),
            "feedback_training_size": meta.get("feedback_training_size", 0),
            "feedback_holdout_excluded": meta.get("feedback_holdout_excluded", 0),
            "test_metrics": meta.get("test_metrics", {}),
            "evaluation_summary": meta.get("evaluation_summary", {}),
            "dashboard_summary": meta.get("dashboard_summary", {}),
            "evaluation_reports": meta.get("evaluation_reports", {}),
        }

@app.post("/learn")
def learn_feedback(request: LearnRequest):
    # Визначаємо правильну мітку
    actual_is_spam = request.is_spam_predicted if request.is_correct else not request.is_spam_predicted
    label_str = "spam" if actual_is_spam else "ham"
    predicted_str = "spam" if request.is_spam_predicted else "ham"
    
    # Зберігаємо у базу
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO feedback VALUES (?, ?, ?, ?, ?)", 
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), request.text, label_str, predicted_str, request.is_correct))
    conn.commit()
    
    # Перевіряємо, чи пора перенавчатися
    c.execute("SELECT COUNT(*) FROM feedback")
    count = c.fetchone()[0]
    conn.close()
    
    if count > 0 and count % RETRAIN_THRESHOLD == 0:
        print("Starting automatic retraining...")
        retrain_logic()
        
    return {"status": "learned", "total_feedback": count}
