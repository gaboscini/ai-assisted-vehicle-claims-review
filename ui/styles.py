from __future__ import annotations

import streamlit as st


SHARED_APP_STYLES = """
<style>
    :root {
        --claims-primary: #0f6cbd;
        --claims-primary-dark: #0b4f87;
        --claims-text: #102a43;
        --claims-muted: #627d98;
        --claims-border: #d9e2ec;
        --claims-surface: #ffffff;
        --claims-background: #f4f7fb;
        --claims-radius: 12px;
        --claims-space-xs: 0.35rem;
        --claims-space-sm: 0.65rem;
        --claims-space-md: 1rem;
        --claims-space-lg: 1.4rem;
        --claims-body-size: 0.9rem;
        --claims-label-size: 0.78rem;
        --claims-value-size: 1.15rem;
    }

    .stApp {
        background:
            radial-gradient(
                circle at 88% 2%,
                rgba(15, 108, 189, 0.08),
                transparent 27rem
            ),
            var(--claims-background);
        color: var(--claims-text);
        font-size: var(--claims-body-size);
    }

    .block-container {
        max-width: 1240px !important;
        padding-top: 1.8rem !important;
        padding-bottom: 3.5rem !important;
    }

    [data-testid="stMainBlockContainer"] > div[data-testid="stVerticalBlock"],
    section.main div[data-testid="stVerticalBlock"] {
        gap: var(--claims-space-md);
    }

    div[data-testid="stHorizontalBlock"] {
        gap: var(--claims-space-md);
        align-items: stretch;
    }

    div[data-testid="stColumn"] {
        min-width: 0;
    }

    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
        height: 100%;
    }

    .stApp p,
    .stApp label,
    .stApp input,
    .stApp textarea,
    .stApp select,
    .stApp button {
        font-size: var(--claims-body-size);
    }

    .stCaptionContainer,
    .stCaptionContainer p,
    div[data-testid="stCaptionContainer"],
    div[data-testid="stCaptionContainer"] p {
        color: var(--claims-muted);
        font-size: var(--claims-label-size) !important;
        line-height: 1.5;
    }

    h1, h2, h3, h4 {
        color: var(--claims-text);
        letter-spacing: -0.02em;
        line-height: 1.2;
    }

    h1 {
        margin: 0 0 0.75rem 0;
        font-size: clamp(2rem, 4vw, 3rem);
    }

    h2 {
        margin: 1rem 0 0.55rem 0;
        font-size: 1.55rem;
    }

    h3 {
        margin: 0.75rem 0 0.45rem 0;
        font-size: 1.15rem;
    }

    h4 {
        margin: 0.6rem 0 0.35rem 0;
        font-size: 1rem;
    }

    .portal-title,
    .agent-title,
    .status-title,
    .knowledge-title {
        margin: 0.35rem 0 0.55rem 0 !important;
        font-size: clamp(2rem, 4vw, 3rem) !important;
        line-height: 1.08 !important;
    }

    .portal-kicker,
    .decision-kicker,
    .agent-kicker,
    .status-kicker,
    .knowledge-kicker {
        font-size: 0.74rem !important;
    }

    .portal-subtitle,
    .agent-subtitle,
    .status-subtitle,
    .knowledge-subtitle {
        margin-bottom: var(--claims-space-lg) !important;
        color: var(--claims-muted) !important;
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
    }

    .section-heading,
    .section-title,
    .faq-label {
        margin: 0 0 0.3rem 0 !important;
        color: var(--claims-text) !important;
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        line-height: 1.3 !important;
    }

    .section-copy,
    .faq-copy {
        margin: 0 0 var(--claims-space-md) 0 !important;
        color: var(--claims-muted) !important;
        font-size: 0.86rem !important;
        line-height: 1.55 !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--claims-border) !important;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 8px 25px rgba(16, 42, 67, 0.05);
    }

    div[data-testid="stMetric"] {
        min-height: 104px;
        height: 100%;
        padding: 1rem;
        border: 1px solid var(--claims-border);
        border-radius: var(--claims-radius);
        background: var(--claims-surface);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] p {
        color: var(--claims-muted);
        font-size: var(--claims-label-size) !important;
        font-weight: 650;
        line-height: 1.35;
    }

    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] > div {
        color: var(--claims-text);
        font-size: var(--claims-value-size) !important;
        font-weight: 700;
        line-height: 1.3;
        white-space: normal;
        overflow-wrap: anywhere;
    }

    div[data-testid="stMetricValue"] > div {
        overflow: visible;
        text-overflow: clip;
        white-space: normal;
        overflow-wrap: anywhere;
    }

    .claim-summary-card,
    .tracking-summary-card {
        min-height: 104px !important;
        height: 100%;
        margin: 0 0 var(--claims-space-xs) 0;
        padding: 1rem !important;
        border: 1px solid var(--claims-border) !important;
        border-radius: var(--claims-radius) !important;
        background: var(--claims-surface) !important;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-sizing: border-box;
    }

    .claim-summary-label,
    .tracking-summary-label {
        margin-bottom: 0.45rem !important;
        color: var(--claims-muted) !important;
        font-size: var(--claims-label-size) !important;
        font-weight: 650 !important;
        line-height: 1.35 !important;
    }

    .claim-summary-value,
    .tracking-summary-value {
        color: var(--claims-text) !important;
        font-size: var(--claims-value-size) !important;
        font-weight: 700 !important;
        line-height: 1.3 !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
    }

    div[data-testid="stTabs"] {
        margin-top: var(--claims-space-sm);
    }

    div[data-baseweb="tab-list"] {
        gap: var(--claims-space-xs);
        margin-bottom: var(--claims-space-md);
        border-bottom: 1px solid var(--claims-border);
    }

    button[data-baseweb="tab"] {
        min-height: 2.8rem;
        padding: 0.65rem 1rem;
        border-radius: 9px 9px 0 0;
        color: #52667a;
        font-size: 0.86rem !important;
        font-weight: 750;
    }

    button[data-baseweb="tab"]:hover {
        color: var(--claims-primary-dark);
        background: #f0f6fb;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--claims-primary-dark);
        background: #edf6ff;
    }

    div[data-baseweb="tab-highlight"] {
        background-color: var(--claims-primary);
    }

    div[data-testid="stExpander"] {
        overflow: hidden;
        margin-bottom: var(--claims-space-sm);
        border: 1px solid var(--claims-border);
        border-radius: var(--claims-radius);
        background: var(--claims-surface);
    }

    div[data-testid="stExpander"] details > summary {
        min-height: 2.9rem;
        padding: 0.7rem 0.9rem;
        font-size: 0.86rem;
        font-weight: 650;
    }

    div[data-testid="stDataFrame"] {
        overflow: hidden;
        margin: var(--claims-space-sm) 0 var(--claims-space-md) 0;
        border: 1px solid var(--claims-border);
        border-radius: 12px;
    }

    .assessment-section-spacer {
        display: block;
        width: 100%;
        height: var(--claims-space-md);
    }

    div[data-testid="stFileUploaderDropzone"] {
        min-height: 5.4rem;
        padding: 0.8rem;
        border: 1px dashed #7eb5df;
        border-radius: var(--claims-radius);
        background: #f4f9fd;
    }

    div[data-testid="stAlert"] {
        width: 100%;
        margin: 0 0 var(--claims-space-md) 0;
        box-sizing: border-box;
    }

    div[data-testid="stAlertContainer"] {
        width: 100%;
        min-height: 0 !important;
        padding: 0.85rem 1rem !important;
        border: 0 !important;
        border-left: 4px solid #0f6cbd !important;
        border-radius: 9px !important;
        color: #334e68 !important;
        background: #edf6ff !important;
        box-shadow: none !important;
        box-sizing: border-box;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
    }

    div[data-testid="stAlertContainer"]:has(
        div[data-testid="stAlertContentSuccess"]
    ) {
        border-left-color: #16845b !important;
        color: #176b4a !important;
        background: #edf9f4 !important;
    }

    div[data-testid="stAlertContainer"]:has(
        div[data-testid="stAlertContentWarning"]
    ) {
        border-left-color: #c78316 !important;
        color: #76520f !important;
        background: #fff8e8 !important;
    }

    div[data-testid="stAlertContainer"]:has(
        div[data-testid="stAlertContentError"]
    ) {
        border-left-color: #c94b55 !important;
        color: #8d2f38 !important;
        background: #fff1f2 !important;
    }

    div[data-testid="stAlertContainer"] > div {
        width: 100%;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
    }

    div[data-testid^="stAlertContent"] {
        width: 100%;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
    }

    div[data-testid^="stAlertContent"] > div,
    div[data-testid^="stAlertContent"] .stMarkdown,
    div[data-testid^="stAlertContent"] .stMarkdown > div {
        width: 100%;
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
    }

    div[data-testid="stAlert"] p,
    div[data-testid="stAlertContainer"] p {
        margin: 0 !important;
        padding: 0 !important;
        font-size: var(--claims-body-size) !important;
        font-weight: 550;
        line-height: 1.35 !important;
    }

    div[data-testid="stForm"] {
        margin: var(--claims-space-sm) 0;
        padding: 1rem;
        border-color: var(--claims-border);
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.72);
    }

    div[data-baseweb="input"],
    div[data-baseweb="select"] > div,
    textarea {
        border: 1px solid #c7d5e3 !important;
        border-radius: 9px !important;
        background: #ffffff !important;
        box-shadow: 0 1px 2px rgba(16, 42, 67, 0.05) !important;
        transition:
            border-color 140ms ease,
            box-shadow 140ms ease;
    }

    div[data-baseweb="input"]:hover,
    div[data-baseweb="select"] > div:hover,
    textarea:hover {
        border-color: #9fb6ca !important;
    }

    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="select"] > div:focus-within,
    textarea:focus {
        border-color: var(--claims-primary) !important;
        box-shadow: 0 0 0 3px rgba(15, 108, 189, 0.13) !important;
        outline: none !important;
    }

    div[data-baseweb="input"] input,
    div[data-baseweb="select"] input {
        background: transparent !important;
    }

    div[data-testid="stTextInput"] div[data-baseweb="input"] {
        height: 2.8rem !important;
        min-height: 2.8rem !important;
    }

    div[data-testid="stTextInput"] input {
        height: 100% !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }

    div[data-testid="stTextInput"],
    div[data-testid="stTextArea"],
    div[data-testid="stSelectbox"],
    div[data-testid="stMultiSelect"],
    div[data-testid="stDateInput"],
    div[data-testid="stFileUploader"] {
        margin-bottom: var(--claims-space-sm);
    }

    .stButton > button,
    .stFormSubmitButton > button {
        height: 2.8rem !important;
        min-height: 2.8rem;
        padding: 0.6rem 1rem;
        border-radius: 10px;
        font-weight: 750;
        box-shadow: none;
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        color: #ffffff;
        border-color: var(--claims-primary);
        background: var(--claims-primary);
        box-shadow: 0 5px 14px rgba(15, 108, 189, 0.18);
    }

    .stButton > button[kind="primary"]:hover,
    .stFormSubmitButton > button[kind="primary"]:hover {
        color: #ffffff;
        border-color: #0b5a9d;
        background: #0b5a9d;
    }

    div[role="dialog"] {
        border: 1px solid var(--claims-border);
        border-radius: 18px;
        background: var(--claims-background);
    }

    div[role="dialog"] > div {
        padding: 0.3rem;
    }

    div[role="dialog"] h2 {
        margin-bottom: var(--claims-space-sm);
        font-size: 1.45rem;
    }

    div[role="dialog"] div[data-testid="stVerticalBlock"] {
        gap: var(--claims-space-md);
    }

    .status-strip,
    .app-notice {
        width: 100%;
        min-height: 0;
        margin: 0 0 var(--claims-space-md) 0 !important;
        padding: 0.85rem 1rem !important;
        border: 0 !important;
        border-left: 4px solid #0f6cbd !important;
        border-radius: 9px !important;
        color: #334e68 !important;
        background: #edf6ff !important;
        box-shadow: none !important;
        box-sizing: border-box;
        display: flex;
        align-items: center;
        font-size: var(--claims-body-size) !important;
        line-height: 1.35 !important;
        white-space: pre-line;
    }

    .app-notice--success {
        border-left-color: #16845b !important;
        color: #176b4a !important;
        background: #edf9f4 !important;
    }

    .app-notice--warning {
        border-left-color: #c78316 !important;
        color: #76520f !important;
        background: #fff8e8 !important;
    }

    .app-notice--error {
        border-left-color: #c94b55 !important;
        color: #8d2f38 !important;
        background: #fff1f2 !important;
    }

    .evidence-checklist {
        margin: var(--claims-space-sm) 0 var(--claims-space-md) 0 !important;
        padding: 0.85rem 1rem !important;
        border-radius: 10px !important;
        font-size: 0.86rem !important;
        line-height: 1.5 !important;
    }

    .upload-card-title,
    .replacement-card-title {
        min-height: 2.9rem !important;
        margin: 0 0 var(--claims-space-sm) 0 !important;
        font-size: 1rem !important;
        line-height: 1.35 !important;
    }

    #MainMenu, footer {
        visibility: hidden;
    }

    @media (max-width: 760px) {
        :root {
            --claims-value-size: 1.05rem;
        }

        .block-container {
            padding-top: 1.2rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    }
</style>
"""


def apply_shared_styles() -> None:
    st.markdown(
        SHARED_APP_STYLES,
        unsafe_allow_html=True,
    )
