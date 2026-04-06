from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import sqlite3
import pandas as pd
import numpy as np
import os
import threading
import time
import hashlib
from collections import OrderedDict
from datetime import datetime
from typing import Optional
from scipy.sparse import hstack

from config import DEFAULT_THRESHOLD, MIN_DECISION_THRESHOLD, RETRAIN_THRESHOLD
from preprocessor import FREE_MAIL_DOMAINS
from retrain_utils import load_feedback_rows_from_db, run_holdout_retrain
from safe_mail_rules import detect_lookalike_domain_rule, detect_safe_business_rule

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
RETRAIN_STATE_LOCK = threading.Lock()
ANALYSIS_CACHE_LOCK = threading.Lock()
ANALYSIS_CACHE = OrderedDict()
ANALYSIS_CACHE_MAX_SIZE = 512
ANALYSIS_CACHE_TTL_SECONDS = 15 * 60
EXPLAINABILITY_MARGIN = 0.12
RETRAIN_STATE = {
    "in_progress": False,
    "started_at": None,
    "last_finished_at": None,
    "last_status": "idle",
    "last_error": None,
}

class TextRequest(BaseModel):
    text: str
    include_explainability: bool = False
    sender: Optional[str] = None
    sender_domain: Optional[str] = None

class LearnRequest(BaseModel):
    text: str
    is_spam_predicted: bool
    is_correct: bool
    sender: Optional[str] = None
    sender_domain: Optional[str] = None

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
        return resolve_decision_threshold(meta.get("threshold", DEFAULT_THRESHOLD))


def get_model_snapshot():
    with MODEL_LOCK:
        return pipeline, dict(meta)


def update_retrain_state(**updates):
    with RETRAIN_STATE_LOCK:
        RETRAIN_STATE.update(updates)


def get_retrain_state_snapshot():
    with RETRAIN_STATE_LOCK:
        return dict(RETRAIN_STATE)


def clear_analysis_cache():
    with ANALYSIS_CACHE_LOCK:
        ANALYSIS_CACHE.clear()


def build_analysis_cache_key(text, include_explainability):
    digest = hashlib.sha256(str(text).encode("utf-8")).hexdigest()
    return f"{digest}:{int(bool(include_explainability))}"


def get_cached_analysis(cache_key):
    now = time.time()
    with ANALYSIS_CACHE_LOCK:
        cached_entry = ANALYSIS_CACHE.get(cache_key)
        if cached_entry is None:
            return None

        if now - cached_entry["created_at"] > ANALYSIS_CACHE_TTL_SECONDS:
            ANALYSIS_CACHE.pop(cache_key, None)
            return None

        ANALYSIS_CACHE.move_to_end(cache_key)
        return dict(cached_entry["result"])


def set_cached_analysis(cache_key, result):
    cacheable_result = dict(result)
    cacheable_result.pop("cache_hit", None)

    with ANALYSIS_CACHE_LOCK:
        ANALYSIS_CACHE[cache_key] = {
            "created_at": time.time(),
            "result": cacheable_result,
        }
        ANALYSIS_CACHE.move_to_end(cache_key)

        while len(ANALYSIS_CACHE) > ANALYSIS_CACHE_MAX_SIZE:
            ANALYSIS_CACHE.popitem(last=False)


def merge_runtime_status(result):
    merged = dict(result)
    retrain_state = get_retrain_state_snapshot()
    merged.update(
        {
            "retrain_in_progress": retrain_state["in_progress"],
            "retrain_started_at": retrain_state["started_at"],
            "retrain_last_finished_at": retrain_state["last_finished_at"],
            "retrain_last_status": retrain_state["last_status"],
            "retrain_last_error": retrain_state["last_error"],
        }
    )
    return merged


def elapsed_ms(start_time):
    return round((time.perf_counter() - start_time) * 1000, 3)


def resolve_decision_threshold(raw_threshold):
    return max(float(raw_threshold), float(MIN_DECISION_THRESHOLD))


