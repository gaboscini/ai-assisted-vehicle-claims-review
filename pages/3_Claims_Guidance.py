import logging

import streamlit as st

from rag.rag_service import answer_question
from ui.input_theme import apply_input_theme
from ui.notices import render_notice
from ui.sidebar import render_sidebar
from ui.styles import apply_shared_styles


LOGGER = logging.getLogger(__name__)


st.set_page_config(
    page_title="Claims Help Center",
    page_icon="📖",
    layout="wide",
)

st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at 88% 2%, rgba(15, 108, 189, 0.08), transparent 27rem),
                #f4f7fb;
        }

        .block-container {
            max-width: 1120px;
            padding-top: 1.8rem;
            padding-bottom: 4rem;
        }

        .knowledge-hero { padding: 0.8rem 0 1.1rem 0; }

        .knowledge-kicker {
            color: #0f6cbd;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .knowledge-title {
            margin: 0.35rem 0 0.55rem 0;
            color: #102a43;
            font-size: clamp(2rem, 4vw, 3.1rem);
            line-height: 1.06;
            letter-spacing: -0.04em;
        }

        .knowledge-subtitle {
            max-width: 760px;
            margin: 0;
            color: #52667a;
            font-size: 1rem;
            line-height: 1.6;
        }

        .faq-label {
            margin: 1.1rem 0 0.2rem 0;
            color: #102a43;
            font-size: 1.2rem;
            font-weight: 800;
        }

        .faq-copy {
            margin: 0 0 0.8rem 0;
            color: #6b7f93;
            font-size: 0.86rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff;
            border-color: #d9e2ec !important;
            border-radius: 16px;
            box-shadow: 0 8px 25px rgba(16, 42, 67, 0.05);
        }

        div[data-testid="stExpander"] {
            border: 1px solid #d9e2ec;
            border-radius: 13px;
            background: #ffffff;
        }

        .stButton > button {
            min-height: 2.8rem;
            border-radius: 10px;
            font-weight: 700;
        }

        #MainMenu, footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

apply_shared_styles()
apply_input_theme()
render_sidebar()


SUGGESTED_FAQS = [
    "Which documents and information are required for a vehicle claim?",
    "What makes a vehicle damage photo acceptable?",
    "Why can the eligibility-adjusted score be 0% when image quality is good?",
    "What happens after I submit a claim?",
    "Why might replacement evidence be requested?",
    "What do confidence and match scores mean?",
    "When is a claim sent for specialist review?",
    "Who makes the final insurance claim decision?",
]


st.markdown(
    """
    <div class="knowledge-hero">
        <div class="knowledge-kicker">Claims guidance</div>
        <h1 class="knowledge-title">Claims Help Center</h1>
        <p class="knowledge-subtitle">
            Find guidance about vehicle claim submissions, photo requirements,
            evidence checks, and review procedures.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

render_notice(
    "Guidance is based on the available claims procedures. Coverage and claim "
    "decisions remain subject to the applicable policy terms."
)

st.markdown('<div class="faq-label">Frequently asked questions</div>', unsafe_allow_html=True)
st.markdown(
    '<p class="faq-copy">Choose a question below or enter your own.</p>',
    unsafe_allow_html=True,
)

faq_columns = st.columns(2, gap="medium")
for index, faq in enumerate(SUGGESTED_FAQS):
    with faq_columns[index % 2]:
        if st.button(faq, key=f"suggested_faq_{index}", width="stretch"):
            st.session_state["knowledge_question"] = faq


with st.container(border=True):
    st.markdown("### Ask about the claims process")
    question = st.text_area(
        "Your question",
        key="knowledge_question",
        placeholder="Type a question or select one of the frequently asked questions.",
        height=110,
    )

    ask_button = st.button(
        "Search Claims Help",
        type="primary",
        width="stretch",
    )


if ask_button:
    if not question.strip():
        render_notice(
            "Enter a question or select one of the frequently asked questions.",
            "warning",
        )
    else:
        with st.spinner("Searching claims guidance..."):
            try:
                response = answer_question(question=question, top_k=5)
                st.markdown("## Answer")
                with st.container(border=True):
                    st.write(response.answer)

                st.markdown("## Related guidance")
                for rank, chunk in enumerate(response.retrieved_chunks, start=1):
                    source_title = (
                        chunk.source.removesuffix(".md")
                        .replace("_", " ")
                        .title()
                    )
                    with st.expander(f"{rank}. {source_title}"):
                        st.write(chunk.text)
            except Exception:
                LOGGER.exception("Claims guidance search failed")
                render_notice(
                    "Claims guidance is temporarily unavailable. Please try again.",
                    "error",
                )
