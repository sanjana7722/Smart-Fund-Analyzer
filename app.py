import altair as alt
from datetime import datetime
import io
import json
import os
import re
import sqlite3
import textwrap
import urllib.parse
import urllib.request

import matplotlib
import pandas as pd
import streamlit as st

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.titlesize"] = 14
plt.rcParams["axes.titleweight"] = "bold"


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # Set this in your environment or .env file; do not commit secrets.


st.set_page_config(
    page_title="AI Mutual Fund Advisor",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)


APP_LINKS = {
    "BI Dashboard": "https://example.com/bi-dashboard",
    "Project Demo": "https://example.com/project-demo",
    "Repository": "https://github.com/your-username/your-repository",
    "FAQs": "https://example.com/faqs",
    "Contact": "https://example.com/contact",
}

LOGO_IMAGE_PATH = "logo_image.jpg"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


@st.cache_data
def load_data():
    scored_path = "backend/data/final_scored_funds.csv"
    mapping_path = "backend/data/fund_name_with_Id.xlsx"

    df_scored = pd.read_csv(scored_path)
    df_mapping = pd.read_excel(mapping_path)

    df_scored.columns = df_scored.columns.str.strip()
    df_mapping.columns = df_mapping.columns.str.strip()

    df_merged = pd.merge(
        df_scored,
        df_mapping,
        left_on="Fund_Name",
        right_on="Fund",
        how="inner",
    )

    df_merged.rename(columns={"Fund Name": "Actual_Fund_Name"}, inplace=True)
    df_merged.columns = df_merged.columns.str.strip()

    for col in df_merged.select_dtypes(include="object").columns:
        df_merged[col] = df_merged[col].astype(str).str.strip()

    df_merged["Risk_Category"] = df_merged["Risk_Category"].str.capitalize()
    return df_merged


df = load_data()

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedback.db")

@st.cache_resource
def get_feedback_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submitted_at TEXT NOT NULL,
            name TEXT,
            email TEXT,
            feedback_type TEXT NOT NULL,
            message TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def save_feedback(name, email, feedback_type, message):
    conn = get_feedback_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO feedback (submitted_at, name, email, feedback_type, message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (datetime.utcnow().isoformat(), name, email, feedback_type, message),
    )
    conn.commit()


def load_feedback_entries():
    conn = get_feedback_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, submitted_at, name, email, feedback_type, message FROM feedback ORDER BY id DESC"
    )
    rows = cursor.fetchall()
    return [
        {
            "id": row[0],
            "submitted_at": row[1],
            "name": row[2],
            "email": row[3],
            "feedback_type": row[4],
            "message": row[5],
        }
        for row in rows
    ]


if "page" not in st.session_state:
    st.session_state.page = "home"

if "results" not in st.session_state:
    st.session_state.results = None

if "risk_quiz_score" not in st.session_state:
    st.session_state.risk_quiz_score = 2

if "risk_quiz_label" not in st.session_state:
    st.session_state.risk_quiz_label = "Moderate"

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "I can explain your recommendation, teach mutual fund basics, compare categories, and answer follow-up questions in simple language.",
        }
    ]

if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = "Explain My Plan"

if "chat_result_signature" not in st.session_state:
    st.session_state.chat_result_signature = None

if "brand_name" not in st.session_state:
    st.session_state.brand_name = "AI Mutual Fund Advisor"

if "brand_tagline" not in st.session_state:
    st.session_state.brand_tagline = "Smart Investing"

if "brand_mark" not in st.session_state:
    st.session_state.brand_mark = "AM"

if "saved_reports" not in st.session_state:
    st.session_state.saved_reports = []

if "show_feedback" not in st.session_state:
    st.session_state.show_feedback = False

if "admin_mode" not in st.session_state:
    st.session_state.admin_mode = False

if "admin_password_input" not in st.session_state:
    st.session_state.admin_password_input = ""

DEFAULT_RECOMMENDATION_INPUTS = {
    "age_input": 25,
    "monthly_income_input": 50000,
    "investment_amount_input": 50000,
    "monthly_sip_input": 5000,
    "risk_appetite_input": "Moderate",
    "duration_input": "3-5 Years",
    "financial_goal_input": "Retirement",
    "market_sentiment_input": "Neutral",
    "tax_saving_input": False,
    "esg_preference_input": False,
}


def sanitize_recommendation_form_state(values):
    sanitized = dict(values)
    numeric_floor_defaults = {
        "age_input": 18,
        "monthly_income_input": 1,
        "investment_amount_input": 1000,
        "monthly_sip_input": 500,
    }

    for key, default_value in DEFAULT_RECOMMENDATION_INPUTS.items():
        current_value = sanitized.get(key)
        if current_value is None or current_value == "":
            sanitized[key] = default_value

    for key, min_value in numeric_floor_defaults.items():
        if sanitized.get(key, 0) < min_value:
            sanitized[key] = DEFAULT_RECOMMENDATION_INPUTS[key]

    return sanitized


for key, value in DEFAULT_RECOMMENDATION_INPUTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

for key, value in sanitize_recommendation_form_state(
    {name: st.session_state.get(name) for name in DEFAULT_RECOMMENDATION_INPUTS}
).items():
    st.session_state[key] = value

if "refine_min_return" not in st.session_state:
    st.session_state.refine_min_return = None

if "refine_max_volatility" not in st.session_state:
    st.session_state.refine_max_volatility = None

if "pending_form_sync" not in st.session_state:
    st.session_state.pending_form_sync = None

if st.session_state.pending_form_sync:
    for key, value in sanitize_recommendation_form_state(st.session_state.pending_form_sync).items():
        st.session_state[key] = value
    st.session_state.pending_form_sync = None

theme = {
    "bg_top": "rgba(8, 145, 178, 0.18)",
    "bg_left": "rgba(59, 130, 246, 0.14)",
    "bg_gradient": "linear-gradient(180deg, #08111f 0%, #0d1728 100%)",
    "text": "#e6eef8",
    "heading": "#f3f7fb",
    "muted": "#9fb3c8",
    "panel": "rgba(13,23,40,0.96)",
    "panel_border": "rgba(148,163,184,0.16)",
    "form": "rgba(11,20,34,0.98)",
    "input": "#101b2d",
    "input_border": "#28415f",
    "control_surface": "#101b2d",
    "control_text": "#e6eef8",
    "hero": "linear-gradient(135deg, #071426 0%, #0f766e 45%, #2563eb 100%)",
    "accent": "#34d399",
    "accent_2": "#0284c7",
    "summary": "linear-gradient(135deg, #0f172a 0%, #072f35 100%)",
    "card": "linear-gradient(180deg, #0d1829 0%, #0c2330 100%)",
    "tab_bg": "rgba(13,23,40,0.95)",
    "tab_text": "#ffffff",
}