def compose_analysis_text(text, sender=None, sender_domain=None):
    metadata_lines = []
    if sender:
        metadata_lines.append(f"X-Sender: {str(sender).strip()}")
    if sender_domain:
        metadata_lines.append(f"X-Sender-Domain: {str(sender_domain).strip()}")

    base_text = str(text or "").strip()
    if not metadata_lines:
        return base_text

    return "\n".join(metadata_lines + [base_text]).strip()


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


def _extract_top_terms_by_polarity_from_features(
    word_features,
    feature_names,
    word_weights,
    limit=5,
    polarity="positive",
):
    important_words = []
    for idx, tfidf_value in zip(word_features.indices, word_features.data):
        contribution = float(word_weights[idx] * tfidf_value)
        if polarity == "positive" and contribution > 0:
            important_words.append(
                {"word": feature_names[idx], "weight": contribution}
            )
        elif polarity == "negative" and contribution < 0:
            important_words.append(
                {"word": feature_names[idx], "weight": abs(contribution)}
            )

    important_words.sort(key=lambda item: item["weight"], reverse=True)

    terms = []
    seen = set()
    for item in important_words:
        word = item["word"]
        if word in seen:
            continue
        seen.add(word)
        terms.append(word)
        if len(terms) == limit:
            break

    return terms


def extract_keywords_from_features(word_features, feature_names, word_weights, limit=7):
    return _extract_top_terms_by_polarity_from_features(
        word_features=word_features,
        feature_names=feature_names,
        word_weights=word_weights,
        limit=limit,
        polarity="positive",
    )


def should_include_explainability(score, threshold, decision_source="model", force=False):
    if force:
        return True, "requested"

    if decision_source != "model":
        return False, f"deferred_{decision_source}"

    if score >= threshold:
        return True, "spam_prediction"

    if abs(score - threshold) <= EXPLAINABILITY_MARGIN:
        return True, "near_threshold"

    return False, "deferred_low_risk_ham"


def build_explainability_payload(
    preprocessor,
    classifier,
    text,
    cleaned_text=None,
    word_features=None,
):
    """Будує keywords та subject/body explainability з мінімумом зайвих трансформацій."""
    try:
        weights = extract_spam_feature_weights(classifier)
        if weights is None:
            return {
                "keywords": [],
                "subject_signals": [],
                "body_signals": [],
                "subject_safe_signals": [],
                "body_safe_signals": [],
                "metadata_signals": [],
            }

        feature_names = preprocessor.word_vectorizer_.get_feature_names_out()
        word_weights = weights[: len(feature_names)]
        cleaned_text = cleaned_text if cleaned_text is not None else preprocessor.clean_text(text)
        word_features = (
            word_features
            if word_features is not None
            else preprocessor.word_vectorizer_.transform([cleaned_text])
        )
        subject_text, body_text, _ = preprocessor.split_subject_body_sections(text)

        keywords = extract_keywords_from_features(
            word_features=word_features,
            feature_names=feature_names,
            word_weights=word_weights,
            limit=7,
        )
        subject_signals = []
        body_signals = []
        subject_safe_signals = []
        body_safe_signals = []

        if subject_text.strip():
            subject_features = preprocessor.word_vectorizer_.transform(
                [preprocessor.clean_text(subject_text)]
            )
            subject_signals = _extract_top_terms_by_polarity_from_features(
                subject_features,
                feature_names,
                word_weights,
                polarity="positive",
            )
            subject_safe_signals = _extract_top_terms_by_polarity_from_features(
                subject_features,
                feature_names,
                word_weights,
                polarity="negative",
            )

        if body_text.strip():
            body_features = preprocessor.word_vectorizer_.transform(
                [preprocessor.clean_text(body_text)]
            )
            body_signals = _extract_top_terms_by_polarity_from_features(
                body_features,
                feature_names,
                word_weights,
                polarity="positive",
            )
            body_safe_signals = _extract_top_terms_by_polarity_from_features(
                body_features,
                feature_names,
                word_weights,
                polarity="negative",
            )

        return {
            "keywords": keywords,
            "subject_signals": subject_signals,
            "body_signals": body_signals,
            "subject_safe_signals": subject_safe_signals,
            "body_safe_signals": body_safe_signals,
            "metadata_signals": [],
        }
    except Exception as exc:
        print(f"Subject/body signal extraction error: {exc}")
        return {
            "keywords": [],
            "subject_signals": [],
            "body_signals": [],
            "subject_safe_signals": [],
            "body_safe_signals": [],
            "metadata_signals": [],
        }


