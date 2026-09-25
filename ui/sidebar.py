import streamlit as st


SIDEBAR_STYLES = """
<style>
    [data-testid="stSidebarNav"] { display: none; }

    [data-testid="stSidebar"] {
        border-right: 1px solid #d9e2ec;
        background: #ffffff;
    }

    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 1rem;
        padding-left: 0.85rem;
        padding-right: 0.85rem;
    }

    .sidebar-brand {
        margin: 0 0 1.4rem 0;
        padding: 0.7rem 0.15rem 1.1rem 0.15rem;
        border-bottom: 1px solid #e3eaf1;
    }

    .sidebar-brand-header {
        display: flex;
        align-items: center;
        gap: 0.7rem;
    }

    .sidebar-brand-mark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2.15rem;
        height: 2.15rem;
        flex: 0 0 auto;
        border-radius: 10px;
        color: #ffffff;
        font-size: 0.72rem;
        font-weight: 900;
        background: linear-gradient(135deg, #1473c7, #0b4f87);
        box-shadow: 0 7px 17px rgba(15, 108, 189, 0.18);
    }

    .sidebar-brand-title {
        color: #102a43;
        font-size: 0.95rem;
        font-weight: 800;
        line-height: 1.2;
    }

    .sidebar-brand-subtitle {
        margin-top: 0.18rem;
        color: #6b7f93;
        font-size: 0.74rem;
        line-height: 1.45;
    }

    .sidebar-section-label {
        margin: 0 0 0.55rem 0.15rem;
        color: #8294a6;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
        min-height: 2.9rem;
        margin-bottom: 0.35rem;
        padding: 0.58rem 0.72rem;
        border: 1px solid transparent;
        border-radius: 10px;
        color: #425b72;
        font-size: 0.86rem;
        font-weight: 700;
    }

    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
        border-color: #dce6ef;
        color: #0b4f87;
        background: #f4f8fc;
    }

    [data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
        border-color: #c9e1f4;
        color: #0b4f87;
        background: #eaf4fc;
        box-shadow: inset 3px 0 0 #0f6cbd;
    }

</style>
"""


def render_sidebar() -> None:
    st.markdown(SIDEBAR_STYLES, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-header">
                    <div class="sidebar-brand-mark">VC</div>
                    <div>
                        <div class="sidebar-brand-title">Vehicle Claims</div>
                        <div class="sidebar-brand-subtitle">Claims service portal</div>
                    </div>
                </div>
            </div>
            <div class="sidebar-section-label">Claims services</div>
            """,
            unsafe_allow_html=True,
        )

        st.page_link("app.py", label="Submit a Claim", icon=":material/description:")
        st.page_link(
            "pages/2_Claim_Status.py",
            label="Track a Claim",
            icon=":material/search:",
        )
        st.page_link(
            "pages/1_Agent_Dashboard.py",
            label="Agent Dashboard",
            icon=":material/space_dashboard:",
        )
        st.page_link(
            "pages/2_knowledge_Assistant.py",
            label="Claims Help",
            icon=":material/help_center:",
        )