css = """
<style>
    .stApp {
        background:
            radial-gradient(circle at top right, __BG_TOP__, transparent 22%),
            radial-gradient(circle at top left, __BG_LEFT__, transparent 24%),
            __BG_GRADIENT__;
        color: __TEXT__;
        font-family: "Aptos", "Segoe UI", "Helvetica Neue", sans-serif;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    p, li, label, span, div, small { color: __TEXT__; }
    .stMarkdown, .stText, .stCaption, .stAlert { color: __TEXT__; }
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span,
    [data-testid="stWidgetLabel"] label {
        color: __HEADING__ !important;
        font-weight: 700;
        font-size: 0.96rem;
    }
    .stRadio label, .stCheckbox label, .stSelectbox label, .stNumberInput label {
        color: __HEADING__ !important;
    }
    .stTabs [data-baseweb="tab-list"] button {
        color: #ffffff !important;
        font-weight: 800;
        background: linear-gradient(135deg, #0d1829 0%, #12304a 100%) !important;
        border: 1px solid __PANEL_BORDER__ !important;
        border-radius: 14px !important;
        padding: 0.85rem 1rem !important;
        min-width: 170px;
        justify-content: center;
        white-space: normal !important;
        height: auto !important;
        font-size: 1.02rem !important;
        line-height: 1.3 !important;
        opacity: 1 !important;
        margin-bottom: 0.2rem !important;
    }
    .stTabs [aria-selected="true"] {
        color: #ffffff !important;
        background: linear-gradient(135deg, #132841 0%, #1b4f78 100%) !important;
        box-shadow: 0 10px 20px rgba(8, 145, 178, 0.22) !important;
    }
    .stTabs [data-baseweb="tab-list"] button *,
    .stTabs [aria-selected="true"] * {
        color: #ffffff !important;
        fill: #ffffff !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 0.7rem; flex-wrap: wrap; }
    .stCaption { color: __MUTED__ !important; }
    h1, h2, h3, h4, h5, h6 {
        color: __HEADING__ !important;
        font-family: "Cambria", Georgia, serif;
        letter-spacing: -0.02em;
    }
    .stForm {
        background: __FORM__;
        border: 1px solid __PANEL_BORDER__;
        border-radius: 22px;
        padding: 1rem 1rem 0.25rem 1rem;
        box-shadow: 0 18px 42px rgba(16, 35, 63, 0.10);
    }
    .stForm p,
    .stForm div,
    .stForm span,
    .stForm small {
        color: __CONTROL_TEXT__;
    }
    .stForm .stMarkdown p,
    .stForm .stMarkdown div,
    .stForm .stMarkdown span,
    .stForm .stMarkdown strong,
    .stForm .stCaption,
    .stForm .stCaption p,
    .stForm [data-testid="stCaptionContainer"],
    .stForm [data-testid="stCaptionContainer"] * {
        color: __CONTROL_TEXT__ !important;
    }
    .stForm .stMarkdown strong {
        font-size: 1.06rem;
        font-weight: 800;
    }
    .stForm .stCaption,
    .stForm .stCaption p {
        opacity: 0.78;
    }
    [data-testid="stNumberInputContainer"],
    [data-testid="stSelectbox"] > div,
    .stRadio > div,
    .stCheckbox { background: transparent; }
    .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] > div {
        background: __CONTROL_SURFACE__ !important;
        color: __CONTROL_TEXT__ !important;
        border: 1px solid __INPUT_BORDER__ !important;
        border-radius: 12px !important;
        min-height: 46px;
        box-shadow: 0 8px 18px rgba(16,35,63,0.08);
    }
    .stSelectbox div[data-baseweb="select"] * {
        color: __CONTROL_TEXT__ !important;
    }
    .stSelectbox div[data-baseweb="select"] span {
        color: __CONTROL_TEXT__ !important;
        opacity: 1 !important;
    }
    .stSelectbox svg {
        fill: __CONTROL_TEXT__ !important;
    }
    div[role="listbox"] {
        background: #101b2d !important;
        border: 1px solid __INPUT_BORDER__ !important;
        border-radius: 14px !important;
        box-shadow: 0 18px 36px rgba(16,35,63,0.18) !important;
        overflow: hidden !important;
        color: #e6eef8 !important;
    }
    ul[role="listbox"] {
        background: #101b2d !important;
        color: #e6eef8 !important;
        border: 1px solid __INPUT_BORDER__ !important;
        border-radius: 14px !important;
        box-shadow: 0 18px 36px rgba(16,35,63,0.18) !important;
        overflow: hidden !important;
    }
    div[role="listbox"],
    div[role="listbox"] > div,
    div[role="listbox"] ul,
    div[role="listbox"] li,
    div[role="listbox"] div {
        background: #101b2d !important;
        color: #e6eef8 !important;
    }
    ul[role="listbox"] *,
    ul[role="listbox"] li,
    ul[role="listbox"] div,
    ul[role="listbox"] span {
        background: #101b2d !important;
        color: #e6eef8 !important;
    }
    div[role="option"] {
        background: #101b2d !important;
        color: #e6eef8 !important;
        font-size: 1rem !important;
        line-height: 1.45 !important;
    }
    div[role="option"] * {
        color: #e6eef8 !important;
    }
    div[role="option"][aria-selected="true"] {
        background: #163150 !important;
        color: #ffffff !important;
    }
    div[role="option"]:hover {
        background: #142742 !important;
        color: #ffffff !important;
    }
    .stNumberInput input::placeholder {
        color: rgba(16,35,63,0.45) !important;
    }
    .stNumberInput input:focus,
    .stSelectbox div[data-baseweb="select"] > div:focus-within {
        border-color: __ACCENT__ !important;
        box-shadow: 0 0 0 3px rgba(56,189,248,0.16), 0 10px 22px rgba(16,35,63,0.10) !important;
    }
    .stNumberInput button { color: __CONTROL_TEXT__ !important; }
    .stRadio [role="radiogroup"] { gap: 0.6rem; }
    .stRadio [role="radiogroup"] > label {
        background: __CONTROL_SURFACE__;
        border: 1px solid __INPUT_BORDER__;
        border-radius: 12px;
        padding: 0.55rem 0.8rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        color: __CONTROL_TEXT__ !important;
    }
    .stRadio [role="radiogroup"] > label:hover,
    .stCheckbox label:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(16,35,63,0.08);
    }
    .stCheckbox label {
        background: __CONTROL_SURFACE__;
        border: 1px solid __INPUT_BORDER__;
        border-radius: 12px;
        padding: 0.55rem 0.8rem;
        width: 100%;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: __CONTROL_TEXT__ !important;
    }
    .hero {
        padding: 2.4rem 2.2rem;
        border-radius: 24px;
        background: __HERO__;
        color: #ffffff;
        box-shadow: 0 24px 60px rgba(16, 35, 63, 0.18);
        margin-bottom: 1.25rem;
        position: relative;
        overflow: hidden;
    }
    .hero::after {
        content: "";
        position: absolute;
        inset: auto -40px -40px auto;
        width: 180px;
        height: 180px;
        background: rgba(255,255,255,0.08);
        border-radius: 50%;
    }
    .hero h1 { font-size: 3rem; line-height: 1.05; margin-bottom: 0.65rem; }
    .hero p { font-size: 1.05rem; color: rgba(255, 255, 255, 0.86); margin-bottom: 0; }
    .hero-strip { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 1rem; }
    .hero-chip {
        background: rgba(255,255,255,0.14);
        color: #ffffff;
        border: 1px solid rgba(255,255,255,0.16);
        border-radius: 999px;
        padding: 0.45rem 0.8rem;
        font-size: 0.86rem;
        font-weight: 700;
    }
    .form-stage {
        background: __PANEL__;
        border: 1px solid __PANEL_BORDER__;
        border-radius: 18px;
        padding: 0.9rem 1rem;
        box-shadow: 0 12px 26px rgba(16,35,63,0.06);
        min-height: 88px;
    }
    .form-stage-title {
        font-size: 0.86rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: __ACCENT__;
        margin-bottom: 0.35rem;
    }
    .form-stage-copy { color: __MUTED__; font-size: 0.92rem; line-height: 1.45; }
    .section-title {
        font-size: 1.18rem;
        font-weight: 800;
        color: __HEADING__;
        margin-top: 0.2rem;
        margin-bottom: 0.8rem;
        font-family: "Cambria", Georgia, serif;
    }
    .info-card, .metric-card, .panel {
        background: __PANEL__;
        border: 1px solid __PANEL_BORDER__;
    }
    .info-card {
        border-radius: 18px;
        padding: 1rem 1rem 0.85rem 1rem;
        box-shadow: 0 14px 32px rgba(16, 35, 63, 0.08);
        min-height: 148px;
    }
    .info-card h3 { margin: 0 0 0.35rem 0; font-size: 1rem; color: __HEADING__; }
    .info-card p { margin: 0; color: __MUTED__; font-size: 0.93rem; }
    .metric-card {
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 14px 34px rgba(16, 35, 63, 0.08);
    }
    .metric-label { color: __MUTED__; font-size: 0.9rem; margin-bottom: 0.4rem; }
    .metric-value { color: __HEADING__; font-size: 1.9rem; font-weight: 800; line-height: 1.1; }
    .metric-note { color: __ACCENT__; font-size: 0.85rem; margin-top: 0.35rem; }
    .panel {
        border-radius: 22px;
        padding: 1.1rem 1.15rem;
        box-shadow: 0 16px 38px rgba(16, 35, 63, 0.08);
        color: __HEADING__;
    }
    .compact-panel {
        border-radius: 16px;
        padding: 0.7rem 0.85rem;
        box-shadow: 0 10px 22px rgba(16, 35, 63, 0.06);
        font-size: 0.92rem;
        line-height: 1.4;
        color: __TEXT__;
    }
    .recommendation-card {
        background: __CARD__;
        border: 1px solid rgba(15, 118, 110, 0.16);
        border-radius: 22px;
        padding: 1.15rem;
        box-shadow: 0 16px 30px rgba(16, 35, 63, 0.08);
        height: 100%;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }
    .recommendation-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 22px 36px rgba(16,35,63,0.12);
    }
    .recommendation-card h3 { margin: 0 0 0.35rem 0; font-size: 1.12rem; color: __HEADING__ !important; }
    .recommendation-meta { color: __ACCENT__ !important; font-weight: 700; font-size: 0.88rem; margin-bottom: 0.7rem; }
    .summary-box {
        background: __SUMMARY__;
        border: 1px solid rgba(15, 118, 110, 0.14);
        border-radius: 20px;
        padding: 1rem 1.1rem;
        box-shadow: 0 14px 28px rgba(15, 118, 110, 0.08);
    }
    .summary-box p { margin: 0; color: __TEXT__; font-size: 1.04rem; line-height: 1.55; }
    .trust-strip {
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
        margin: 0.65rem 0 1rem 0;
    }
    .trust-chip-card {
        flex: 1 1 220px;
        min-width: 0;
        background: rgba(13,23,40,0.82);
        border: 1px solid rgba(148,163,184,0.14);
        border-radius: 18px;
        padding: 0.85rem 1rem;
        box-shadow: 0 10px 24px rgba(16,35,63,0.06);
    }
    .trust-chip-label {
        color: __MUTED__;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.28rem;
    }
    .trust-chip-value {
        color: __HEADING__;
        font-size: 0.98rem;
        font-weight: 700;
        line-height: 1.35;
    }
    .disclosure-note {
        margin-bottom: 1rem;
        padding: 0.85rem 1rem;
        border-radius: 16px;
        border: 1px solid rgba(148,163,184,0.14);
        background: rgba(15,23,42,0.76);
        color: #94a3b8;
        font-size: 0.92rem;
        line-height: 1.5;
    }
    .disclosure-note strong {
        color: #cbd5e1 !important;
    }
    .action-dock {
        background: rgba(13,23,40,0.82);
        border: 1px solid rgba(148,163,184,0.16);
        border-radius: 22px;
        padding: 0.9rem 1rem;
        box-shadow: 0 16px 34px rgba(16,35,63,0.08);
        margin-top: 1rem;
    }
    .action-dock-title {
        color: __HEADING__;
        font-size: 1rem;
        font-weight: 800;
        margin-bottom: 0.18rem;
    }
    .action-dock-copy {
        color: __MUTED__;
        font-size: 0.9rem;
        line-height: 1.4;
        margin-bottom: 0.8rem;
    }
    .current-plan-card {
        border: 1px solid rgba(52,211,153,0.34);
        box-shadow: 0 18px 36px rgba(16,35,63,0.12), 0 0 0 1px rgba(52,211,153,0.12) inset;
    }
    .stButton > button {
        background: linear-gradient(135deg, __ACCENT__ 0%, __ACCENT_2__ 100%);
        color: #ffffff !important;
        border: 0;
        border-radius: 12px;
        padding: 0.65rem 1.2rem;
        font-weight: 700;
        box-shadow: 0 12px 28px rgba(2, 132, 199, 0.22);
        font-size: 0.98rem;
        line-height: 1.2;
    }
    .stButton > button:hover { filter: brightness(1.04); }
    .stForm button { color: #ffffff !important; }
    .stFormSubmitButton button {
        background: linear-gradient(135deg, #0d1829 0%, #154468 100%) !important;
        color: #ffffff !important;
        opacity: 1 !important;
        border: 1px solid rgba(148,163,184,0.18) !important;
        box-shadow: 0 14px 28px rgba(8, 145, 178, 0.18) !important;
    }
    .stFormSubmitButton button p,
    .stFormSubmitButton button span,
    .stFormSubmitButton button div {
        color: #ffffff !important;
    }
    .stPopover button,
    .stPopover button * {
        color: #ffffff !important;
    }
    [data-testid="stDataFrame"] {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid __PANEL_BORDER__;
        background: __PANEL__;
    }
    [data-testid="stDataFrame"] * { color: __HEADING__ !important; }
    table, thead, tbody, tr, th, td { color: __HEADING__ !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: __ACCENT__ !important; }
    .brand-wrap {
        display:flex;
        align-items:center;
        gap:1rem;
        margin-bottom:1rem;
        padding:0.8rem 1rem;
        background:__PANEL__;
        border:1px solid __PANEL_BORDER__;
        border-radius:18px;
        box-shadow:0 12px 28px rgba(16,35,63,0.08);
    }
    .brand-logo {
        width:56px;
        height:56px;
        border-radius:16px;
        background:linear-gradient(135deg,__HEADING__ 0%,__ACCENT__ 55%,__ACCENT_2__ 100%);
        display:flex;
        align-items:center;
        justify-content:center;
        color:#ffffff !important;
        font-weight:800;
        font-size:1.15rem;
        box-shadow:0 12px 26px rgba(16,35,63,0.18);
        flex-shrink:0;
    }
    .brand-text-top {
        font-size:0.76rem;
        font-weight:800;
        letter-spacing:0.18em;
        color:__ACCENT__ !important;
        text-transform:uppercase;
    }
    .brand-text-main {
        font-size:1.5rem;
        font-weight:800;
        color:__HEADING__ !important;
        font-family:"Cambria", Georgia, serif;
        line-height:1.1;
    }
    [data-testid="stToggle"] {
        margin-top: 1.15rem;
        padding: 0.55rem 0.8rem;
        background: __PANEL__;
        border: 1px solid __PANEL_BORDER__;
        border-radius: 14px;
        box-shadow: 0 10px 22px rgba(16,35,63,0.08);
    }
    [data-testid="stToggle"] label,
    [data-testid="stToggle"] p,
    [data-testid="stToggle"] span {
        color: __HEADING__ !important;
        font-weight: 700 !important;
    }
    .chat-fab { margin-top: 0.2rem; }
    .chat-fab button {
        border-radius: 999px !important;
        padding: 0.8rem 1rem !important;
        background: linear-gradient(135deg,__HEADING__ 0%,__ACCENT__ 60%,__ACCENT_2__ 100%) !important;
        color: #ffffff !important;
        box-shadow: 0 14px 30px rgba(16,35,63,0.24) !important;
    }
    .takeaway-card {
        background: rgba(15,23,42,0.88);
        border: 1px solid rgba(86, 196, 225, 0.18);
        border-radius: 18px;
        padding: 1rem;
        box-shadow: 0 14px 32px rgba(16,35,63,0.08);
        min-height: 120px;
    }
    .takeaway-label {
        color: #94a3b8;
        text-transform: uppercase;
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        margin-bottom: 0.4rem;
    }
    .takeaway-value {
        color: __HEADING__;
        font-size: 1.28rem;
        font-weight: 800;
        margin-bottom: 0.45rem;
    }
    .takeaway-note {
        color: __MUTED__;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    [data-baseweb="popover"] {
        background: #101b2d !important;
        border: 1px solid __INPUT_BORDER__ !important;
        border-radius: 18px !important;
        box-shadow: 0 20px 44px rgba(16,35,63,0.20) !important;
        color: #e6eef8 !important;
    }
    [data-baseweb="popover"] * {
        color: #e6eef8 !important;
    }
    [data-baseweb="popover"] a {
        color: __ACCENT__ !important;
    }
    [data-baseweb="menu"],
    [data-baseweb="select-dropdown"] {
        background: #101b2d !important;
        border-radius: 14px !important;
        box-shadow: 0 18px 36px rgba(16,35,63,0.18) !important;
        color: #e6eef8 !important;
    }
    [data-baseweb="select-dropdown"] > div,
    [data-baseweb="select-dropdown"] ul,
    [data-baseweb="select-dropdown"] li,
    [data-baseweb="select-dropdown"] div,
    [data-baseweb="menu"] > div,
    [data-baseweb="menu"] ul,
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] div {
        background: #101b2d !important;
        color: #e6eef8 !important;
    }
    [data-baseweb="menu"] *,
    [data-baseweb="select-dropdown"] * {
        color: #e6eef8 !important;
    }
    [data-baseweb="menu"] [aria-selected="true"],
    [data-baseweb="select-dropdown"] [aria-selected="true"] {
        background: #163150 !important;
        color: #ffffff !important;
    }
    [data-baseweb="menu"] li:hover,
    [data-baseweb="select-dropdown"] li:hover,
    [data-baseweb="menu"] [role="option"]:hover,
    [data-baseweb="select-dropdown"] [role="option"]:hover {
        background: #142742 !important;
        color: #ffffff !important;
    }
    .stRadio [role="radiogroup"] > label *,
    .stCheckbox label *,
    .stButton > button *,
    .stFormSubmitButton button * {
        color: inherit !important;
    }
    .stMarkdown a, a {
        color: __ACCENT__ !important;
    }
    ul, ol {
        color: #111827 !important;
    }
    body [role="presentation"] [data-baseweb="popover"],
    body [role="presentation"] [data-baseweb="menu"],
    body [role="presentation"] [data-baseweb="select-dropdown"] {
        background: #101b2d !important;
        color: #e6eef8 !important;
    }
    body [role="presentation"] [data-baseweb="popover"] *,
    body [role="presentation"] [data-baseweb="menu"] *,
    body [role="presentation"] [data-baseweb="select-dropdown"] * {
        color: #e6eef8 !important;
        background-color: #101b2d !important;
    }
    [data-testid="stPopover"] *,
    [data-testid="stPopoverContent"] *,
    [data-testid="stPopover"] div,
    [data-testid="stPopoverContent"] div,
    [data-testid="stPopover"] p,
    [data-testid="stPopoverContent"] p {
        color: #e6eef8 !important;
        background: #101b2d !important;
    }
    [data-testid="stPopover"],
    [data-testid="stPopoverContent"],
    [data-testid="stPopover"] > div,
    [data-testid="stPopoverContent"] > div,
    div[role="dialog"],
    div[role="dialog"] > div {
        background: #ffffff !important;
        color: #111827 !important;
        border-radius: 18px !important;
    }
    [data-testid="stChatMessage"],
    [data-testid="stChatMessage"] > div,
    [data-testid="stChatMessage"] * {
        background: #ffffff !important;
        color: #111827 !important;
    }
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] * {
        background: #ffffff !important;
        color: #111827 !important;
    }
    [data-testid="stChatInput"] input,
    [data-testid="stChatInput"] textarea {
        background: #ffffff !important;
        color: #111827 !important;
    }
</style>
"""
for token, value in {
    "__BG_TOP__": theme["bg_top"],
    "__BG_LEFT__": theme["bg_left"],
    "__BG_GRADIENT__": theme["bg_gradient"],
    "__TEXT__": theme["text"],
    "__HEADING__": theme["heading"],
    "__MUTED__": theme["muted"],
    "__PANEL__": theme["panel"],
    "__PANEL_BORDER__": theme["panel_border"],
    "__FORM__": theme["form"],
    "__INPUT__": theme["input"],
    "__INPUT_BORDER__": theme["input_border"],
    "__CONTROL_SURFACE__": theme["control_surface"],
    "__CONTROL_TEXT__": theme["control_text"],
    "__HERO__": theme["hero"],
    "__ACCENT__": theme["accent"],
    "__ACCENT_2__": theme["accent_2"],
    "__SUMMARY__": theme["summary"],
    "__CARD__": theme["card"],
    "__TAB_BG__": theme["tab_bg"],
    "__TAB_TEXT__": theme["tab_text"],
}.items():
    css = css.replace(token, value)

st.markdown(css, unsafe_allow_html=True)