def extract_keywords(text: str):
    """Сумісний wrapper для отримання spam-keywords."""
    try:
        pipeline_snapshot, _ = get_model_snapshot()
        preprocessor = pipeline_snapshot.named_steps["prep"]
        classifier = pipeline_snapshot.named_steps["clf"]
        payload = build_explainability_payload(preprocessor, classifier, text)
        return payload["keywords"]
    except Exception as exc:
        print(f"Keyword extraction error: {exc}")
        return []


def extract_subject_body_signals(text: str):
    """Сумісний wrapper для subject/body explainability."""
    try:
        pipeline_snapshot, _ = get_model_snapshot()
        preprocessor = pipeline_snapshot.named_steps["prep"]
        classifier = pipeline_snapshot.named_steps["clf"]
        payload = build_explainability_payload(preprocessor, classifier, text)
        return {
            "subject_signals": payload["subject_signals"],
            "body_signals": payload["body_signals"],
            "subject_safe_signals": payload["subject_safe_signals"],
            "body_safe_signals": payload["body_safe_signals"],
        }
    except Exception as exc:
        print(f"Subject/body signal extraction error: {exc}")
        return {
            "subject_signals": [],
            "body_signals": [],
            "subject_safe_signals": [],
            "body_safe_signals": [],
        }


def extract_metadata_signals(text: str):
    """Пояснює URL/domain/sender-ризики окремо від текстових keywords."""
    try:
        phishing_rule_result = detect_lookalike_domain_rule(text)
        if phishing_rule_result:
            return phishing_rule_result.get("matched_signals", [])[:6]

        pipeline_snapshot, _ = get_model_snapshot()
        preprocessor = pipeline_snapshot.named_steps["prep"]
        sender_metadata = preprocessor.extract_sender_metadata(text)
        content_text = preprocessor.strip_metadata_headers(text)
        url_domains = preprocessor.extract_url_domains(content_text)

        signals = []
        sender_domain = sender_metadata["sender_domain"]
        if sender_domain:
            signals.append(f"sender domain: {sender_domain}")
            if sender_domain in FREE_MAIL_DOMAINS:
                signals.append("sender uses free-mail domain")

        unique_url_domains = list(dict.fromkeys(url_domains))
        if unique_url_domains:
            signals.append(f"url domains: {', '.join(unique_url_domains[:3])}")

        if sender_domain and unique_url_domains and sender_domain not in set(unique_url_domains):
            signals.append("sender domain differs from linked domain")

        if any(preprocessor.is_shortener_domain(domain) for domain in unique_url_domains):
            signals.append("contains shortened URL")

        if any(preprocessor.is_ip_host(domain) for domain in unique_url_domains):
            signals.append("contains IP-based URL")

        if any("xn--" in domain for domain in unique_url_domains):
            signals.append("contains punycode domain")

        if any(preprocessor.has_suspicious_tld(domain) for domain in unique_url_domains):
            signals.append("contains suspicious domain TLD")

        if sender_domain and preprocessor.has_suspicious_tld(sender_domain):
            signals.append("sender domain has suspicious TLD")

        return signals[:6]
    except Exception as exc:
        print(f"Metadata signal extraction error: {exc}")
        return []


