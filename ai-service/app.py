from pathlib import Path
import joblib
import streamlit as st
import time
from PIL import Image
import pytesseract
import csv
import os
from datetime import datetime
import plotly.express as px
import pandas as pd
import sqlite3

from dataset_loader import combine_training_data, load_training_corpora, prepare_feedback_frame
from runtime_metadata import refresh_runtime_metadata

# --- КОНФІГУРАЦІЯ НАВЧАННЯ ---
RETRAIN_THRESHOLD = 5  # Перенавчати модель кожні 5 нових відгуків
DATA_FILE = "data/feedback_log.csv" 
DEFAULT_THRESHOLD = 0.5
DEFAULT_EVALUATION_SCOPE = "full_offline_eval"

# Вказуємо шлях до Tesseract (для Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- 1. Налаштування сторінки ---
st.set_page_config(
    page_title="Spam Detection AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Ініціалізація стану сесії ---
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'feedback_given' not in st.session_state:
    st.session_state.feedback_given = False
if 'total_checked' not in st.session_state:
    st.session_state.total_checked = 0
if 'spam_count' not in st.session_state:
    st.session_state.spam_count = 0
if 'ham_count' not in st.session_state:
    st.session_state.ham_count = 0
if 'history' not in st.session_state:
    st.session_state.history = []

# --- 2. CSS (Cyber Style) ---
st.markdown("""
    <style>
    .stApp { background-color: #0A0F1C; color: #F8FAFC; }
    [data-testid="stSidebar"] { background-color: #0d1323; border-right: 1px solid #1A2236; }
    div.stButton > button {
        background: linear-gradient(90deg, #0ea5e9, #10b981);
        color: white; border-radius: 12px; font-weight: 600; padding: 12px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. Функції навчання та БД ---

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/feedback.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (timestamp TEXT, text TEXT, actual_label TEXT, predicted_label TEXT, user_is_correct BOOLEAN)''')
    conn.commit()
    conn.close()

init_db()

@st.cache_resource
def load_artifacts():
    pipeline = joblib.load("models/spam_pipeline.pkl")
    meta = joblib.load("models/model_meta.pkl")
    return pipeline, meta

def retrain_model():
    """Перенавчає модель на всіх базових CSV та нових відгуках користувача."""
    try:
        conn = sqlite3.connect("data/feedback.db")
        new_data_df = pd.read_sql_query("SELECT text, actual_label as label FROM feedback", conn)
        conn.close()

        if len(new_data_df) < RETRAIN_THRESHOLD:
            return False

        base_df = load_training_corpora(
            data_dir="data",
            ignored_filenames={"feedback_log.csv"},
        )
        feedback_df = prepare_feedback_frame(
            new_data_df,
            label_column="label",
            text_column="text",
            source_name="user_feedback_db",
        )

        if feedback_df.empty:
            return False

        combined_df = combine_training_data(
            base_df,
            feedback_df=feedback_df,
            feedback_weight=5,
        )

        X = combined_df['text'].astype(str)
        y = combined_df['label'].astype(int)

        pipeline, meta = load_artifacts()
        pipeline.fit(X, y)
        meta = refresh_runtime_metadata(pipeline, combined_df, previous_meta=meta)

        joblib.dump(pipeline, "models/spam_pipeline.pkl")
        joblib.dump(meta, "models/model_meta.pkl")
        
        st.cache_resource.clear()
        return True
    except Exception as e:
        st.error(f"Помилка під час навчання: {e}")
        return False

def save_feedback(text: str, is_spam_predicted: bool, is_correct: bool):
    actual_is_spam = is_spam_predicted if is_correct else not is_spam_predicted
    label_str = "spam" if actual_is_spam else "ham"
    predicted_str = "spam" if is_spam_predicted else "ham"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = sqlite3.connect("data/feedback.db")
    c = conn.cursor()
    c.execute("INSERT INTO feedback VALUES (?, ?, ?, ?, ?)", 
              (timestamp, text, label_str, predicted_str, is_correct))
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM feedback")
    count = c.fetchone()[0]
    conn.close()

    if count > 0 and count % RETRAIN_THRESHOLD == 0:
        with st.spinner("🤖 Автоматичне перенавчання моделі на основі ваших відгуків..."):
            if retrain_model():
                st.toast("🚀 Модель успішно оновилася самостійно!", icon="🧠")

def export_sqlite_to_csv():
    try:
        conn = sqlite3.connect("data/feedback.db")
        df = pd.read_sql_query("SELECT * FROM feedback", conn)
        df.to_csv("data/feedback_log.csv", index=False, encoding='utf-8-sig')
        conn.close()
        return True
    except Exception as e:
        return False

pipeline, meta = load_artifacts()
preprocessor = pipeline.named_steps["prep"]
classifier = pipeline.named_steps["clf"]
current_threshold = float(meta.get("threshold", DEFAULT_THRESHOLD))
evaluation_scope = meta.get("evaluation_scope", DEFAULT_EVALUATION_SCOPE)
dashboard_summary = meta.get("dashboard_summary", {})
evaluation_summary = meta.get("evaluation_summary", {})
ukrainian_report_meta = meta.get("evaluation_reports", {}).get("ukrainian_test", {})
english_report_meta = meta.get("evaluation_reports", {}).get("english_test", {})


def render_report_panel(title, report_meta, metric_label, metric_value_pct):
    if not report_meta.get("rows"):
        return

    st.markdown("---")
    st.markdown(f"#### {title}")
    value = 0.0 if metric_value_pct is None else float(metric_value_pct)
    st.metric(metric_label, f"{value:.2f}%")
    with st.expander("Показати сегментний звіт"):
        st.dataframe(
            pd.DataFrame(report_meta["rows"]),
            use_container_width=True,
            hide_index=True,
        )


def render_evaluation_scope_badge(scope):
    badges = {
        "full_offline_eval": {
            "label": "Full Offline Eval",
            "background": "#14532d",
            "border": "#22c55e",
            "text": "#dcfce7",
            "description": "Метрики підтверджені на незалежному тестовому датасеті.",
        },
        "auto_retrain_snapshot": {
            "label": "Auto-Retrain Snapshot",
            "background": "#7c2d12",
            "border": "#f59e0b",
            "text": "#ffedd5",
            "description": "Метрики актуалізовані після фідбеків, але це локальний зріз і згодом бажаний повний ретрейн.",
        },
    }
    badge = badges.get(scope, badges["full_offline_eval"])
    st.markdown(
        f"""
        <div style="margin: 10px 0 14px 0;">
            <span style="
                display: inline-block;
                padding: 6px 10px;
                border-radius: 999px;
                border: 1px solid {badge['border']};
                background: {badge['background']};
                color: {badge['text']};
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.02em;
            ">
                {badge['label']}
            </span>
            <div style="margin-top: 8px; font-size: 12px; color: #cbd5e1; line-height: 1.4;">
                {badge['description']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("### 🛡️ Spam Detection AI")
    st.caption(f"Останнє навчання: {meta.get('last_retrain', 'При завантаженні')}")
    st.markdown("---")
    
    st.markdown("#### 📊 Статистика")
    render_evaluation_scope_badge(evaluation_scope)
    col1, col2, col3 = st.columns(3)
    col1.metric("Всього", st.session_state.total_checked)
    col2.metric("Спам", st.session_state.spam_count)
    col3.metric("Safe", st.session_state.ham_count)
    
    if st.session_state.total_checked > 0:
        chart_data = pd.DataFrame({
            "Категорія": ["Spam", "Ham"],
            "Кількість": [st.session_state.spam_count, st.session_state.ham_count]
        })
        fig = px.pie(chart_data, names="Категорія", values="Кількість", hole=0.6,
                     color_discrete_sequence=["#EF4444", "#22C55E"])
        fig.update_layout(height=200, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, use_container_width=True)

    render_report_panel(
        "🇺🇦 Ukrainian Eval",
        ukrainian_report_meta,
        metric_label="UA Spam Recall",
        metric_value_pct=dashboard_summary.get("ua_spam_recall_pct"),
    )
    render_report_panel(
        "🇬🇧 English Eval",
        english_report_meta,
        metric_label="EN Spam Recall",
        metric_value_pct=dashboard_summary.get("en_spam_recall_pct"),
    )

# --- 5. ЦЕНТРАЛЬНА ЧАСТИНА ---
st.title("🛡️ Розумна детекція спаму")

user_input = st.text_area("Вставте текст листа:", height=150)

# --- 6. ЛОГІКА АНАЛІЗУ ---
if st.button("🔍 Перевірити"):
    if user_input:
        with st.spinner("🧠 Аналізуємо текст..."):
            time.sleep(0.4)
            
            # ГАРЯЧА ПАМ'ЯТЬ
            conn = sqlite3.connect("data/feedback.db")
            c = conn.cursor()
            c.execute("SELECT actual_label FROM feedback WHERE text = ? ORDER BY timestamp DESC LIMIT 1", (user_input,))
            row = c.fetchone()
            conn.close()

            if row:
                forced_label = row[0]
                prob = 0.99 if forced_label == 'spam' else 0.01
                st.toast("⚡ Знайдено у ваших відгуках! Застосовано виправлення.", icon="🧠")
            else:
                features = preprocessor.transform([user_input])
                prob = classifier.predict_proba(features)[0][1]

            predicted_is_spam = prob >= current_threshold
            
            st.session_state.analyzed = True
            st.session_state.spam_score = prob
            st.session_state.current_text = user_input
            st.session_state.prediction_threshold = current_threshold
            st.session_state.predicted_is_spam = predicted_is_spam
            st.session_state.feedback_given = False 
            
            st.session_state.total_checked += 1
            if predicted_is_spam:
                st.session_state.spam_count += 1
            else:
                st.session_state.ham_count += 1
            
            st.rerun()

if st.session_state.analyzed:
    score = st.session_state.spam_score
    st.metric("Ймовірність спаму", f"{score:.1%}")
    
    hue = max(0, min(120, int(120 - (score * 120))))
    st.markdown(f"""
        <div style="width: 100%; background: #1A2236; border-radius: 10px;">
            <div style="width: {score*100}%; background: hsl({hue}, 80%, 50%); height: 20px; border-radius: 10px; transition: width 0.5s ease-out, background 0.5s ease-out;"></div>
        </div>
    """, unsafe_allow_html=True)

    # --- FEEDBACK LOOP ---
    st.markdown("### 🧠 Навчіть мою модель")
    c1, c2 = st.columns(2)
    if not st.session_state.feedback_given:
        if c1.button("✔️ Правильно"):
            save_feedback(st.session_state.current_text, st.session_state.predicted_is_spam, True)
            st.session_state.feedback_given = True
            st.rerun()
        if c2.button("⚠️ Модель помилилася"):
            save_feedback(st.session_state.current_text, st.session_state.predicted_is_spam, False)
            st.session_state.feedback_given = True
            st.rerun()
    else:
        st.info("Дякую! Ці дані вже використовуються для мого самонавчання.")
