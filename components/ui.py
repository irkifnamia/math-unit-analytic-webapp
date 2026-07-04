from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
KMK_LOGO = ROOT / "assets" / "logo_kmk.png"
AFJ_LOGO = ROOT / "assets" / "logo_afj_analytic.png"


def image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-bg: #f6f7fb;
            --app-panel: #ffffff;
            --app-panel-soft: #f5f6fb;
            --app-border: #dde2ee;
            --app-border-strong: #b8bfd6;
            --app-muted: #5f6678;
            --app-ink: #141827;
            --app-surface: #ffffff;
            --app-accent: #2d3192;
            --app-accent-dark: #202466;
            --app-accent-soft: #eef0ff;
            --app-red: #ed1c24;
            --app-red-dark: #b8131a;
            --app-yellow: #ffe81a;
            --app-success: #08756f;
            --app-shadow: 0 18px 45px rgba(20, 24, 39, 0.1);
            --app-shadow-soft: 0 8px 24px rgba(20, 24, 39, 0.07);
        }

        html, body, [data-testid="stAppViewContainer"] {
            background:
                linear-gradient(180deg, #ffffff 0%, #f8f9fd 34%, #f2f4fb 100%) !important;
            color: var(--app-ink);
            font-family: Inter, Aptos, "Segoe UI", Arial, sans-serif;
        }

        [data-testid="stHeader"] {
            background: rgba(246, 247, 251, 0.88);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(224, 228, 239, 0.78);
        }

        .block-container {
            padding-top: 1.35rem;
            padding-bottom: 2.25rem;
            max-width: 1420px;
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(246,247,252,0.98) 100%);
            border-right: 1px solid var(--app-border);
        }

        [data-testid="stSidebar"]::before {
            content: "";
            display: block;
            height: 5px;
            background: linear-gradient(90deg, var(--app-red), var(--app-yellow), var(--app-accent));
            margin: 0 -1rem 1rem;
        }

        [data-testid="stSidebar"] * {
            color: var(--app-ink);
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            font-weight: 750;
        }

        h1, h2, h3 {
            color: var(--app-ink);
            letter-spacing: 0;
            font-family: Inter, Aptos, "Segoe UI", Arial, sans-serif;
        }

        p, label, span, div {
            letter-spacing: 0;
        }

        [data-testid="stForm"] {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid var(--app-border);
            border-radius: 8px;
            box-shadow: var(--app-shadow-soft);
            padding: 1rem;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-baseweb="select"] > div {
            background: #ffffff;
            border-color: var(--app-border);
            color: var(--app-ink);
            border-radius: 8px;
        }

        [data-testid="stTextInput"] > div > div,
        [data-testid="stTextArea"] > div > div,
        [data-testid="stFileUploader"] section,
        [data-baseweb="select"] > div {
            border: 1px solid var(--app-border-strong) !important;
            border-radius: 8px !important;
            background: #ffffff !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
        }

        [data-testid="stTextInput"] label,
        [data-testid="stTextArea"] label,
        [data-testid="stSelectbox"] label,
        [data-testid="stFileUploader"] label {
            color: var(--app-ink) !important;
            font-weight: 700;
        }

        [data-testid="stTextInput"] input:focus,
        [data-testid="stTextArea"] textarea:focus {
            border-color: var(--app-accent);
            box-shadow: 0 0 0 3px rgba(45, 49, 146, 0.13);
        }

        .stButton > button,
        [data-testid="stFormSubmitButton"] button,
        .stDownloadButton > button {
            border-radius: 8px;
            border: 1px solid var(--app-accent);
            background: linear-gradient(135deg, var(--app-accent) 0%, var(--app-accent-dark) 100%);
            color: #ffffff;
            font-weight: 700;
            box-shadow: 0 8px 18px rgba(45, 49, 146, 0.18);
        }

        .stButton > button *,
        [data-testid="stFormSubmitButton"] button *,
        .stDownloadButton > button * {
            color: #f8fafc !important;
            font-weight: 700 !important;
        }

        .stButton > button:hover,
        [data-testid="stFormSubmitButton"] button:hover,
        .stDownloadButton > button:hover {
            background: linear-gradient(135deg, #363aa8 0%, #181b55 100%);
            border-color: var(--app-accent-dark);
            color: #ffffff;
        }

        .stButton > button[kind="secondary"] {
            background: #ffffff;
            border-color: var(--app-border-strong);
            color: var(--app-accent);
            box-shadow: var(--app-shadow-soft);
        }

        .stButton > button[kind="secondary"] * {
            color: var(--app-accent) !important;
        }

        .stButton > button[kind="secondary"]:hover {
            background: var(--app-accent-soft);
            border-color: var(--app-accent);
            color: var(--app-accent-dark);
        }

        .stButton > button[kind="secondary"]:hover * {
            color: var(--app-accent-dark) !important;
        }

        .download-strip {
            margin: 0.35rem 0 1.1rem;
        }

        div[data-testid="stMetric"] {
            background:
                linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
            border: 1px solid var(--app-border);
            border-radius: 8px;
            padding: 16px 18px;
            box-shadow: var(--app-shadow-soft);
            position: relative;
            overflow: hidden;
        }

        div[data-testid="stMetric"]::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(180deg, var(--app-red), var(--app-accent));
        }

        div[data-testid="stMetricLabel"] p {
            color: var(--app-muted);
            font-size: 0.82rem;
            font-weight: 700;
        }

        div[data-testid="stMetricValue"] {
            color: var(--app-ink);
        }

        div[data-testid="stElementContainer"]:has(.app-header),
        div.element-container:has(.app-header),
        div[data-testid="stMarkdownContainer"]:has(.app-header) {
            position: sticky !important;
            top: 0 !important;
            z-index: 1000 !important;
            background: linear-gradient(180deg, rgba(246, 247, 251, 0.98), rgba(246, 247, 251, 0.9));
            padding: 0.35rem 0 0.4rem;
            margin: -0.35rem 0 0.9rem;
            backdrop-filter: blur(12px);
        }

        .app-header {
            position: sticky;
            top: 0;
            z-index: 1001;
            background:
                linear-gradient(135deg, #171b4f 0%, #25298c 58%, #111432 100%);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-left: 5px solid var(--app-red);
            border-radius: 8px;
            padding: 0.82rem 1rem 0.88rem;
            margin-bottom: 0;
            box-shadow: 0 14px 34px rgba(17, 20, 50, 0.22);
        }

        .app-header::after {
            content: "";
            display: block;
            width: 100%;
            height: 3px;
            margin-top: 0.7rem;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--app-red), var(--app-yellow), var(--app-accent));
        }

        .app-header h1 {
            margin: 0;
            line-height: 1.08;
            font-weight: 850;
            text-transform: uppercase;
            font-size: clamp(1.55rem, 2.4vw, 2.35rem);
            color: #ffffff;
        }

        .app-header p {
            color: rgba(255, 255, 255, 0.78);
            font-size: 0.96rem;
            margin: 0.48rem 0 0;
        }

        .role-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            border: 1px solid rgba(255, 232, 26, 0.52);
            color: var(--app-yellow);
            font-size: 0.78rem;
            font-weight: 700;
            padding: 0.18rem 0.55rem;
            margin-left: 0.35rem;
            background: rgba(255, 232, 26, 0.1);
        }

        [data-testid="stTabs"] button {
            color: var(--app-muted);
            font-weight: 700;
        }

        [data-testid="stTabs"] button[aria-selected="true"] {
            color: var(--app-accent);
            border-bottom-color: var(--app-accent) !important;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border: 1px solid var(--app-border);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: var(--app-shadow-soft);
        }

        [data-testid="stAlert"] {
            border-radius: 8px;
            border: 1px solid var(--app-border);
        }

        .js-plotly-plot {
            border: 1px solid var(--app-border);
            border-radius: 8px;
            background: linear-gradient(180deg, #ffffff 0%, #fbfcff 100%);
            box-shadow: var(--app-shadow-soft);
            padding: 0.25rem;
        }

        .kmk-app-brand {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            gap: 0.55rem;
            padding: 0.35rem 0 0.85rem;
            text-align: center;
        }

        .kmk-app-brand img {
            width: 96px;
            height: 96px;
            object-fit: contain;
        }

        .kmk-app-brand-title {
            color: var(--app-ink);
            font-weight: 850;
            font-size: 1.2rem;
            line-height: 1.08;
            text-transform: uppercase;
        }

        .kmk-app-brand-caption {
            color: var(--app-muted);
            font-size: 0.82rem;
        }

        .sidebar-user-badge {
            text-align: center;
            color: var(--app-muted);
            font-size: 0.82rem;
            font-weight: 650;
            line-height: 1.25;
            margin: -0.25rem 0 1rem;
            width: 100%;
        }

        .afj-sidebar-brand {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
            padding: 0.85rem 0.65rem;
            margin: 0.35rem 0 0.75rem;
            border: 1px solid var(--app-border);
            border-radius: 8px;
            background: linear-gradient(135deg, #ffffff 0%, #f6f7fc 100%);
            box-shadow: var(--app-shadow-soft);
            text-align: center;
        }

        .afj-sidebar-brand img {
            width: 58px;
            height: 58px;
            object-fit: contain;
            border-radius: 8px;
        }

        .afj-sidebar-brand span {
            display: block;
            color: var(--app-muted);
            font-size: 0.74rem;
            font-weight: 700;
            text-transform: uppercase;
            text-align: center;
        }

        .afj-sidebar-brand strong {
            display: block;
            color: var(--app-ink);
            font-size: 0.88rem;
            line-height: 1.15;
            text-align: center;
            text-transform: uppercase;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, caption: str, role: str | None = None) -> None:
    role_markup = f"<span class='role-pill'>{role}</span>" if role else ""
    st.markdown(
        f"""
        <div class="app-header">
            <h1>{title.upper()} {role_markup}</h1>
            <p>{caption}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def app_brand() -> None:
    logo_uri = image_data_uri(KMK_LOGO)
    logo_markup = f"<img src='{logo_uri}' alt='Kolej Matrikulasi Kedah logo'>" if logo_uri else ""
    st.markdown(
        f"""
        <div class="kmk-app-brand">
            {logo_markup}
            <div class="kmk-app-brand-title">MATHEMATICS UNIT ANALYTIC</div>
            <div class="kmk-app-brand-caption">Kolej Matrikulasi Kedah</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def afj_sidebar_brand() -> None:
    logo_uri = image_data_uri(AFJ_LOGO)
    logo_markup = f"<img src='{logo_uri}' alt='AFJ Analytic logo'>" if logo_uri else ""
    st.markdown(
        f"""
        <div class="afj-sidebar-brand">
            {logo_markup}
            <span>Powered by</span>
            <strong>AFJ Analytic</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


def blank_state(message: str) -> None:
    st.info(message)