def run_model_inference(text, threshold, include_explainability=False):
    model_started_at = time.perf_counter()
    pipeline_snapshot, _ = get_model_snapshot()
    preprocessor = pipeline_snapshot.named_steps["prep"]
    classifier = pipeline_snapshot.named_steps["clf"]

    feature_parts = preprocessor.build_feature_parts([text])
    features = hstack(
        [
            part
            for part in (
                feature_parts["x_word"],
                feature_parts["x_char_wb"],
                feature_parts["x_char_dense"],
                feature_parts["x_structural"],
            )
            if part is not None
        ]
    ).tocsr()
    score = float(classifier.predict_proba(features)[0][1])
    model_inference_ms = elapsed_ms(model_started_at)

    include_details, explainability_reason = should_include_explainability(
        score=score,
        threshold=threshold,
        decision_source="model",
        force=include_explainability,
    )

    explainability_payload = {
        "keywords": [],
        "subject_signals": [],
        "body_signals": [],
        "subject_safe_signals": [],
        "body_safe_signals": [],
        "metadata_signals": [],
    }
    explainability_ms = 0.0
    if include_details:
        explainability_started_at = time.perf_counter()
        explainability_payload = build_explainability_payload(
            preprocessor=preprocessor,
            classifier=classifier,
            text=text,
            cleaned_text=feature_parts["cleaned"][0],
            word_features=feature_parts["x_word"],
        )
        explainability_payload["metadata_signals"] = extract_metadata_signals(text)
        explainability_ms = elapsed_ms(explainability_started_at)

    return {
        "score": score,
        "decision_source": "model",
        "rule_name": None,
        "rule_label": None,
        "rule_matches": [],
        "reason": None,
        "matched_signals": [],
        "explainability_included": include_details,
        "explainability_reason": explainability_reason,
        "timings_ms": {
            "model_inference_ms": model_inference_ms,
            "explainability_ms": explainability_ms,
        },
        **explainability_payload,
    }

def retrain_logic():
    """Перенавчає модель на всіх базових CSV та нових відгуках."""
    global pipeline, meta

    if not RETRAIN_LOCK.acquire(blocking=False):
        print("Retrain skipped: another retrain is already in progress.")
        return False

    try:
        update_retrain_state(
            in_progress=True,
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_status="running",
            last_error=None,
        )
        feedback_rows = load_feedback_rows_from_db(DB_PATH)
        if feedback_rows.empty:
            update_retrain_state(
                in_progress=False,
                last_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                last_status="skipped_no_feedback",
            )
            return False

        # Тренуємо окрему копію моделі поза MODEL_LOCK, щоб /analyze не блокувався.
        with MODEL_LOCK:
            current_meta = dict(meta)

        training_pipeline = joblib.load(MODEL_PATH)
        result = run_holdout_retrain(
            pipeline=training_pipeline,
            previous_meta=current_meta,
            db_path=DB_PATH,
            data_dir="data",
        )
        if result is None:
            return False

        trained_pipeline = result["pipeline"]
        trained_meta = result["meta"]

        joblib.dump(trained_pipeline, MODEL_PATH)
        joblib.dump(trained_meta, META_PATH)

        # Швидко підміняємо модель у пам'яті вже після завершення retrain.
        with MODEL_LOCK:
            pipeline = trained_pipeline
            meta = trained_meta
        clear_analysis_cache()
        update_retrain_state(
            in_progress=False,
            last_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_status="success",
            last_error=None,
        )
        return True
    except Exception as e:
        print(f"Retrain Error: {e}")
        update_retrain_state(
            in_progress=False,
            last_finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_status="error",
            last_error=str(e),
        )
        return False
    finally:
        RETRAIN_LOCK.release()


def start_retrain_in_background():
    """Запускає retrain у фоні, не блокуючи HTTP-відповідь."""
    if RETRAIN_LOCK.locked():
        print("Retrain already running, background start skipped.")
        return False

    update_retrain_state(
        in_progress=True,
        started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_status="scheduled",
        last_error=None,
    )

    retrain_thread = threading.Thread(
        target=retrain_logic,
        name="auto-retrain",
        daemon=True,
    )
    retrain_thread.start()
    return True