def metric_card(label, value, note):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top_bar():
    left, right = st.columns([5, 1])
    with left:
        logo_col, text_col = st.columns([1.1, 4.2])
        with logo_col:
            st.image(LOGO_IMAGE_PATH, width=110)
        with text_col:
            st.markdown(
                """
                <div style="padding-top:0.7rem;">
                    <div style="font-size:0.88rem;font-weight:700;letter-spacing:0.18em;color:#0f766e;">SMART INVESTING</div>
                    <div style="font-size:1.6rem;font-weight:800;color:#10233f;font-family:Georgia,'Times New Roman',serif;">AI Mutual Fund Advisor</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with right:
        with st.popover("⋮"):
            st.markdown("### More")
            for label, url in APP_LINKS.items():
                st.markdown(f"- [{label}]({url})")
            st.caption("Replace these placeholder links with your actual dashboard, repository, FAQ, and project pages.")


def takeaway_card(title, value, note):
    st.markdown(
        f"""
        <div class="takeaway-card">
            <div class="takeaway-label">{title}</div>
            <div class="takeaway-value">{value}</div>
            <div class="takeaway-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pill(label, tone="neutral"):
    tones = {
        "neutral": ("#fff7ed", "#9a3412"),
        "good": ("#ecfdf5", "#047857"),
        "warn": ("#fffbeb", "#b45309"),
        "info": ("#eff6ff", "#1d4ed8"),
    }
    bg, fg = tones.get(tone, tones["neutral"])
    st.markdown(
        f"""
        <div style="
            display:inline-block;
            padding:0.38rem 0.72rem;
            border-radius:999px;
            background:{bg};
            color:{fg};
            font-weight:700;
            font-size:0.84rem;
            border:1px solid rgba(17,24,39,0.08);
            margin-bottom:0.5rem;
        ">{label}</div>
        """,
        unsafe_allow_html=True,
    )


def info_card(title, body):
    st.markdown(
        f"""
        <div class="info-card">
            <h3>{title}</h3>
            <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_explanation_cards(results):
    return [
        (
            "Risk Fit",
            (
                f"Your selected risk appetite was {results['risk_appetite']}, and the quiz signal came out "
                f"{results['risk_quiz_label'].lower()}. The final portfolio stays {results['portfolio'].lower()} "
                f"with {results['equity']}% equity and {results['debt']}% debt."
            ),
        ),
        (
            "Goal Fit",
            (
                f"The shortlist was tilted toward funds that fit your {results['goal'].lower()} goal, "
                f"so the recommendation prioritizes category match before raw performance."
            ),
        ),
        (
            "Time Horizon Fit",
            (
                f"Your {results['duration'].lower()} horizon influences both the allocation and the fund types shown, "
                f"which is why the app avoided options that look mismatched for that timeline."
            ),
        ),
    ]


def build_sip_projection(monthly_sip, annual_return, years):
    monthly_rate = annual_return / 100 / 12
    values = []
    future_value = 0.0
    for month in range(1, years * 12 + 1):
        future_value = (future_value + monthly_sip) * (1 + monthly_rate)
        if month % 12 == 0:
            values.append(
                {
                    "Year": month // 12,
                    "Invested Amount": monthly_sip * month,
                    "Projected Value": future_value,
                }
            )
    return pd.DataFrame(values)


def format_currency(value):
    return f"Rs. {value:,.0f}"


def build_suitability_flags(
    *,
    goal,
    duration,
    tax_saving,
    esg_preference,
    market_sentiment,
    portfolio,
    equity,
):
    flags = []

    if duration == "1-3 Years" and equity >= 50:
        flags.append(
            "Short investment horizon with meaningful equity exposure can create visible interim volatility."
        )
    elif duration == "1-3 Years":
        flags.append(
            "Short duration means capital protection matters more than chasing high-growth categories."
        )

    if portfolio == "Aggressive":
        flags.append(
            "This mix is growth-oriented and may see sharp market swings before long-term returns settle."
        )

    if goal == "Emergency Fund":
        flags.append(
            "Emergency-fund goals need liquidity, so avoid locking too much money into volatile or restrictive categories."
        )

    if tax_saving:
        flags.append(
            "Tax-saving preference may introduce ELSS funds, which usually carry a 3-year lock-in."
        )

    if esg_preference:
        flags.append(
            "ESG filtering can narrow the shortlist, so the app may show fewer matching funds than a broad search."
        )

    if market_sentiment == "Bearish" and equity >= 60:
        flags.append(
            "Even with a cautious outlook, this recommendation still keeps notable equity for long-term growth."
        )

    return flags[:4]


def estimate_portfolio_volatility(filtered_df, equity, debt):
    if filtered_df.empty or "Volatility" not in filtered_df.columns:
        return round(max(4.0, 5.5 + equity * 0.12), 2)

    exposure_map = {
        "Liquid": 0.0,
        "Corporate Bond": 0.05,
        "Dynamic Asset Allocation": 0.45,
        "Aggressive Hybrid": 0.7,
        "Large Cap": 1.0,
        "Nifty 50": 1.0,
        "ELSS": 1.0,
        "Mid Cap": 1.0,
        "Small Cap": 1.0,
    }
    weights = []
    volatilities = []
    for _, row in filtered_df.iterrows():
        exposure = exposure_map.get(row["SubType"], 0.8)
        weight = equity * exposure + debt * (1 - exposure)
        weights.append(max(weight, 1))
        volatilities.append(float(row["Volatility"]))

    total_weight = sum(weights) or 1
    estimated = sum(weight / total_weight * vol for weight, vol in zip(weights, volatilities))
    return round(float(estimated), 2)


def classify_volatility(estimated_volatility):
    if estimated_volatility < 9:
        return "Low"
    if estimated_volatility < 13:
        return "Moderate"
    return "High"


def build_recommendation_inputs_from_state():
    return {
        "age": st.session_state.age_input,
        "monthly_income": st.session_state.monthly_income_input,
        "risk_appetite": st.session_state.risk_appetite_input,
        "investment_amount": st.session_state.investment_amount_input,
        "monthly_sip": st.session_state.monthly_sip_input,
        "duration": st.session_state.duration_input,
        "financial_goal": st.session_state.financial_goal_input,
        "tax_saving": st.session_state.tax_saving_input,
        "esg_preference": st.session_state.esg_preference_input,
        "market_sentiment": st.session_state.market_sentiment_input,
        "risk_quiz_score": st.session_state.risk_quiz_score,
        "risk_quiz_label": st.session_state.risk_quiz_label,
    }


def sync_recommendation_state_from_results(results):
    st.session_state.pending_form_sync = {
        "age_input": results["age"],
        "monthly_income_input": results["monthly_income"],
        "risk_appetite_input": results["risk_appetite"],
        "investment_amount_input": results["investment_amount"],
        "monthly_sip_input": results["monthly_sip"],
        "duration_input": results["duration"],
        "financial_goal_input": results["goal"],
        "market_sentiment_input": results["market_sentiment"],
        "tax_saving_input": results["tax_saving"],
        "esg_preference_input": results["esg_preference"],
    }


def save_results_to_history(results):
    st.session_state.saved_reports.insert(0, build_saved_report_entry(results))
    st.session_state.saved_reports = st.session_state.saved_reports[:8]


def run_recommendation(refine_min_return=None, refine_max_volatility=None, save_history=True):
    current_inputs = build_recommendation_inputs_from_state()
    results = calculate_recommendation(
        **current_inputs,
        refine_min_return=refine_min_return,
        refine_max_volatility=refine_max_volatility,
    )
    results["comparison_snapshots"] = build_comparison_snapshots(results)
    st.session_state.results = results
    st.session_state.refine_min_return = refine_min_return
    st.session_state.refine_max_volatility = refine_max_volatility
    if save_history:
        save_results_to_history(results)
    return results


def build_portfolio_comparison_inputs(results, target_risk_appetite):
    return {
        "age": results["age"],
        "monthly_income": results["monthly_income"],
        "risk_appetite": target_risk_appetite,
        "investment_amount": results["investment_amount"],
        "monthly_sip": results["monthly_sip"],
        "duration": results["duration"],
        "financial_goal": results["goal"],
        "tax_saving": results["tax_saving"],
        "esg_preference": results["esg_preference"],
        "market_sentiment": results["market_sentiment"],
        "risk_quiz_score": results["risk_quiz_score"],
        "risk_quiz_label": results["risk_quiz_label"],
    }


def build_comparison_snapshots(results):
    snapshots = []
    for target_risk_appetite in ["Conservative", "Moderate", "Aggressive"]:
        scenario = calculate_recommendation(
            **build_portfolio_comparison_inputs(results, target_risk_appetite)
        )
        snapshots.append(
            {
                "profile": target_risk_appetite,
                "portfolio": scenario["portfolio"],
                "equity": scenario["equity"],
                "debt": scenario["debt"],
                "return_range": scenario["return_range"],
                "estimated_volatility": scenario["estimated_volatility"],
                "future_value_low": scenario["future_value_low"],
                "future_value_high": scenario["future_value_high"],
                "top_fund": scenario["top_fund_reasons"][0]["name"] if scenario["top_fund_reasons"] else "No fund available",
                "risk_note": scenario["allocation_reasons"][1],
            }
        )
    return snapshots


def build_saved_report_entry(results):
    return {
        "saved_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "goal": results["goal"],
        "duration": results["duration"],
        "portfolio": results["portfolio"],
        "risk_appetite": results["risk_appetite"],
        "equity": results["equity"],
        "debt": results["debt"],
        "return_range": list(results["return_range"]),
        "estimated_volatility": results.get("estimated_volatility"),
        "volatility_label": results.get("volatility_label"),
        "future_value_low": results["future_value_low"],
        "future_value_high": results["future_value_high"],
        "investment_amount": results["investment_amount"],
        "monthly_sip": results["monthly_sip"],
        "confidence_label": results["confidence_label"],
        "summary": results["summary"],
        "warnings": results.get("warnings", []),
        "top_funds": [fund["name"] for fund in results.get("top_fund_reasons", [])[:3]],
        "results_snapshot": dict(results),
    }


def score_risk_quiz(risk_reaction, investment_style, time_commitment, return_expectation):
    risk_quiz_score = round(
        (
            {
                "Sell quickly": 1,
                "Wait and watch": 2,
                "Invest more if possible": 3,
            }[risk_reaction]
            + {
                "Capital safety": 1,
                "Balanced growth": 2,
                "Maximum long-term growth": 3,
            }[investment_style]
            + {
                "Less than 3 years": 1,
                "Around 5 years": 2,
                "10 years or more": 3,
            }[time_commitment]
            + {
                "Stable but lower returns": 1,
                "Some ups and downs": 2,
                "High volatility for higher growth": 3,
            }[return_expectation]
        )
        / 4
    )
    risk_quiz_label = {
        1: "Conservative",
        2: "Moderate",
        3: "Aggressive",
    }[risk_quiz_score]
    return risk_quiz_score, risk_quiz_label


def explain_risk_quiz_score(risk_quiz_label):
    explanations = {
        "Conservative": "Your answers show higher comfort with stability, shorter holding periods, or lower tolerance for market swings.",
        "Moderate": "Your answers show a balanced mindset, with room for growth but not extreme volatility.",
        "Aggressive": "Your answers show stronger comfort with long-term investing, market fluctuations, and higher-growth options.",
    }
    return explanations[risk_quiz_label]


def generate_chat_reply(question, results):
    query = question.lower().strip()
    if not query:
        return "Ask about allocation, risk, top funds, expected returns, or why a category was avoided."

    if results is None:
        return "Submit your profile first. Then I can answer questions about your allocation, top funds, and recommendation reasoning."

    if any(word in query for word in ["allocation", "equity", "debt", "split", "portfolio"]):
        return (
            f"Your current allocation is {results['equity']}% equity and {results['debt']}% debt. "
            f"This matches a {results['portfolio'].lower()} profile. "
            f"Main reasons: {results['allocation_reasons'][0]} {results['allocation_reasons'][1]}"
        )

    if any(word in query for word in ["risk", "safe", "aggressive", "moderate", "conservative"]):
        return (
            f"Your risk outcome is {results['portfolio']}. "
            f"The app mapped your inputs to this profile and then shortlisted funds in the matching risk category."
        )

    if any(word in query for word in ["return", "growth", "future", "value"]):
        return (
            f"Expected return range is {results['return_range'][0]}% to {results['return_range'][1]}% annually. "
            f"Projected value range is Rs. {results['future_value_low']:,.0f} to Rs. {results['future_value_high']:,.0f} over {results['years']} years."
        )

    if any(word in query for word in ["top fund", "which fund", "recommended fund", "best fund"]):
        top_fund = results["top_fund_reasons"][0]
        return (
            f"Top current pick: {top_fund['name']}. "
            f"It was chosen because {top_fund['reasons'][0].lower()}, {top_fund['reasons'][1].lower()}, "
            f"and it also has CAGR {top_fund['cagr']}% with Sharpe ratio {top_fund['sharpe']}."
        )

    if any(word in query for word in ["why", "reason", "chosen"]):
        top_fund = results["top_fund_reasons"][0]
        return (
            f"The recommendation is based on your goal, duration, market outlook, and risk category. "
            f"For example, {top_fund['name']} was shortlisted because {top_fund['reasons'][0].lower()} and {top_fund['reasons'][1].lower()}."
        )

    if any(word in query for word in ["avoid", "rejected", "not selected", "why not"]):
        return "Categories avoided for your profile: " + " ".join(results["not_suitable"][:2])

    if any(word in query for word in ["faq", "help", "what can you do"]):
        return "You can ask about allocation, risk category, expected return range, future value, top fund reasons, or what categories were avoided."

    return (
        "I can help with your current recommendation. Ask things like: "
        "'Why is my allocation 65/35?', 'Why was this fund chosen?', "
        "'What return range should I expect?', or 'Why were small-cap funds avoided?'"
    )


def render_advisor_chat(results):
    st.markdown("<div class='section-title'>Advisor Assistant</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="panel" style="padding:1rem;">
            Ask a quick question about your recommendation. This assistant uses your current profile and latest result on the page.
        </div>
        """,
        unsafe_allow_html=True,
    )
    for message in st.session_state.chat_messages[-4:]:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_prompt = st.chat_input("Ask about your allocation, returns, or why a fund was chosen")
    if user_prompt:
        st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
        reply = generate_chat_reply(user_prompt, results)
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()


def build_pdf_report(results):
    buffer = io.BytesIO()
    title_font = {"fontfamily": "DejaVu Serif", "fontweight": "bold", "color": "#10233f"}
    body_font = {"fontfamily": "DejaVu Sans", "color": "#334155"}
    accent_color = "#0f766e"
    secondary_color = "#0284c7"

    with PdfPages(buffer) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.patch.set_facecolor("white")
        fig.text(0.08, 0.95, "AI Mutual Fund Advisor Report", fontsize=20, **title_font)
        fig.text(0.08, 0.915, results["summary"], fontsize=11, **body_font)
        fig.text(0.08, 0.875, f"Confidence: {results['confidence_label']}", fontsize=11, color=accent_color, fontfamily="DejaVu Sans")
        fig.text(0.08, 0.848, f"Allocation: {results['equity']}% Equity / {results['debt']}% Debt", fontsize=11, fontfamily="DejaVu Sans", color="#10233f")
        fig.text(
            0.08,
            0.821,
            f"Expected return range: {results['return_range'][0]}% - {results['return_range'][1]}%",
            fontsize=11,
            fontfamily="DejaVu Sans",
            color="#10233f",
        )
        fig.text(
            0.08,
            0.794,
            f"Projected value range: Rs. {results['future_value_low']:,.0f} - Rs. {results['future_value_high']:,.0f}",
            fontsize=11,
            fontfamily="DejaVu Sans",
            color="#10233f",
        )

        y = 0.74
        fig.text(0.08, y, "Why this was recommended", fontsize=14, **title_font)
        y -= 0.03
        for item in results["reasons"]:
            wrapped = textwrap.fill(f"- {item}", width=88)
            fig.text(0.09, y, wrapped, fontsize=10.5, **body_font)
            y -= 0.055

        y -= 0.01
        fig.text(0.08, y, "Allocation reasoning", fontsize=14, **title_font)
        y -= 0.03
        for item in results["allocation_reasons"][:5]:
            wrapped = textwrap.fill(f"- {item}", width=88)
            fig.text(0.09, y, wrapped, fontsize=10.5, **body_font)
            y -= 0.05

        if results["not_suitable"]:
            y -= 0.01
            fig.text(0.08, y, "What was avoided", fontsize=14, **title_font)
            y -= 0.03
            for item in results["not_suitable"][:2]:
                wrapped = textwrap.fill(f"- {item}", width=88)
                fig.text(0.09, y, wrapped, fontsize=10.5, **body_font)
                y -= 0.05

        if results.get("warnings"):
            y -= 0.01
            fig.text(0.08, y, "Suitability flags", fontsize=14, **title_font)
            y -= 0.03
            for item in results["warnings"][:3]:
                wrapped = textwrap.fill(f"- {item}", width=88)
                fig.text(0.09, y, wrapped, fontsize=10.5, **body_font)
                y -= 0.05

        plt.axis("off")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(11.69, 8.27))
        fig.patch.set_facecolor("white")

        axes[0].pie(
            results["allocation_df"]["Share"],
            labels=results["allocation_df"]["Asset"],
            autopct="%1.0f%%",
            startangle=90,
            colors=[secondary_color, accent_color],
            wedgeprops={"width": 0.45, "edgecolor": "white"},
            textprops={"color": "#10233f", "fontsize": 11, "fontfamily": "DejaVu Sans"},
        )
        axes[0].set_title("Suggested Allocation", fontsize=14, fontweight="bold", color="#10233f", fontfamily="DejaVu Serif")

        axes[1].plot(
            results["projection_df"]["Year"],
            results["projection_df"]["Projected Value"],
            marker="o",
            linewidth=2.5,
            color=accent_color,
        )
        axes[1].fill_between(
            results["projection_df"]["Year"],
            results["projection_df"]["Projected Value"],
            color="#cffafe",
            alpha=0.5,
        )
        axes[1].set_title("Projected Growth", fontsize=14, fontweight="bold", color="#10233f", fontfamily="DejaVu Serif")
        axes[1].set_xlabel("Year")
        axes[1].set_ylabel("Value (Rs.)")
        axes[1].grid(alpha=0.25)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        plot_df = results["filtered_df"].head(5).copy().sort_values("Personalized_Score", ascending=True)
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        fig.patch.set_facecolor("white")
        ax.barh(
            plot_df["Actual_Fund_Name"],
            plot_df["Personalized_Score"],
            color=secondary_color,
            alpha=0.9,
        )
        ax.set_title("Top Fund Suggestions", fontsize=16, fontweight="bold", color="#10233f", fontfamily="DejaVu Serif")
        ax.set_xlabel("Personalized Score")
        ax.set_ylabel("Fund")
        ax.grid(axis="x", alpha=0.25)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        fig = plt.figure(figsize=(8.27, 11.69))
        fig.patch.set_facecolor("white")
        fig.text(0.08, 0.95, "Why These Funds Were Chosen", fontsize=18, **title_font)
        y = 0.9
        for idx, fund in enumerate(results["top_fund_reasons"][:3], start=1):
            fig.text(
                0.08,
                y,
                f"{idx}. {fund['name']}",
                fontsize=12.5,
                fontfamily="DejaVu Serif",
                fontweight="bold",
                color="#10233f",
            )
            y -= 0.022
            fig.text(
                0.1,
                y,
                f"{fund['subtype']} | {fund['risk_category']} | CAGR {fund['cagr']}% | Sharpe {fund['sharpe']}",
                fontsize=10,
                color=accent_color,
                fontfamily="DejaVu Sans",
            )
            y -= 0.03
            for item in fund["reasons"]:
                wrapped = textwrap.fill(f"- {item}", width=82)
                fig.text(0.11, y, wrapped, fontsize=10.2, **body_font)
                y -= 0.045
            y -= 0.02
        plt.axis("off")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    buffer.seek(0)
    return buffer.getvalue()


