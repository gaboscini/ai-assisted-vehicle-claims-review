from __future__ import annotations

import streamlit as st


FORM_CONTROL_STYLES = """
<style>
    div[data-testid="stTextInputRootElement"],
    div[data-testid="stTextAreaRootElement"],
    div[data-testid="stSelectbox"] div:has(> input[aria-label]),
    div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
    div[data-testid="stDateInput"] div[data-baseweb="input"],
    div[data-testid="stNumberInput"] div[data-baseweb="input"],
    div[data-testid="stTimeInput"] div[data-baseweb="input"] {
        border: 1px solid #7897b2 !important;
        border-radius: 9px !important;
        background: #fbfaf7 !important;
        box-shadow:
            0 0 0 1px rgba(71, 102, 130, 0.1),
            0 2px 5px rgba(16, 42, 67, 0.06) !important;
        box-sizing: border-box !important;
        transition:
            border-color 140ms ease,
            box-shadow 140ms ease !important;
    }

    div[data-testid="stTextInputRootElement"] input,
    div[data-testid="stTextAreaRootElement"] textarea,
    div[data-testid="stSelectbox"] div:has(> input[aria-label]) input,
    div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div input,
    div[data-testid="stTextInput"] input,
    div[data-testid="stDateInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTimeInput"] input {
        border: 0 !important;
        background-color: transparent !important;
        box-shadow: none !important;
    }

    div[data-testid="stTextInputRootElement"]:hover,
    div[data-testid="stTextAreaRootElement"]:hover,
    div[data-testid="stSelectbox"] div:has(> input[aria-label]):hover,
    div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div:hover,
    div[data-testid="stDateInput"] div[data-baseweb="input"]:hover,
    div[data-testid="stNumberInput"] div[data-baseweb="input"]:hover,
    div[data-testid="stTimeInput"] div[data-baseweb="input"]:hover {
        border-color: #496d8b !important;
    }

    div[data-testid="stTextInputRootElement"]:focus-within,
    div[data-testid="stTextAreaRootElement"]:focus-within,
    div[data-testid="stSelectbox"] div:has(> input[aria-label]):focus-within,
    div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div:focus-within,
    div[data-testid="stDateInput"] div[data-baseweb="input"]:focus-within,
    div[data-testid="stNumberInput"] div[data-baseweb="input"]:focus-within,
    div[data-testid="stTimeInput"] div[data-baseweb="input"]:focus-within {
        border-color: #0f6cbd !important;
        box-shadow: 0 0 0 3px rgba(15, 108, 189, 0.15) !important;
        outline: none !important;
    }

    div[data-testid="stTextAreaRootElement"] textarea {
        min-height: 6rem;
    }
</style>
"""


def apply_input_theme() -> None:
    st.markdown(FORM_CONTROL_STYLES, unsafe_allow_html=True)