@app.post("/analyze")
def analyze_text(request: TextRequest):
    request_started_at = time.perf_counter()
    raw_text = request.text
    text = compose_analysis_text(
        text=raw_text,
        sender=request.sender,
        sender_domain=request.sender_domain,
    )
    include_explainability = bool(request.include_explainability)
    threshold = get_current_threshold()
    cache_key = build_analysis_cache_key(text, include_explainability)
    cache_lookup_started_at = time.perf_counter()
    cached_result = get_cached_analysis(cache_key)
    cache_lookup_ms = elapsed_ms(cache_lookup_started_at)
    if cached_result is not None:
        cached_timings = dict(cached_result.get("timings_ms", {}))
        cached_timings["cache_lookup_ms"] = cache_lookup_ms
        cached_timings["total_ms"] = elapsed_ms(request_started_at)
        cached_result["timings_ms"] = cached_timings
        cached_result["cache_hit"] = True
        return merge_runtime_status(cached_result)
    
    # 1. Спершу перевіряємо "Гарячу пам'ять" (SQLite)
    hot_memory_started_at = time.perf_counter()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT actual_label FROM feedback WHERE text = ? ORDER BY timestamp DESC LIMIT 1", (text,))
    row = c.fetchone()
    conn.close()
    hot_memory_lookup_ms = elapsed_ms(hot_memory_started_at)

    if row:
        # Якщо ти вже виправляв цей текст, повертаємо твій результат миттєво
        actual = row[0]
        result = {
            "score": 0.99 if actual == 'spam' else 0.01,
            "keywords": [],
            "subject_signals": [],
            "body_signals": [],
            "subject_safe_signals": [],
            "body_safe_signals": [],
            "metadata_signals": extract_metadata_signals(text) if include_explainability else [],
            "decision_source": "hot_memory",
            "rule_name": None,
            "rule_label": None,
            "rule_matches": [],
            "reason": "Matched previously confirmed feedback.",
            "matched_signals": [],
            "explainability_included": False,
            "explainability_reason": "deferred_hot_memory",
            "timings_ms": {
                "hot_memory_lookup_ms": hot_memory_lookup_ms,
                "rule_check_ms": 0.0,
                "model_inference_ms": 0.0,
                "explainability_ms": 0.0,
            },
        }
        print(f"Using hot memory for: {text[:30]}...")
    else:
        rule_check_started_at = time.perf_counter()
        phishing_rule_result = detect_lookalike_domain_rule(text)
        if phishing_rule_result:
            rule_result = phishing_rule_result
            rule_explainability_reason = "phishing_domain_rule"
        else:
            rule_result = detect_safe_business_rule(raw_text)
            rule_explainability_reason = "safe_business_rule"
        rule_check_ms = elapsed_ms(rule_check_started_at)
        if rule_result:
            result = {
                "score": float(rule_result["score"]),
                "keywords": [],
                "subject_signals": [],
                "body_signals": [],
                "subject_safe_signals": [],
                "body_safe_signals": [],
                "metadata_signals": extract_metadata_signals(text) if include_explainability else [],
                "decision_source": rule_result["decision_source"],
                "rule_name": rule_result["rule_name"],
                "rule_label": rule_result["rule_label"],
                "rule_matches": rule_result["rule_matches"],
                "reason": rule_result.get("reason"),
                "matched_signals": rule_result.get("matched_signals", []),
                "explainability_included": False,
                "explainability_reason": f"deferred_{rule_explainability_reason}",
                "timings_ms": {
                    "hot_memory_lookup_ms": hot_memory_lookup_ms,
                    "rule_check_ms": rule_check_ms,
                    "model_inference_ms": 0.0,
                    "explainability_ms": 0.0,
                },
            }
        else:
            result = run_model_inference(
                text=text,
                threshold=threshold,
                include_explainability=include_explainability,
            )
            model_timings = dict(result.get("timings_ms", {}))
            result["timings_ms"] = {
                "hot_memory_lookup_ms": hot_memory_lookup_ms,
                "rule_check_ms": rule_check_ms,
                "model_inference_ms": model_timings.get("model_inference_ms", 0.0),
                "explainability_ms": model_timings.get("explainability_ms", 0.0),
            }

    is_spam_predicted = result["score"] >= threshold

    response = {
        "spam_score": result["score"],
        "base_threshold": threshold,
        "threshold_used": threshold,
        "is_spam_predicted": is_spam_predicted,
        "predicted_label": "spam" if is_spam_predicted else "ham",
        "decision_source": result["decision_source"],
        "rule_name": result["rule_name"],
        "rule_label": result["rule_label"],
        "rule_matches": result["rule_matches"],
        "reason": result["reason"],
        "matched_signals": result["matched_signals"],
        "keywords": result["keywords"],
        "subject_signals": result["subject_signals"],
        "body_signals": result["body_signals"],
        "subject_safe_signals": result["subject_safe_signals"],
        "body_safe_signals": result["body_safe_signals"],
        "metadata_signals": result["metadata_signals"],
        "explainability_included": result["explainability_included"],
        "explainability_reason": result["explainability_reason"],
        "timings_ms": {
            **result.get("timings_ms", {}),
            "cache_lookup_ms": cache_lookup_ms,
            "total_ms": elapsed_ms(request_started_at),
        },
        "cache_hit": False,
    }

    set_cached_analysis(cache_key, response)
    return merge_runtime_status(response)