def render_admin_sidebar():
    with st.sidebar:
        st.markdown("## Admin Panel")
        if st.session_state.admin_mode:
            if st.button("Exit admin view", use_container_width=True):
                st.session_state.admin_mode = False
                st.session_state.admin_password_input = ""

            with st.expander("Admin Branding", expanded=False):
                st.session_state.brand_name = st.text_input(
                    "Application Name",
                    value=st.session_state.brand_name,
                )
                st.session_state.brand_tagline = st.text_input(
                    "Tagline",
                    value=st.session_state.brand_tagline,
                )
                st.session_state.brand_mark = st.text_input(
                    "Logo Mark",
                    value=st.session_state.brand_mark,
                    max_chars=3,
                )
                st.caption("Admin can edit the visible logo block here.")

            st.write("---")
            st.markdown("### Feedback Database")
            st.caption("View saved feedback entries in the admin dashboard.")
        else:
            st.text_input(
                "Admin password",
                type="password",
                key="admin_password_input",
            )
            if st.button("Enter admin", use_container_width=True):
                if st.session_state.admin_password_input == ADMIN_PASSWORD:
                    st.session_state.admin_mode = True
                else:
                    st.error("Invalid admin password.")


def render_admin_dashboard():
    render_top_bar()
    st.markdown("<div class='section-title'>Admin Dashboard</div>", unsafe_allow_html=True)
    feedback_entries = load_feedback_entries()
    st.markdown(
        f"<div class='panel'>Saved feedback entries: <strong>{len(feedback_entries)}</strong>.</div>",
        unsafe_allow_html=True,
    )
    if feedback_entries:
        st.dataframe(pd.DataFrame(feedback_entries), use_container_width=True)
    else:
        st.info("No feedback has been submitted yet.")


