from __future__ import annotations

from html import escape

import streamlit as st


def render_notice(message: object, kind: str = "info") -> None:
    notice_kind = kind if kind in {"info", "success", "warning", "error"} else "info"
    st.markdown(
        (
            f'<div class="app-notice app-notice--{notice_kind}" role="status">'
            f"{escape(str(message))}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