@app.get("/model-meta")
def get_model_meta():
    retrain_state = get_retrain_state_snapshot()
    with ANALYSIS_CACHE_LOCK:
        analysis_cache_entries = len(ANALYSIS_CACHE)
    with MODEL_LOCK:
        return {
            "model_name": meta.get("model_name"),
            "threshold": get_current_threshold(),
            "raw_model_threshold": meta.get("threshold"),
            "last_retrain": meta.get("last_retrain"),
            "evaluation_scope": meta.get("evaluation_scope"),
            "feedback_training_size": meta.get("feedback_training_size", 0),
            "feedback_holdout_excluded": meta.get("feedback_holdout_excluded", 0),
            "test_metrics": meta.get("test_metrics", {}),
            "evaluation_summary": meta.get("evaluation_summary", {}),
            "dashboard_summary": meta.get("dashboard_summary", {}),
            "evaluation_reports": meta.get("evaluation_reports", {}),
            "retrain_in_progress": retrain_state["in_progress"],
            "retrain_started_at": retrain_state["started_at"],
            "retrain_last_finished_at": retrain_state["last_finished_at"],
            "retrain_last_status": retrain_state["last_status"],
            "retrain_last_error": retrain_state["last_error"],
            "analysis_cache_entries": analysis_cache_entries,
        }

@app.post("/learn")
def learn_feedback(request: LearnRequest):
    learning_text = compose_analysis_text(
        text=request.text,
        sender=request.sender,
        sender_domain=request.sender_domain,
    )
    # Визначаємо правильну мітку
    actual_is_spam = request.is_spam_predicted if request.is_correct else not request.is_spam_predicted
    label_str = "spam" if actual_is_spam else "ham"
    predicted_str = "spam" if request.is_spam_predicted else "ham"
    
    # Зберігаємо у базу
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO feedback VALUES (?, ?, ?, ?, ?)", 
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), learning_text, label_str, predicted_str, request.is_correct))
    conn.commit()
    clear_analysis_cache()
    
    # Перевіряємо, чи пора перенавчатися
    c.execute("SELECT COUNT(*) FROM feedback")
    count = c.fetchone()[0]
    conn.close()
    
    retrain_started = False
    if count > 0 and count % RETRAIN_THRESHOLD == 0:
        print("Scheduling automatic retraining in background...")
        retrain_started = start_retrain_in_background()
        
    return {
        "status": "learned",
        "total_feedback": count,
        "retrain_scheduled": retrain_started,
        "retrain_in_progress": get_retrain_state_snapshot()["in_progress"],
        "retrain_started_at": get_retrain_state_snapshot()["started_at"],
        "retrain_last_finished_at": get_retrain_state_snapshot()["last_finished_at"],
        "retrain_last_status": get_retrain_state_snapshot()["last_status"],
        "retrain_last_error": get_retrain_state_snapshot()["last_error"],
    }