def render_top_bar():
    left, right = st.columns([5, 1])
    with left:
        logo_col, text_col = st.columns([1.1, 4.2])
        with logo_col:
            st.image(LOGO_IMAGE_PATH, width=110)
        with text_col:
            st.markdown(
                f"""
                <div style="padding-top:0.7rem;">
                    <div class="brand-text-top">{st.session_state.brand_tagline}</div>
                    <div class="brand-text-main">{st.session_state.brand_name}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with right:
        with st.popover("..."):
            st.markdown("### More")
            for label, url in APP_LINKS.items():
                st.markdown(f"- [{label}]({url})")
            st.caption("Replace these placeholder links with your actual dashboard, repository, FAQ, and project pages.")


def build_advisor_context(results):
    if results is None:
        return "No recommendation has been generated yet."

    age = results.get("age", "Not available")
    monthly_income = results.get("monthly_income", 0)
    investment_amount = results.get("investment_amount", 0)
    risk_appetite = results.get("risk_appetite", results.get("portfolio", "Not available"))
    goal = results.get("goal", "Not available")
    duration = results.get("duration", f"{results.get('years', 'Unknown')} years")
    market_sentiment = results.get("market_sentiment", "Not available")
    confidence_label = results.get("confidence_label", "Not available")
    summary = results.get("summary", "No summary available.")
    allocation_reasons = results.get("allocation_reasons", [])
    reasons = results.get("reasons", [])
    not_suitable = results.get("not_suitable", [])
    warnings = results.get("warnings", [])

    top_lines = []
    for idx, fund in enumerate(results.get("top_fund_reasons", [])[:3], start=1):
        top_lines.append(
            f"{idx}. {fund['name']} | {fund['subtype']} | {fund['risk_category']} | "
            f"Fit {fund['score'] * 100:.0f}% | CAGR {fund['cagr']}% | Sharpe {fund['sharpe']}"
        )
    filters = []
    if results.get("tax_saving"):
        filters.append("tax-saving filter on")
    if results.get("esg_preference"):
        filters.append("ESG filter on")
    filter_text = ", ".join(filters) if filters else "no extra filters"

    return "\n".join(
        [
            "Current recommendation context:",
            f"- Age: {age}",
            f"- Monthly income: Rs. {monthly_income:,}" if isinstance(monthly_income, (int, float)) else f"- Monthly income: {monthly_income}",
            f"- Investment amount: Rs. {investment_amount:,}" if isinstance(investment_amount, (int, float)) else f"- Investment amount: {investment_amount}",
            f"- Risk appetite selected: {risk_appetite}",
            f"- Goal: {goal}",
            f"- Duration: {duration}",
            f"- Market outlook: {market_sentiment}",
            f"- Portfolio outcome: {results['portfolio']}",
            f"- Suggested allocation: {results['equity']}% equity / {results['debt']}% debt",
            f"- Expected return range: {results['return_range'][0]}% to {results['return_range'][1]}%",
            f"- Confidence: {confidence_label}",
            f"- Filters: {filter_text}",
            f"- Summary: {summary}",
            "- Allocation reasoning:",
            *[f"  - {item}" for item in allocation_reasons[:4]],
            "- Recommendation reasoning:",
            *[f"  - {item}" for item in reasons[:4]],
            "- Suitability flags:",
            *[f"  - {item}" for item in warnings[:4]],
            "- Top funds:",
            *[f"  - {line}" for line in top_lines],
            "- Avoided categories:",
            *[f"  - {item}" for item in not_suitable[:3]],
        ]
    )


def build_suggested_questions(results, mode):
    if mode == "Learn Basics":
        return [
            "What is the difference between equity and debt funds?",
            "What is SIP and when is it useful?",
            "What does CAGR mean in simple words?",
        ]
    if mode == "Compare Options" and results is not None:
        top_names = [fund["name"] for fund in results["top_fund_reasons"][:2]]
        compare_text = " vs ".join(top_names) if len(top_names) == 2 else "my top two funds"
        return [
            f"Compare {compare_text}",
            "What changes if my duration becomes 10+ years?",
            "Why were some categories avoided for me?",
        ]
    return [
        "Why is my allocation suggested this way?",
        "Why was the top fund chosen for me?",
        "Should I think about SIP or lump sum for this profile?",
    ]


def lookup_finance_concept(query):
    concepts = {
        "sip": "SIP means investing a fixed amount regularly, usually every month. It is useful when you want discipline, easier budgeting, and less timing pressure than a one-time lump sum.",
        "lump sum": "A lump sum is a one-time investment. It can work when you already have capital ready, but short-term market timing matters more than with a SIP.",
        "elss": "ELSS is an equity-linked savings scheme. It is mainly used for tax-saving under Section 80C and has a lock-in period, so it is not suitable for short-term liquidity needs.",
        "cagr": "CAGR is the annualized growth rate over a period. It helps you understand long-term growth, but it does not show volatility or guarantee future returns.",
        "sharpe": "Sharpe ratio shows return earned relative to risk taken. A higher Sharpe ratio usually means the fund delivered returns more efficiently for the volatility it took.",
        "equity": "Equity funds invest more in stocks. They usually offer higher long-term growth potential, but they can fluctuate more in the short term.",
        "debt": "Debt funds invest in instruments like bonds and money-market securities. They are generally used for stability, lower volatility, and shorter horizons.",
        "large cap": "Large-cap funds invest in bigger, more established companies. They are usually more stable than mid-cap or small-cap funds, though growth may be more moderate.",
        "mid cap": "Mid-cap funds invest in medium-sized companies. They can offer stronger growth than large-cap funds, but they usually come with higher volatility.",
        "small cap": "Small-cap funds invest in smaller companies with high growth potential, but they are usually the most volatile and need a longer time horizon.",
        "risk": "Risk in mutual funds means how much the value can move up or down. Higher-growth categories usually have higher short-term volatility.",
    }
    for key, value in concepts.items():
        if key in query:
            return value
    return None


def find_referenced_funds(query, results):
    if results is None:
        return []
    query_tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    matches = []
    for fund in results["top_fund_reasons"]:
        fund_tokens = set(re.findall(r"[a-z0-9]+", fund["name"].lower()))
        if len(query_tokens & fund_tokens) >= 2:
            matches.append(fund)
    return matches


def build_local_advisor_reply(question, results):
    query = question.lower().strip()
    if not query:
        return "Ask about your allocation, top funds, risk, SIP vs lump sum, or any mutual fund basic."

    concept_reply = lookup_finance_concept(query)

    if results is None:
        if concept_reply:
            return concept_reply
        return (
            "I can explain mutual fund basics now, and after you generate a recommendation I can answer in a more personalized way "
            "about your allocation, top funds, and why they were selected."
        )

    referenced_funds = find_referenced_funds(query, results)
    if "compare" in query and len(results["top_fund_reasons"]) >= 2:
        fund_a = results["top_fund_reasons"][0]
        fund_b = results["top_fund_reasons"][1]
        return (
            f"{fund_a['name']} is the stronger overall fit right now because it ranks first for your profile. "
            f"It is in {fund_a['subtype']} and was selected for reasons like {fund_a['reasons'][0].lower()}. "
            f"{fund_b['name']} is still relevant, but it ranks slightly lower for your goal and horizon."
        )

    if referenced_funds:
        fund = referenced_funds[0]
        return (
            f"{fund['name']} was shortlisted because {fund['reasons'][0].lower()}, {fund['reasons'][1].lower()}, "
            f"and it also brings quality signals like CAGR {fund['cagr']}% and Sharpe ratio {fund['sharpe']}."
        )

    if any(word in query for word in ["allocation", "equity", "debt", "split", "portfolio"]):
        return (
            f"Quick answer: your current mix is {results['equity']}% equity and {results['debt']}% debt. "
            f"Why this fits you: your selected risk appetite is {results['risk_appetite'].lower()}, your goal is {results['goal'].lower()}, "
            f"and your duration is {results['duration'].lower()}. "
            f"Main drivers were: {results['allocation_reasons'][0]} {results['allocation_reasons'][1]}"
        )

    if any(word in query for word in ["risk", "safe", "aggressive", "moderate", "conservative"]):
        return (
            f"Your final portfolio outcome is {results['portfolio']}, while your selected risk appetite was {results['risk_appetite']}. "
            f"The app adjusts that base choice using age, duration, goal, and market outlook before deciding the final allocation."
        )

    if any(word in query for word in ["return", "growth", "future", "value"]):
        return (
            f"The app estimates a return range of {results['return_range'][0]}% to {results['return_range'][1]}% a year, "
            f"with a projected value range of Rs. {results['future_value_low']:,.0f} to Rs. {results['future_value_high']:,.0f} over {results['years']} years. "
            "This is only a planning range, not a guaranteed result."
        )

    if any(word in query for word in ["top fund", "which fund", "recommended fund", "best fund"]):
        top_fund = results["top_fund_reasons"][0]
        return (
            f"Your top current pick is {top_fund['name']}. It stands out because {top_fund['reasons'][0].lower()}, "
            f"{top_fund['reasons'][1].lower()}, and it also has CAGR {top_fund['cagr']}% with Sharpe ratio {top_fund['sharpe']}."
        )

    if any(word in query for word in ["why", "reason", "chosen", "selected"]):
        top_fund = results["top_fund_reasons"][0]
        return (
            f"The shortlist is built from your risk, goal, duration, and market outlook. "
            f"For example, {top_fund['name']} was selected because {top_fund['reasons'][0].lower()} and {top_fund['reasons'][1].lower()}."
        )

    if any(word in query for word in ["avoid", "rejected", "not selected", "why not"]):
        return "The app avoided these areas for your profile: " + " ".join(results["not_suitable"][:2])

    if any(word in query for word in ["sip", "lump sum"]):
        sip_line = lookup_finance_concept("sip") or ""
        duration = results.get("duration", "")
        if duration in ["1-3 Years", "3-5 Years"]:
            extra = "For your current horizon, regular SIP-style investing can reduce timing pressure."
        else:
            extra = "For a longer horizon, either SIP or phased investing can work if you want smoother market entry."
        return f"{sip_line} {extra}"

    if any(word in query for word in ["what if", "instead", "change", "becomes", "become"]):
        return (
            "I can explain likely changes even without recalculating live. In general, a longer duration or more aggressive risk appetite "
            "would move the mix toward more equity, while a shorter goal horizon or emergency-focused goal would move it toward more debt."
        )

    if concept_reply:
        return concept_reply

    return (
        "I can answer this in a beginner-friendly way. Try asking about allocation, top fund reasons, risk level, SIP vs lump sum, "
        "CAGR, Sharpe ratio, or why some categories were avoided."
    )


def generate_chat_reply(question, results):
    def try_openai_chat(user_question, recommendation_results):
        api_key = (OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")).strip()
        if not api_key:
            return None

        system_prompt = (
            "You are a beginner-friendly mutual fund advisor assistant inside an investment recommendation app. "
            "Explain things simply, keep answers practical, and use the recommendation context when it is available. "
            "Do not guarantee returns. Do not invent fund facts. If the answer depends on the user's profile, say why. "
            "Prefer this structure when useful: Quick answer, Why this matters for you, What you can do next."
        )

        messages = [{"role": "system", "content": system_prompt}]
        if recommendation_results is not None:
            messages.append({"role": "system", "content": build_advisor_context(recommendation_results)})

        for message in st.session_state.chat_messages[-6:]:
            messages.append({"role": message["role"], "content": message["content"]})
        messages.append({"role": "user", "content": user_question})

        try:
            payload = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "temperature": 0.35,
            }
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None

    def try_web_lookup(raw_query):
        try:
            url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
                {"q": raw_query, "format": "json", "no_html": 1, "skip_disambig": 1}
            )
            with urllib.request.urlopen(url, timeout=4) as response:
                payload = json.loads(response.read().decode("utf-8"))
            abstract = payload.get("AbstractText", "").strip()
            if abstract:
                return "Small public-web note: " + abstract
            for item in payload.get("RelatedTopics", []):
                if isinstance(item, dict) and item.get("Text"):
                    return "Small public-web note: " + item["Text"]
        except Exception:
            return None
        return None

    openai_reply = try_openai_chat(question, results)
    if openai_reply:
        return openai_reply

    local_reply = build_local_advisor_reply(question, results)
    if results is not None:
        return local_reply

    web_note = try_web_lookup(question)
    if web_note:
        return f"{local_reply}\n\n{web_note}"
    return local_reply


def render_advisor_chat(results):
    result_signature = None
    if results is not None:
        result_signature = (
            results["portfolio"],
            results["equity"],
            results["debt"],
            results.get("goal"),
            results.get("duration"),
            results.get("market_sentiment"),
        )

    if result_signature != st.session_state.chat_result_signature:
        st.session_state.chat_result_signature = result_signature
        st.session_state.chat_messages = [
            {
                "role": "assistant",
                "content": (
                    "I am ready to explain your recommendation. Ask why the allocation was chosen, why a fund was selected, "
                    "what was avoided, or any mutual fund basic you want to understand."
                    if results is not None
                    else "Ask any beginner mutual fund question. Once you generate a recommendation, I can answer in a personalized way too."
                ),
            }
        ]

    st.markdown(
        """
        <div class="action-dock">
            <div class="action-dock-title">Actions & AI Help</div>
            <div class="action-dock-copy">Use the assistant to understand the recommendation, or export the current report as a PDF.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div class='chat-fab'>", unsafe_allow_html=True)
    fab_col1, fab_col2 = st.columns([1.15, 1], gap="small")
    with fab_col1:
        with st.popover("Ask AI"):
            st.markdown("### Advisor Assistant")
            st.caption("Use it to understand your recommendation, learn mutual fund basics, or compare options in simple language.")
            st.session_state.chat_mode = st.radio(
                "Assistant mode",
                ["Explain My Plan", "Learn Basics", "Compare Options"],
                horizontal=True,
                key="advisor_mode_picker",
                index=["Explain My Plan", "Learn Basics", "Compare Options"].index(st.session_state.chat_mode),
            )

            st.markdown("**Try one of these:**")
            suggestion_cols = st.columns(3)
            for idx, suggestion in enumerate(build_suggested_questions(results, st.session_state.chat_mode)):
                with suggestion_cols[idx]:
                    if st.button(suggestion, key=f"chat_suggestion_{idx}", use_container_width=True):
                        st.session_state.chat_messages.append({"role": "user", "content": suggestion})
                        reply = generate_chat_reply(suggestion, results)
                        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                        st.rerun()

            for message in st.session_state.chat_messages[-6:]:
                with st.chat_message(message["role"]):
                    st.write(message["content"])

            if st.button("Clear", key="clear_chat_history", use_container_width=True):
                st.session_state.chat_messages = [
                    {
                        "role": "assistant",
                        "content": "Chat cleared. Ask your next question whenever you are ready.",
                    }
                ]
                st.rerun()

            user_prompt = st.chat_input("Ask about allocation, risk, SIP, top funds, or mutual fund basics")
            if user_prompt:
                st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
                reply = generate_chat_reply(user_prompt, results)
                st.session_state.chat_messages.append({"role": "assistant", "content": reply})
                st.rerun()
    with fab_col2:
        if results is not None:
            pdf_bytes = build_pdf_report(results)
            st.download_button(
                "Download PDF",
                data=pdf_bytes,
                file_name="mutual_fund_recommendation.pdf",
                mime="application/pdf",
                key="advisor_pdf_download",
                use_container_width=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


def _calculate_recommendation_core(
    age,
    monthly_income,
    risk_appetite,
    investment_amount,
    monthly_sip,
    duration,
    financial_goal,
    tax_saving,
    esg_preference,
    market_sentiment,
    risk_quiz_score,
    risk_quiz_label,
):
    def add_keyword_bonus(frame, column, keywords, bonus):
        if not keywords:
            return 0
        pattern = "|".join(keywords)
        return frame[column].str.contains(pattern, case=False, na=False).astype(int) * bonus

    def clamp(value, low, high):
        return max(low, min(high, value))

    def subtype_mask(frame, subtypes):
        if not subtypes:
            return pd.Series([True] * len(frame), index=frame.index)
        return frame["SubType"].isin(subtypes)

    def build_fund_reason(row, financial_goal, duration, market_sentiment, risk_filter):
        reasons = []

        if row["Risk_Category"] == risk_filter:
            reasons.append(f"Matches your {risk_filter.lower()} risk bucket")
        else:
            reasons.append("Included as a nearest available dataset match")

        reasons.append(f"{row['SubType']} subtype fits your {financial_goal.lower()} goal")
        reasons.append(f"Works with your {duration.lower()} investment horizon")

        if market_sentiment == "Bullish" and row["SubType"] in ["Mid Cap", "Small Cap", "Aggressive Hybrid", "ELSS"]:
            reasons.append("Higher-growth profile aligns with your bullish outlook")
        elif market_sentiment == "Bearish" and row["SubType"] in ["Liquid", "Corporate Bond", "Dynamic Asset Allocation", "Large Cap"]:
            reasons.append("More defensive category aligns with your bearish outlook")
        elif market_sentiment == "Neutral" and row["SubType"] in ["Large Cap", "Nifty 50", "Dynamic Asset Allocation"]:
            reasons.append("Balanced category suits your neutral market outlook")

        reasons.append(f"AI score {row['AI_Score']:.3f} with CAGR {row['CAGR']:.2f}% and Sharpe ratio {row['Sharpe_Ratio']:.2f}")
        return reasons[:4]

    def confidence_label(level):
        mapping = {
            "High": "High confidence",
            "Medium": "Medium confidence",
            "Low": "Low confidence",
        }
        return mapping[level]

    def with_article(word):
        return f"an {word}" if word[:1].lower() in "aeiou" else f"a {word}"

    base_equity_map = {
        "Conservative": 30,
        "Moderate": 55,
        "Aggressive": 75,
    }
    equity = base_equity_map[risk_appetite]
    profile_adjustments = []

    if age < 30:
        equity += 5
        profile_adjustments.append("younger age supports slightly higher equity")
    elif age >= 50:
        equity -= 10
        profile_adjustments.append("higher age reduces equity exposure")

    duration_adjustments = {
        "1-3 Years": -15,
        "3-5 Years": -5,
        "5-10 Years": 5,
        "10+ Years": 10,
    }
    equity += duration_adjustments[duration]
    if duration_adjustments[duration] != 0:
        profile_adjustments.append(f"{duration} horizon changes equity by {duration_adjustments[duration]} points")

    goal_adjustments = {
        "Retirement": 0,
        "Child Education": 0,
        "Buying House": -10,
        "Wealth Creation": 10,
        "Emergency Fund": -20,
    }
    equity += goal_adjustments[financial_goal]
    if goal_adjustments[financial_goal] != 0:
        profile_adjustments.append(
            f"{financial_goal.lower()} goal changes equity by {goal_adjustments[financial_goal]} points"
        )

    sentiment_adjustments = {
        "Bullish": 5,
        "Neutral": 0,
        "Bearish": -5,
    }
    equity += sentiment_adjustments[market_sentiment]
    if sentiment_adjustments[market_sentiment] != 0:
        profile_adjustments.append(
            f"{market_sentiment.lower()} outlook changes equity by {sentiment_adjustments[market_sentiment]} points"
        )

    if monthly_income >= 100000 and risk_appetite == "Aggressive":
        equity += 5
        profile_adjustments.append("higher income allows slightly more growth exposure")

    declared_risk_score = {
        "Conservative": 1,
        "Moderate": 2,
        "Aggressive": 3,
    }[risk_appetite]
    quiz_delta = risk_quiz_score - declared_risk_score
    if quiz_delta != 0:
        equity += quiz_delta * 5
        if quiz_delta > 0:
            profile_adjustments.append(
                f"risk quiz answers were slightly more growth-oriented than your selected risk appetite"
            )
        else:
            profile_adjustments.append(
                f"risk quiz answers were slightly more cautious than your selected risk appetite"
            )

    equity = clamp(equity, 20, 85)
    debt = 100 - equity

    risk_score = round((equity - 20) / 13)

    if equity >= 70:
        portfolio = "Aggressive"
        ret = 14
        risk_filter = "Aggressive"
    elif equity >= 45:
        portfolio = "Balanced"
        ret = 11
        risk_filter = "Moderate"
    else:
        portfolio = "Conservative"
        ret = 8
        risk_filter = "Conservative"

    years_map = {
        "1-3 Years": 3,
        "3-5 Years": 5,
        "5-10 Years": 10,
        "10+ Years": 15,
    }

    years = years_map[duration]
    return_band = {
        "Conservative": (6, 9),
        "Balanced": (9, 12),
        "Aggressive": (12, 15),
    }
    low_ret, high_ret = return_band[portfolio]
    future_value = investment_amount * ((1 + ret / 100) ** years)
    future_value_low = investment_amount * ((1 + low_ret / 100) ** years)
    future_value_high = investment_amount * ((1 + high_ret / 100) ** years)

    allocation_reasons = [
        f"Your selected risk appetite starts the portfolio near {base_equity_map[risk_appetite]}% equity.",
        f"After profile adjustments, the suggested mix becomes {equity}% equity and {debt}% debt.",
        f"This maps to a {portfolio.lower()} portfolio with an expected return assumption of {ret}%.",
    ]
    allocation_reasons.extend(profile_adjustments[:3])
    if market_sentiment == "Bullish":
        allocation_reasons.append("Bullish outlook slightly increases equity exposure.")
    elif market_sentiment == "Bearish":
        allocation_reasons.append("Bearish outlook reduces equity exposure and increases debt allocation.")

    ranked_df = df.copy()
    ranked_df["match_score"] = 0.0

    risk_preferences = {
        "Conservative": ["Liquid", "Corporate Bond", "Dynamic Asset Allocation", "Large Cap"],
        "Moderate": ["Dynamic Asset Allocation", "Aggressive Hybrid", "Large Cap", "Nifty 50", "ELSS"],
        "Aggressive": ["Mid Cap", "Small Cap", "ELSS", "Large Cap"],
    }
    duration_preferences = {
        "1-3 Years": ["Liquid", "Corporate Bond", "Dynamic Asset Allocation"],
        "3-5 Years": ["Corporate Bond", "Dynamic Asset Allocation", "Large Cap", "Nifty 50"],
        "5-10 Years": ["Large Cap", "Nifty 50", "Aggressive Hybrid", "Mid Cap", "ELSS"],
        "10+ Years": ["Large Cap", "Mid Cap", "Small Cap", "ELSS", "Aggressive Hybrid"],
    }
    goal_preferences = {
        "Retirement": ["Dynamic Asset Allocation", "Aggressive Hybrid", "Large Cap", "Nifty 50"],
        "Child Education": ["Large Cap", "Nifty 50", "Aggressive Hybrid", "Mid Cap"],
        "Buying House": ["Liquid", "Corporate Bond", "Dynamic Asset Allocation", "Large Cap"],
        "Wealth Creation": ["Mid Cap", "Small Cap", "Large Cap", "ELSS"],
        "Emergency Fund": ["Liquid", "Corporate Bond", "Dynamic Asset Allocation"],
    }
    sentiment_preferences = {
        "Bullish": ["Mid Cap", "Small Cap", "Aggressive Hybrid", "ELSS"],
        "Neutral": ["Large Cap", "Nifty 50", "Dynamic Asset Allocation"],
        "Bearish": ["Liquid", "Corporate Bond", "Dynamic Asset Allocation", "Large Cap"],
    }

    preferred_subtypes = []
    for group in (
        risk_preferences[risk_appetite],
        duration_preferences[duration],
        goal_preferences[financial_goal],
        sentiment_preferences[market_sentiment],
    ):
        for subtype in group:
            if subtype not in preferred_subtypes:
                preferred_subtypes.append(subtype)

    strict_subtypes = [
        subtype
        for subtype in preferred_subtypes
        if subtype in duration_preferences[duration] and subtype in goal_preferences[financial_goal]
    ]
    if not strict_subtypes:
        strict_subtypes = [
            subtype
            for subtype in preferred_subtypes
            if subtype in risk_preferences[risk_appetite] and subtype in goal_preferences[financial_goal]
        ]

    ranked_df["match_score"] += (ranked_df["Risk_Category"] == risk_filter).astype(int) * 4.0
    ranked_df["match_score"] += add_keyword_bonus(
        ranked_df,
        "SubType",
        risk_preferences[risk_appetite],
        2.2,
    )
    ranked_df["match_score"] += add_keyword_bonus(
        ranked_df,
        "SubType",
        duration_preferences[duration],
        2.0,
    )
    ranked_df["match_score"] += add_keyword_bonus(
        ranked_df,
        "SubType",
        goal_preferences[financial_goal],
        2.6,
    )
    ranked_df["match_score"] += add_keyword_bonus(
        ranked_df,
        "SubType",
        sentiment_preferences[market_sentiment],
        1.4,
    )
    ranked_df["match_score"] += add_keyword_bonus(
        ranked_df,
        "SubType",
        strict_subtypes,
        3.2,
    )

    ranked_df["quality_score"] = (
        ranked_df["AI_Score"].rank(pct=True) * 0.5
        + ranked_df["Sharpe_Ratio"].rank(pct=True) * 0.25
        + ranked_df["CAGR"].rank(pct=True) * 0.15
        + ranked_df["Forecast_Return"].rank(pct=True) * 0.10
    )

    if monthly_income >= 100000 and risk_appetite == "Aggressive":
        ranked_df["match_score"] += add_keyword_bonus(
            ranked_df,
            "SubType",
            ["Mid Cap", "Small Cap"],
            0.8,
        )

    filtered_df = ranked_df[
        (ranked_df["Risk_Category"] == risk_filter)
        & subtype_mask(ranked_df, strict_subtypes if strict_subtypes else preferred_subtypes)
    ].copy()
    used_fallback = False
    confidence = "High"

    if tax_saving:
        filtered_df = filtered_df[
            filtered_df["SubType"].str.contains("ELSS", case=False, na=False)
        ]

    if esg_preference:
        filtered_df = filtered_df[
            filtered_df["Actual_Fund_Name"].str.contains("ESG", case=False, na=False)
        ]

    if filtered_df.empty:
        filtered_df = ranked_df[
            (ranked_df["Risk_Category"] == risk_filter)
            & subtype_mask(ranked_df, preferred_subtypes)
        ].copy()
        fallback_note = "No exact subtype match found. Showing closest funds for your profile."
        confidence = "Medium"

    if filtered_df.empty:
        filtered_df = ranked_df[ranked_df["Risk_Category"] == risk_filter].copy()
        fallback_note = "Limited matches in the dataset. Showing best funds in your risk bucket."
        used_fallback = True
        confidence = "Low"

    if filtered_df.empty:
        filtered_df = ranked_df.copy()
        fallback_note = "Dataset match was too limited. Showing highest ranked funds overall."
        used_fallback = True
        confidence = "Low"

    max_match_score = max(ranked_df["match_score"].max(), 1)
    filtered_df["Profile_Match_Score"] = filtered_df["match_score"] / max_match_score
    filtered_df["Personalized_Score"] = (
        filtered_df["quality_score"] * 0.55 + filtered_df["Profile_Match_Score"] * 0.45
    )
    filtered_df = filtered_df.sort_values(
        by=["Personalized_Score", "AI_Score", "CAGR"],
        ascending=False,
    ).head(5)
    if not used_fallback:
        fallback_note = "Recommendations are aligned with your risk profile and filters."
    if (tax_saving or esg_preference) and not used_fallback:
        fallback_note += " Preference filters were applied."

    rejected_categories = []
    for subtype in ["Liquid", "Corporate Bond", "Dynamic Asset Allocation", "Large Cap", "Nifty 50", "Aggressive Hybrid", "ELSS", "Mid Cap", "Small Cap"]:
        if subtype not in filtered_df["SubType"].unique().tolist():
            if subtype not in preferred_subtypes:
                rejected_categories.append(subtype)

    not_suitable = []
    if portfolio == "Conservative":
        not_suitable.extend(
            [
                "Small Cap and Mid Cap were avoided because your profile needs lower volatility.",
                "Pure high-growth categories were deprioritized to protect near-term capital.",
            ]
        )
    elif portfolio == "Balanced":
        not_suitable.extend(
            [
                "Very defensive categories were not prioritized because your profile can take moderate growth exposure.",
                "The shortlist avoids extreme risk on either side and stays near diversified categories.",
            ]
        )
    else:
        not_suitable.extend(
            [
                "Low-growth liquid and short-duration debt options were deprioritized because your profile can handle more equity.",
                "The shortlist favors long-term growth categories over capital-preservation funds.",
            ]
        )

    projection_df = pd.DataFrame(
        {
            "Year": list(range(0, years + 1)),
            "Projected Value": [
                investment_amount * ((1 + ret / 100) ** year)
                for year in range(0, years + 1)
            ],
        }
    )

    sip_projection_df = build_sip_projection(monthly_sip, ret, years)
    sip_projection_alt_df = build_sip_projection(monthly_sip, high_ret, years)
    sip_future_value = float(sip_projection_df["Projected Value"].iloc[-1]) if not sip_projection_df.empty else 0.0
    sip_future_value_high = (
        float(sip_projection_alt_df["Projected Value"].iloc[-1]) if not sip_projection_alt_df.empty else 0.0
    )

    allocation_df = pd.DataFrame(
        {"Asset": ["Equity", "Debt"], "Share": [equity, debt]}
    )

    reasons = [
        f"Your inputs map to a {portfolio.lower()} investor profile.",
        f"Funds were shortlisted using your goal, duration, market outlook, and matching risk category.",
        f"Allocation is kept at {equity}% equity and {debt}% debt to stay consistent with that profile.",
    ]

    if tax_saving:
        reasons.append("Tax-saving preference applied through ELSS-focused filtering.")
    if esg_preference:
        reasons.append("ESG preference applied to keep the shortlist aligned with sustainability.")
    if market_sentiment != "Neutral":
        reasons.append(
            f"Market outlook marked as {market_sentiment.lower()}, which slightly influenced portfolio posture."
        )
    reasons.append(
        f"Risk quiz result was {risk_quiz_label.lower()}, which was used as a cross-check before finalizing the allocation."
    )

    warnings = build_suitability_flags(
        goal=financial_goal,
        duration=duration,
        tax_saving=tax_saving,
        esg_preference=esg_preference,
        market_sentiment=market_sentiment,
        portfolio=portfolio,
        equity=equity,
    )
    estimated_volatility = estimate_portfolio_volatility(filtered_df, equity, debt)
    volatility_label = classify_volatility(estimated_volatility)

    top_fund_reasons = []
    for _, row in filtered_df.iterrows():
        top_fund_reasons.append(
            {
                "name": row["Actual_Fund_Name"],
                "subtype": row["SubType"],
                "risk_category": row["Risk_Category"],
                "score": round(float(row["Personalized_Score"]), 3),
                "cagr": round(float(row["CAGR"]), 2),
                "sharpe": round(float(row["Sharpe_Ratio"]), 2),
                "reasons": build_fund_reason(
                    row,
                    financial_goal=financial_goal,
                    duration=duration,
                    market_sentiment=market_sentiment,
                    risk_filter=risk_filter,
                ),
            }
        )

    return {
        "portfolio": portfolio,
        "equity": equity,
        "debt": debt,
        "ret": ret,
        "return_range": (low_ret, high_ret),
        "risk_score": risk_score,
        "years": years,
        "estimated_volatility": estimated_volatility,
        "volatility_label": volatility_label,
        "future_value": future_value,
        "future_value_low": future_value_low,
        "future_value_high": future_value_high,
        "monthly_sip": monthly_sip,
        "sip_projection_df": sip_projection_df,
        "sip_future_value": sip_future_value,
        "sip_future_value_high": sip_future_value_high,
        "filtered_df": filtered_df,
        "projection_df": projection_df,
        "allocation_df": allocation_df,
        "allocation_reasons": allocation_reasons,
        "fallback_note": fallback_note,
        "confidence": confidence,
        "confidence_label": confidence_label(confidence),
        "not_suitable": not_suitable,
        "warnings": warnings,
        "reasons": reasons,
        "top_fund_reasons": top_fund_reasons,
        "age": age,
        "monthly_income": monthly_income,
        "risk_appetite": risk_appetite,
        "risk_quiz_score": risk_quiz_score,
        "risk_quiz_label": risk_quiz_label,
        "goal": financial_goal,
        "duration": duration,
        "market_sentiment": market_sentiment,
        "tax_saving": tax_saving,
        "esg_preference": esg_preference,
        "investment_amount": investment_amount,
        "refine_min_return": None,
        "refine_max_volatility": None,
        "is_refined": False,
        "refined_from_risk_appetite": None,
        "refinement_note": "",
        "summary": (
            f"You fit {with_article(portfolio.lower())} profile. The app is suggesting funds in categories that match your "
            f"{financial_goal.lower()} goal and {duration.lower()} horizon, with a target allocation of "
            f"{equity}% equity and {debt}% debt."
        ),
        "comparison_snapshots": [],
    }


def calculate_recommendation(
    age,
    monthly_income,
    risk_appetite,
    investment_amount,
    monthly_sip,
    duration,
    financial_goal,
    tax_saving,
    esg_preference,
    market_sentiment,
    risk_quiz_score,
    risk_quiz_label,
    refine_min_return=None,
    refine_max_volatility=None,
):
    inputs = {
        "age": age,
        "monthly_income": monthly_income,
        "risk_appetite": risk_appetite,
        "investment_amount": investment_amount,
        "monthly_sip": monthly_sip,
        "duration": duration,
        "financial_goal": financial_goal,
        "tax_saving": tax_saving,
        "esg_preference": esg_preference,
        "market_sentiment": market_sentiment,
        "risk_quiz_score": risk_quiz_score,
        "risk_quiz_label": risk_quiz_label,
    }
    base_result = _calculate_recommendation_core(**inputs)

    requested_refine = refine_min_return is not None or refine_max_volatility is not None
    if not requested_refine:
        return base_result

    def candidate_penalty(candidate):
        mid_return = sum(candidate["return_range"]) / 2
        penalty = 0.0
        if refine_min_return is not None:
            penalty += max(0.0, refine_min_return - mid_return) * 4
        if refine_max_volatility is not None:
            penalty += max(0.0, candidate["estimated_volatility"] - refine_max_volatility) * 4
        penalty += abs(mid_return - sum(base_result["return_range"]) / 2) * 0.2
        penalty += abs(candidate["estimated_volatility"] - base_result["estimated_volatility"]) * 0.15
        if candidate["risk_appetite"] != risk_appetite:
            penalty += 0.1
        return penalty

    candidates = []
    for candidate_risk in ["Conservative", "Moderate", "Aggressive"]:
        candidate = _calculate_recommendation_core(
            **{**inputs, "risk_appetite": candidate_risk}
        )
        candidate["refine_min_return"] = refine_min_return
        candidate["refine_max_volatility"] = refine_max_volatility
        candidates.append(candidate)

    best_result = min(candidates, key=candidate_penalty)
    best_result["is_refined"] = best_result["risk_appetite"] != risk_appetite
    best_result["refined_from_risk_appetite"] = risk_appetite if best_result["is_refined"] else None
    best_result["refine_min_return"] = refine_min_return
    best_result["refine_max_volatility"] = refine_max_volatility

    refinement_notes = []
    if refine_min_return is not None:
        refinement_notes.append(f"targeting at least {refine_min_return:.1f}% expected annual return")
    if refine_max_volatility is not None:
        refinement_notes.append(f"keeping estimated volatility near or below {refine_max_volatility:.1f}%")

    if best_result["is_refined"]:
        best_result["refinement_note"] = (
            f"Recommendation refined from {risk_appetite.lower()} to {best_result['risk_appetite'].lower()} "
            f"by {' and '.join(refinement_notes)}."
        )
    else:
        best_result["refinement_note"] = (
            f"Current profile already stayed closest to your requested refinement by {' and '.join(refinement_notes)}."
        )

    return best_result


render_admin_sidebar()


if st.session_state.admin_mode:
    render_admin_dashboard()
elif st.session_state.page == "home":
    render_top_bar()
    st.markdown(
        """
        <div class="hero">
            <h1>Welcome to Your Beginner-Friendly Mutual Fund Guide</h1>
            <p>Get a simple view of risk, allocation, fund types, and possible outcomes before investing.</p>
            <div class="hero-strip">
                <span class="hero-chip">Made for first-time investors</span>
                <span class="hero-chip">Quick portfolio overview</span>
                <span class="hero-chip">Simple fund reasoning</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    feature_cols = st.columns(4)
    with feature_cols[0]:
        info_card(
            "Why This Exists",
            "Turns mutual fund choices into a simple beginner-friendly overview.",
        )
    with feature_cols[1]:
        info_card(
            "Useful For Beginners",
            "Explains risk, allocation, and fund types in simple terms.",
        )
    with feature_cols[2]:
        info_card(
            "What You Will See",
            "Shows allocation, top funds, and projected outcomes.",
        )
    with feature_cols[3]:
        info_card(
            "How It Helps",
            "Matches your goal and timeline with a clearer investment path.",
        )

    st.markdown("<div class='section-title'>What This Application Does For You</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="panel">
            The app is designed as a beginner-friendly mutual fund companion. It does not expect the user to already know
            the difference between aggressive, balanced, and conservative investing. Instead, it translates profile inputs
            into a clear overview so users can understand what kind of investment path may suit them and why.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-title'>How It Works</div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="panel">
            <div style="display: flex; flex-direction: column; gap: 1rem;">
                <div style="display: flex; align-items: flex-start; gap: 1rem;">
                    <div style="background: #34d399; color: white; padding: 0.5rem; border-radius: 50%; font-weight: bold; min-width: 2rem; text-align: center;">1</div>
                    <div>
                        <strong>Quick Risk Assessment</strong><br/>
                        Answer 4 simple questions to understand your risk tolerance and investment style.
                    </div>
                </div>
                <div style="display: flex; align-items: flex-start; gap: 1rem;">
                    <div style="background: #34d399; color: white; padding: 0.5rem; border-radius: 50%; font-weight: bold; min-width: 2rem; text-align: center;">2</div>
                    <div>
                        <strong>Personalized Profile</strong><br/>
                        Share your age, income, goals, and preferences to get tailored recommendations.
                    </div>
                </div>
                <div style="display: flex; align-items: flex-start; gap: 1rem;">
                    <div style="background: #34d399; color: white; padding: 0.5rem; border-radius: 50%; font-weight: bold; min-width: 2rem; text-align: center;">3</div>
                    <div>
                        <strong>Smart Analysis</strong><br/>
                        Our AI analyzes thousands of funds using advanced algorithms to find your best matches.
                    </div>
                </div>
                <div style="display: flex; align-items: flex-start; gap: 1rem;">
                    <div style="background: #34d399; color: white; padding: 0.5rem; border-radius: 50%; font-weight: bold; min-width: 2rem; text-align: center;">4</div>
                    <div>
                        <strong>Clear Results</strong><br/>
                        Get simple explanations, fund comparisons, and projected outcomes you can understand.
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-title'>Key Features</div>", unsafe_allow_html=True)
    feature_cols = st.columns(3)
    with feature_cols[0]:
        st.markdown(
            """
            <div class="panel" style="text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🎯</div>
                <strong>Goal-Based Matching</strong><br/>
                Recommendations tailored to your specific financial goals and timeline.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with feature_cols[1]:
        st.markdown(
            """
            <div class="panel" style="text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">📊</div>
                <strong>Risk Assessment</strong><br/>
                Understand your risk tolerance with a simple quiz and get appropriate allocations.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with feature_cols[2]:
        st.markdown(
            """
            <div class="panel" style="text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">🤖</div>
                <strong>AI-Powered Analysis</strong><br/>
                Advanced algorithms analyze fund performance, volatility, and market data.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown(
        """
        <style>
            .stButton > button,
            button[data-baseweb="button"] {
                font-size: 1.5rem !important;
                font-weight: 800 !important;
                padding: 1.4rem 1.8rem !important;
                min-height: 3.2rem !important;
                letter-spacing: 0.02em !important;
                border-radius: 1rem !important;
                box-shadow: 0 16px 36px rgba(15, 23, 42, 0.22) !important;
                background: linear-gradient(135deg, #10b981 0%, #0ea5e9 100%) !important;
                color: #ffffff !important;
                border: none !important;
            }
            .stButton > button:hover,
            button[data-baseweb="button"]:hover {
                filter: brightness(1.05) !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
    button_cols = st.columns([1, 0.75, 1])
    with button_cols[1]:
        if st.button("Start Recommendation", use_container_width=True, key="home_start"):
            st.session_state.page = "quiz"
            st.rerun()

    st.markdown("<div class='section-title'>Frequently Asked Questions</div>", unsafe_allow_html=True)
    with st.expander("Is this financial advice?"):
        st.write("No, this is an educational tool to help you understand mutual fund options. Always consult a certified financial advisor before making investment decisions.")
    
    with st.expander("How accurate are the recommendations?"):
        st.write("The recommendations are based on historical data and statistical analysis. Past performance doesn't guarantee future results. Market conditions can change.")
    
    with st.expander("Can I invest directly through this app?"):
        st.write("No, this app provides educational recommendations only. You'll need to use a brokerage account or mutual fund platform to make actual investments.")
    
    with st.expander("What data sources do you use?"):
        st.write("We use publicly available mutual fund data, historical performance metrics, and market analysis. All data is for educational purposes.")
    
    with st.expander("What metrics are used and what do they mean?"):
        st.markdown(
            """
            - **CAGR**: Compound Annual Growth Rate, the average annual return over the selected horizon.
            - **Sharpe Ratio**: A measure of how much return you get for each unit of risk taken.
            - **Fit Score**: How well the fund matches your profile, goals and risk preference.
            - **Return Range**: The estimated yearly return band the portfolio is expected to deliver.
            - **Volatility**: The estimated amount the portfolio value may move up or down.
            - **Projected Value Range**: The possible future value of your investment over the chosen time period.
            """,
        )

elif st.session_state.page == "quiz":
    render_top_bar()
    st.markdown(
        """
        <div class="hero">
            <h1>Personalize Your Recommendation</h1>
            <p>Answer a few quick questions first. This helps the app understand how much risk and volatility you may actually be comfortable with.</p>
            <div class="hero-strip">
                <span class="hero-chip">4 quick questions</span>
                <span class="hero-chip">Better personalization</span>
                <span class="hero-chip">Beginner-friendly flow</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("risk_quiz_form"):
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Risk Personalization Quiz</div>", unsafe_allow_html=True)
        quiz_left, quiz_right = st.columns(2)

        with quiz_left:
            risk_reaction = st.selectbox(
                "If markets fall 15%, what will you do?",
                ["Sell quickly", "Wait and watch", "Invest more if possible"],
            )
            investment_style = st.selectbox(
                "Which outcome matters more?",
                ["Capital safety", "Balanced growth", "Maximum long-term growth"],
            )

        with quiz_right:
            time_commitment = st.selectbox(
                "How long can you stay invested without needing the money?",
                ["Less than 3 years", "Around 5 years", "10 years or more"],
            )
            return_expectation = st.selectbox(
                "What kind of return journey are you comfortable with?",
                ["Stable but lower returns", "Some ups and downs", "High volatility for higher growth"],
            )

        quiz_back, quiz_continue = st.columns([1, 1])
        with quiz_back:
            back_clicked = st.form_submit_button("Back to Home", use_container_width=True)
        with quiz_continue:
            continue_clicked = st.form_submit_button("Continue to Form", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if back_clicked:
        st.session_state.page = "home"
        st.rerun()

    if continue_clicked:
        risk_quiz_score, risk_quiz_label = score_risk_quiz(
            risk_reaction,
            investment_style,
            time_commitment,
            return_expectation,
        )
        st.session_state.risk_quiz_score = risk_quiz_score
        st.session_state.risk_quiz_label = risk_quiz_label
        st.session_state.page = "form"
        st.rerun()

elif st.session_state.page == "form":
    render_top_bar()
    st.markdown(
        """
        <div class="hero">
            <h1>Build Your Investment Profile</h1>
            <p>Get a fast, readable recommendation with a clear allocation, top fund shortlist, and simple reasoning you can understand quickly.</p>
            <div class="hero-strip">
                <span class="hero-chip">Goal-based shortlist</span>
                <span class="hero-chip">Readable allocation logic</span>
                <span class="hero-chip">Top 3 funds with reasons</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>Investor Inputs</div>", unsafe_allow_html=True)
        stage_cols = st.columns(3)
        with stage_cols[0]:
            st.markdown(
                """
                <div class="form-stage">
                    <div class="form-stage-title">Step 1</div>
                    <div class="form-stage-copy">Tell the app about your age, income, and how much risk you want to take.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with stage_cols[1]:
            st.markdown(
                """
                <div class="form-stage">
                    <div class="form-stage-title">Step 2</div>
                    <div class="form-stage-copy">Choose your goal and horizon so the shortlist matches what you are investing for.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with stage_cols[2]:
            st.markdown(
                """
                <div class="form-stage">
                    <div class="form-stage-title">Step 3</div>
                    <div class="form-stage-copy">Review the recommendation, top fund picks, and quick explanation of the allocation.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.write("")

        with st.form("recommendation_form"):
            need_lower_volatility = False
            need_higher_return = False
            reset_refinement = False
            apply_custom_refinement = False

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**Profile**")
                st.caption("Core inputs about the investor.")
                st.number_input("Age", min_value=18, max_value=70, step=1, key="age_input")
                st.caption("Younger age usually allows a longer investment horizon.")
                st.number_input(
                    "Monthly Income",
                    min_value=0,
                    step=5000,
                    key="monthly_income_input",
                )
                st.caption("Income helps estimate how much risk and SIP level may be practical.")
                st.number_input(
                    "Investment Amount",
                    min_value=1000,
                    step=1000,
                    key="investment_amount_input",
                )
                st.caption("This is your starting lump-sum amount for the projection.")
                st.number_input(
                    "Monthly SIP",
                    min_value=500,
                    step=500,
                    key="monthly_sip_input",
                )
                st.caption("This is the monthly contribution used for the SIP projection.")

            with col2:
                st.markdown("**Plan**")
                st.caption("Risk and time horizon determine the shortlist.")
                st.radio(
                    "Risk Appetite",
                    ["Conservative", "Moderate", "Aggressive"],
                    horizontal=True,
                    key="risk_appetite_input",
                )
                st.caption("Choose how much market volatility you are comfortable handling.")
                st.selectbox(
                    "Duration",
                    ["1-3 Years", "3-5 Years", "5-10 Years", "10+ Years"],
                    key="duration_input",
                )
                st.caption("Longer duration usually supports more equity exposure.")
                st.selectbox(
                    "Goal",
                    [
                        "Retirement",
                        "Child Education",
                        "Buying House",
                        "Wealth Creation",
                        "Emergency Fund",
                    ],
                    key="financial_goal_input",
                )
                st.caption("Your goal shapes which fund categories are prioritized.")

            with col3:
                st.markdown("**Preferences**")
                st.caption("Optional filters and market view.")
                with st.expander("Optional filters", expanded=False):
                    st.selectbox(
                        "Market Outlook",
                        ["Bullish", "Neutral", "Bearish"],
                        key="market_sentiment_input",
                    )
                    st.caption("This slightly adjusts the portfolio posture, not the full strategy.")
                    st.checkbox("Tax Saving Only", key="tax_saving_input")
                    st.caption("Use this if you want ELSS-style tax-saving fund preference.")
                    st.checkbox("ESG Funds Only", key="esg_preference_input")
                    st.caption("Use this to prefer sustainability-focused funds when available.")

                    if st.session_state.results:
                        results = st.session_state.results
                        st.markdown("<hr style='border-color:rgba(148,163,184,0.18); margin:1rem 0;' />", unsafe_allow_html=True)
                        st.markdown("<div class='section-title'>Refine Recommendation</div>", unsafe_allow_html=True)
                        st.caption("When a recommendation exists, use these optional controls to adjust your target return or volatility.")
                        quick_refine_cols = st.columns(3)
                        with quick_refine_cols[0]:
                            need_lower_volatility = st.form_submit_button(
                                "Need Lower Volatility",
                                key="need_lower_volatility",
                                use_container_width=True,
                            )
                        with quick_refine_cols[1]:
                            need_higher_return = st.form_submit_button(
                                "Need Higher Return",
                                key="need_higher_return",
                                use_container_width=True,
                            )
                        with quick_refine_cols[2]:
                            reset_refinement = st.form_submit_button(
                                "Reset Refinement",
                                key="reset_refinement",
                                use_container_width=True,
                            )

                        with st.expander("Custom refinement controls", expanded=False):
                            current_mid_return = sum(results["return_range"]) / 2
                            refine_min_return_value = st.number_input(
                                "Minimum acceptable expected return (%)",
                                min_value=0.0,
                                max_value=25.0,
                                value=float(round(current_mid_return, 1)),
                                step=0.5,
                                key="refine_min_return_input",
                            )
                            refine_max_volatility_value = st.number_input(
                                "Maximum acceptable estimated volatility (%)",
                                min_value=1.0,
                                max_value=30.0,
                                value=float(round(results["estimated_volatility"], 1)),
                                step=0.5,
                                key="refine_max_volatility_input",
                            )
                            custom_refine_cols = st.columns(2)
                            with custom_refine_cols[0]:
                                apply_custom_refinement = st.form_submit_button(
                                    "Refine",
                                    key="apply_custom_refinement",
                                    use_container_width=True,
                                )
                            with custom_refine_cols[1]:
                                st.caption(
                                    f"Current plan midpoint return is about {current_mid_return:.1f}% with estimated volatility near {results['estimated_volatility']:.1f}%.")

                st.markdown(
                    f"""
                    <div class="panel" style="margin-top: 0.75rem;">
                        <strong>Risk quiz result:</strong> {st.session_state.risk_quiz_label}<br/>
                        <strong>Score:</strong> {st.session_state.risk_quiz_score} / 3
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption(explain_risk_quiz_score(st.session_state.risk_quiz_label))

            action_col1, action_col2 = st.columns([1, 1.4])
            with action_col1:
                retake_quiz = st.form_submit_button("Retake Quiz", use_container_width=True)
            with action_col2:
                submitted = st.form_submit_button("Get Recommendation", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    if retake_quiz:
        st.session_state.page = "quiz"
        st.rerun()

    if submitted:
        with st.spinner("Analyzing profile and ranking funds..."):
            run_recommendation(save_history=True)

    if need_lower_volatility:
        results = st.session_state.results
        if results:
            target_volatility = max(1.0, results["estimated_volatility"] - 1.5)
            with st.spinner("Refining for lower volatility..."):
                run_recommendation(
                    refine_min_return=st.session_state.refine_min_return,
                    refine_max_volatility=target_volatility,
                )
            st.rerun()

    if need_higher_return:
        results = st.session_state.results
        if results:
            current_mid_return = sum(results["return_range"]) / 2
            with st.spinner("Refining for higher return..."):
                run_recommendation(
                    refine_min_return=round(current_mid_return + 1, 1),
                    refine_max_volatility=st.session_state.refine_max_volatility,
                )
            st.rerun()

    if reset_refinement:
        with st.spinner("Restoring your base recommendation..."):
            run_recommendation()
        st.rerun()

    if apply_custom_refinement:
        with st.spinner("Applying your refinement targets..."):
            run_recommendation(
                refine_min_return=st.session_state.refine_min_return_input,
                refine_max_volatility=st.session_state.refine_max_volatility_input,
            )
        st.rerun()

    results = st.session_state.results

    if results:
        if "warnings" not in results:
            results["warnings"] = build_suitability_flags(
                goal=results["goal"],
                duration=results["duration"],
                tax_saving=results["tax_saving"],
                esg_preference=results["esg_preference"],
                market_sentiment=results["market_sentiment"],
                portfolio=results["portfolio"],
                equity=results["equity"],
            )
        if "estimated_volatility" not in results:
            results["estimated_volatility"] = estimate_portfolio_volatility(
                results["filtered_df"],
                results["equity"],
                results["debt"],
            )
        if "volatility_label" not in results:
            results["volatility_label"] = classify_volatility(results["estimated_volatility"])
        if "refinement_note" not in results:
            results["refinement_note"] = ""
        if not results.get("comparison_snapshots"):
            results["comparison_snapshots"] = build_comparison_snapshots(results)
        st.write("")
        confidence_tone = {"High": "good", "Medium": "warn", "Low": "neutral"}[results["confidence"]]
        pill(results["confidence_label"], confidence_tone)
        st.markdown(
            f"""
            <div class="summary-box">
                <p>{results["summary"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="trust-strip">
                <div class="trust-chip-card">
                    <div class="trust-chip-label">Recommendation Basis</div>
                    <div class="trust-chip-value">{results["goal"]} goal, {results["duration"]} horizon, {results["risk_appetite"]} risk input</div>
                </div>
                <div class="trust-chip-card">
                    <div class="trust-chip-label">Data Scope</div>
                    <div class="trust-chip-value">Historical fund screening using Yahoo-linked market data and internal profile ranking</div>
                </div>
                <div class="trust-chip-card">
                    <div class="trust-chip-label">Confidence</div>
                    <div class="trust-chip-value">{results["confidence_label"]} with {results["equity"]}% equity and {results["debt"]}% debt</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        top_metrics = st.columns(5)
        with top_metrics[0]:
            metric_card(
                "Portfolio",
                results["portfolio"],
                f'Risk score: {results["risk_score"]}',
            )
        with top_metrics[1]:
            metric_card(
                "Expected Return",
                f'{results["return_range"][0]}% - {results["return_range"][1]}%',
                "Estimated annual range",
            )
        with top_metrics[2]:
            metric_card(
                "Volatility",
                f'{results["estimated_volatility"]:.1f}%',
                f'{results["volatility_label"]} estimated fluctuation',
            )
        with top_metrics[3]:
            metric_card(
                "Projected SIP Value",
                f'Rs. {results["sip_future_value"]:,.0f} - Rs. {results["sip_future_value_high"]:,.0f}',
                f'SIP returns over {results["years"]} years',
            )
        with top_metrics[4]:
            metric_card(
                "Monthly SIP",
                f'Rs. {results["monthly_sip"]:,.0f}',
                f'Total invested: Rs. {results["monthly_sip"] * results["years"] * 12:,.0f}',
            )

        takeaway_cols = st.columns(3)
        with takeaway_cols[0]:
            takeaway_card(
                "Total invested",
                f'Rs. {results["monthly_sip"] * results["years"] * 12:,.0f}',
                f'{results["years"]} years of SIP contributions',
            )
        with takeaway_cols[1]:
            takeaway_card(
                "Projected growth",
                f'Rs. {results["sip_future_value"]:,.0f} - Rs. {results["sip_future_value_high"]:,.0f}',
                f'Projected value after {results["years"]} years',
            )
        with takeaway_cols[2]:
            takeaway_card(
                "Investment fit",
                f'{results["duration"]} | {results["portfolio"]}',
                "Balanced for your selected horizon and goal",
            )

        st.markdown(
            f"""
            <div class="summary-box">
                <p>{results["summary"]}</p>
            </div>
            <div class="panel" style="margin-top: 1rem; border-left: 4px solid #34d399;">
                <strong>How this SIP plan works:</strong><br/>
                Investing <strong>Rs. {results["monthly_sip"]:,.0f}</strong> every month for <strong>{results["years"]} years</strong> means a total contribution of <strong>Rs. {results["monthly_sip"] * results["years"] * 12:,.0f}</strong>.<br/>
                The projected range shown is based on the app's return assumptions for your selected horizon.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if results.get("refinement_note"):
            st.markdown(
                f"""
                <div class="panel compact-panel" style="margin-top: 0.9rem;">
                    <strong>Refinement update:</strong> {results["refinement_note"]}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")
        st.markdown("<div class='section-title'>Why This Recommendation Fits You</div>", unsafe_allow_html=True)
        explain_cols = st.columns(3)
        for col, (title, body) in zip(explain_cols, build_explanation_cards(results)):
            with col:
                info_card(title, body)

        st.caption(results["fallback_note"])
        st.markdown(
            """
            <div class="disclosure-note">
                <strong>Note:</strong> Suggested funds are based on historical fund data collected from Yahoo-linked market datasets.
                These are past data points and should be treated as informational, not as a guarantee of future performance.
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Quick Summary", "Allocation", "Top Funds", "Compare Plans", "SIP & Saved Reports"]
        )

        with tab1:
            left, right = st.columns([1.05, 1])
            with left:
                st.markdown("<div class='section-title'>What This Means</div>", unsafe_allow_html=True)
                st.markdown(
                    f"""
                    <div class="panel" style="margin-bottom: 0.8rem;">
                        <strong>{results["portfolio"]} profile</strong><br/>
                        {results["summary"]}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                for reason in results["reasons"][:2]:
                    st.markdown(
                        f"""
                        <div class="panel" style="margin-bottom: 0.8rem;">
                            {reason}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            with right:
                st.markdown("<div class='section-title'>Suitability Flags</div>", unsafe_allow_html=True)
                for warning in results["warnings"]:
                    st.markdown(
                        f"""
                        <div class="panel compact-panel" style="margin-bottom: 0.55rem;">
                            {warning}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                st.markdown("<div class='section-title'>Why Some Options Were Avoided</div>", unsafe_allow_html=True)
                for reason in results["not_suitable"][:2]:
                    st.markdown(
                        f"""
                        <div class="panel compact-panel" style="margin-bottom: 0.55rem;">
                            {reason}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f"""
                    <div class="panel compact-panel">
                        <strong>Confidence:</strong> {results["confidence_label"]}<br/>
                        {results["fallback_note"]}<br/><br/>
                        <strong>Risk quiz result:</strong> {results["risk_quiz_label"]}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with tab2:
            allocation_df = results["allocation_df"].copy()
            allocation_df["Share"] = allocation_df["Share"].astype(float)
            allocation_df["Label"] = allocation_df.apply(
                lambda row: f"{row['Asset']} {int(row['Share'])}%",
                axis=1,
            )
            allocation_center_df = pd.DataFrame(
                [
                    {"x": 1, "y": 1, "line": "Portfolio Mix", "order": 0},
                    {
                        "x": 1,
                        "y": 1,
                        "line": f"{int(results['equity'])}% Equity | {int(results['debt'])}% Debt",
                        "order": 1,
                    },
                ]
            )
            color_scale = alt.Scale(
                domain=["Equity", "Debt"],
                range=["#7dd3c7", "#cbd5e1"],
            )
            chart_col1, chart_col2 = st.columns([1.05, 0.95], gap="medium")

            with chart_col1:
                st.markdown("<div class='section-title'>Asset Mix</div>", unsafe_allow_html=True)
                donut_chart = (
                    alt.Chart(allocation_df)
                    .mark_arc(
                        innerRadius=78,
                        outerRadius=112,
                        cornerRadius=4,
                        stroke="#0d1728",
                        strokeWidth=1.2,
                    )
                    .encode(
                        theta=alt.Theta("Share:Q"),
                        color=alt.Color(
                            "Asset:N",
                            scale=color_scale,
                            legend=alt.Legend(orient="bottom", title=None),
                        ),
                        tooltip=[
                            alt.Tooltip("Asset:N"),
                            alt.Tooltip("Share:Q", format=".0f", title="Allocation (%)"),
                        ],
                    )
                    .properties(height=320)
                )
                donut_center_title = (
                    alt.Chart(allocation_center_df[allocation_center_df["order"] == 0])
                    .mark_text(
                        fontSize=15,
                        fontWeight="bold",
                        color="#f8fafc",
                    )
                    .encode(
                        x=alt.value(160),
                        y=alt.value(145),
                        text="line:N",
                    )
                )
                donut_center_value = (
                    alt.Chart(allocation_center_df[allocation_center_df["order"] == 1])
                    .mark_text(
                        fontSize=12,
                        fontWeight="normal",
                        color="#cbd5e1",
                    )
                    .encode(
                        x=alt.value(160),
                        y=alt.value(165),
                        text="line:N",
                    )
                )
                donut_labels = (
                    alt.Chart(allocation_df)
                    .mark_text(radius=118, fontSize=12, fontWeight="normal", color="#dbe7f3")
                    .encode(theta=alt.Theta("Share:Q"), text="Label:N")
                )
                st.altair_chart(
                    donut_chart + donut_labels + donut_center_title + donut_center_value,
                    use_container_width=True,
                )
                st.markdown("<div class='section-title'>Allocation Balance</div>", unsafe_allow_html=True)
                balance_bar = (
                    alt.Chart(allocation_df)
                    .mark_bar(size=28, cornerRadius=18)
                    .encode(
                        y=alt.Y("Asset:N", sort=["Equity", "Debt"], title=None),
                        x=alt.X(
                            "Share:Q",
                            title="Portfolio share (%)",
                            scale=alt.Scale(domain=[0, 100]),
                        ),
                        color=alt.Color("Asset:N", scale=color_scale, legend=None),
                        tooltip=[
                            alt.Tooltip("Asset:N"),
                            alt.Tooltip("Share:Q", format=".0f", title="Allocation (%)"),
                        ],
                    )
                    .properties(height=135)
                )
                balance_text = (
                    alt.Chart(allocation_df)
                    .mark_text(align="left", baseline="middle", dx=8, fontSize=15, fontWeight="bold", color="#f8fafc")
                    .encode(
                        y=alt.Y("Asset:N", sort=["Equity", "Debt"], title=None),
                        x=alt.X("Share:Q"),
                        text=alt.Text("Share:Q", format=".0f"),
                    )
                )
                st.altair_chart(balance_bar + balance_text, use_container_width=True)

            with chart_col2:
                st.markdown("<div class='section-title'>Allocation Reasoning</div>", unsafe_allow_html=True)
                for reason in results["allocation_reasons"]:
                    st.markdown(
                        f"""
                        <div class="panel compact-panel" style="margin-bottom: 0.55rem;">
                            {reason}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        with tab3:
            st.markdown("<div class='section-title'>Top Fund Picks</div>", unsafe_allow_html=True)
            top_cols = st.columns(3)
            for idx, fund in enumerate(results["top_fund_reasons"][:3]):
                reason_text = "".join(
                    f"<li>{item}</li>" for item in fund["reasons"]
                )
                with top_cols[idx]:
                    st.markdown(
                        f"""
                        <div class="recommendation-card">
                            <h3>{fund["name"]}</h3>
                            <div class="recommendation-meta">{fund["subtype"]} | {fund["risk_category"]}</div>
                            <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:0.8rem;">
                                <span class="hero-chip" style="background:rgba(52,211,153,0.12); border-color:rgba(52,211,153,0.18); color:#d1fae5;">CAGR {fund["cagr"]}%</span>
                                <span class="hero-chip" style="background:rgba(56,189,248,0.12); border-color:rgba(56,189,248,0.18); color:#dbeafe;">Sharpe {fund["sharpe"]}</span>
                                <span class="hero-chip" style="background:rgba(148,163,184,0.12); border-color:rgba(148,163,184,0.18); color:#e2e8f0;">Fit {fund["score"] * 100:.0f}%</span>
                            </div>
                            <div style="color:#94a3b8; font-size:0.9rem; margin-bottom:0.75rem; line-height:1.3;">
                                Fit: match to your profile. CAGR: annual growth rate. Sharpe: extra return per unit of risk.
                            </div>
                            <ul style="margin:0; padding-left:1.1rem;">
                                {reason_text}
                            </ul>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            with st.expander("See More Funds"):
                funds_to_show = results["filtered_df"][
                    [
                        "Actual_Fund_Name",
                        "SubType",
                        "Risk_Category",
                    ]
                ].copy()
                funds_to_show.columns = ["Fund", "Category", "Risk"]
                st.dataframe(
                    funds_to_show,
                    use_container_width=True,
                    hide_index=True,
                )

        with tab4:
            st.markdown("<div class='section-title'>Portfolio Comparison</div>", unsafe_allow_html=True)
            comparison_cols = st.columns(3)
            for col, snapshot in zip(comparison_cols, results["comparison_snapshots"]):
                selected_marker = "Current selection" if snapshot["profile"] == results["risk_appetite"] else "Alternative"
                card_class = "recommendation-card current-plan-card" if snapshot["profile"] == results["risk_appetite"] else "recommendation-card"
                with col:
                    st.markdown(
                        f"""
                        <div class="{card_class}">
                            <h3>{snapshot["profile"]}</h3>
                            <div class="recommendation-meta">{selected_marker} | {snapshot["portfolio"]} mix</div>
                            <p><strong>Allocation:</strong> {snapshot["equity"]}% equity / {snapshot["debt"]}% debt</p>
                            <p><strong>Expected return:</strong> {snapshot["return_range"][0]}% - {snapshot["return_range"][1]}%</p>
                            <p><strong>Estimated volatility:</strong> {snapshot["estimated_volatility"]:.1f}%</p>
                            <p><strong>Projected range:</strong><br/>{format_currency(snapshot["future_value_low"])} - {format_currency(snapshot["future_value_high"])}</p>
                            <p><strong>Top fund:</strong> {snapshot["top_fund"]}</p>
                            <p style="margin-bottom:0;">{snapshot["risk_note"]}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            comparison_df = pd.DataFrame(results["comparison_snapshots"]).rename(
                columns={
                    "profile": "Risk Profile",
                    "portfolio": "Portfolio",
                    "equity": "Equity (%)",
                    "debt": "Debt (%)",
                    "top_fund": "Top Fund",
                }
            )
            comparison_df["Return Range"] = comparison_df["return_range"].apply(
                lambda item: f"{item[0]}% - {item[1]}%"
            )
            comparison_df["Estimated Volatility"] = comparison_df["estimated_volatility"].apply(
                lambda value: f"{value:.1f}%"
            )
            comparison_df["Projected Value Range"] = comparison_df.apply(
                lambda row: f"{format_currency(row['future_value_low'])} - {format_currency(row['future_value_high'])}",
                axis=1,
            )
            st.dataframe(
                comparison_df[
                    [
                        "Risk Profile",
                        "Portfolio",
                        "Equity (%)",
                        "Debt (%)",
                        "Return Range",
                        "Estimated Volatility",
                        "Projected Value Range",
                        "Top Fund",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Projected value range: The estimated total amount your investment could grow to over the selected time period, based on the expected returns and market volatility for each risk profile.")

        with tab5:
            left, right = st.columns([1.05, 1])
            with left:
                st.markdown("<div class='section-title'>Monthly SIP Projection</div>", unsafe_allow_html=True)
                st.markdown(
                    f"""
                    <div class="panel" style="margin-bottom: 0.8rem;">
                        If you invest <strong>Rs. {results["monthly_sip"]:,.0f}</strong> every month for
                        <strong>{results["years"]} years</strong>, the projected value is about
                        <strong>Rs. {results["sip_future_value"]:,.0f}</strong> at the base return assumption.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                sip_chart = (
                    alt.Chart(results["sip_projection_df"])
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("Year:O"),
                        y=alt.Y("Projected Value:Q"),
                        tooltip=["Year", "Invested Amount", "Projected Value"],
                    )
                )
                st.altair_chart(sip_chart, use_container_width=True)

            with right:
                st.markdown("<div class='section-title'>SIP Reading</div>", unsafe_allow_html=True)
                st.markdown(
                    f"""
                    <div class="panel" style="margin-bottom: 0.75rem;">
                        <strong>Total SIP invested:</strong><br/>
                        Rs. {results["monthly_sip"] * results["years"] * 12:,.0f}
                    </div>
                    <div class="panel" style="margin-bottom: 0.75rem;">
                        <strong>Projected value at base return:</strong><br/>
                        Rs. {results["sip_future_value"]:,.0f}
                    </div>
                    <div class="panel">
                        <strong>Projected value at upper range:</strong><br/>
                        Rs. {results["sip_future_value_high"]:,.0f}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption("This SIP estimate is illustrative and uses the app's portfolio return assumption, not guaranteed returns.")

                st.write("")
                st.markdown("<div class='section-title'>Saved Reports</div>", unsafe_allow_html=True)
                with st.popover("View Saved Reports", use_container_width=True):
                    if not st.session_state.saved_reports:
                        st.caption("No saved reports yet. Generate a recommendation to start building history.")
                    else:
                        for idx, item in enumerate(st.session_state.saved_reports):
                            report_export = {
                                key: value
                                for key, value in item.items()
                                if key != "results_snapshot"
                            }
                            with st.expander(
                                f"{item['saved_at']} | {item['goal']} | {item['portfolio']}",
                                expanded=(idx == 0),
                            ):
                                st.markdown(
                                    f"""
                                    <div class="panel compact-panel" style="margin-bottom: 0.55rem;">
                                        <strong>{item["portfolio"]}</strong> for {item["goal"]} over {item["duration"]}.<br/>
                                        Allocation: {item["equity"]}% equity / {item["debt"]}% debt<br/>
                                        Estimated volatility: {item.get("estimated_volatility", 0):.1f}%<br/>
                                        Projected value range: {format_currency(item["future_value_low"])} - {format_currency(item["future_value_high"])}<br/>
                                        Confidence: {item["confidence_label"]}
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                                button_cols = st.columns([1, 1.2, 3.8])
                                with button_cols[0]:
                                    if st.button("Restore", key=f"restore_report_{idx}", use_container_width=True):
                                        st.session_state.results = dict(item["results_snapshot"])
                                        sync_recommendation_state_from_results(st.session_state.results)
                                        st.session_state.refine_min_return = st.session_state.results.get("refine_min_return")
                                        st.session_state.refine_max_volatility = st.session_state.results.get("refine_max_volatility")
                                        st.rerun()
                                with button_cols[1]:
                                    st.download_button(
                                        "Export JSON",
                                        data=json.dumps(report_export, indent=2),
                                        file_name=f"saved_report_{idx + 1}.json",
                                        mime="application/json",
                                        key=f"export_report_{idx}",
                                        use_container_width=True,
                                    )
                                with button_cols[2]:
                                    top_funds_text = ", ".join(item["top_funds"]) if item["top_funds"] else "No funds stored"
                                    st.caption(f"Top funds: {top_funds_text}")

        st.write("")
        render_advisor_chat(results)

    st.write("")

    if st.session_state.get("show_feedback", False):
        st.markdown("<div class='section-title'>Share Your Feedback</div>", unsafe_allow_html=True)
        with st.form("results_feedback_form"):
            feedback_name = st.text_input("Name (optional)")
            feedback_email = st.text_input("Email (optional)")
            feedback_type = st.selectbox("Feedback Type", ["General Feedback", "Bug Report", "Feature Request", "Question"])
            feedback_message = st.text_area("Your Message", height=100)
            feedback_submit = st.form_submit_button("Submit Feedback", use_container_width=True)
        
        if feedback_submit:
            save_feedback(feedback_name.strip(), feedback_email.strip(), feedback_type, feedback_message.strip())
            st.success("Thank you for your feedback! We'll review it and get back to you if needed.")
            st.session_state.show_feedback = False
            st.rerun()

    nav_left, nav_center, nav_right = st.columns([1, 1, 1])
    with nav_left:
        if st.button("Back to Home", use_container_width=True):
            st.session_state.page = "home"
            st.rerun()
    with nav_right:
        if st.button("💬 Share Your Feedback", use_container_width=True):
            st.session_state.show_feedback = True
            st.rerun()
