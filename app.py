from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from services.aws_claim_service import upload_aws_claim_package
from services.aws_claim_workflow_service import (
    start_document_processing,
)
from services.claim_record_service import (
    build_claim_record,
    check_policy_eligibility,
)
from services.claim_submission_service import (
    ClaimSubmissionResult,
    ClaimUpload,
    submit_claim,
)
from services.policy_record_service import get_policy_record
from ui.input_theme import apply_input_theme
from ui.notices import render_notice
from ui.sidebar import render_sidebar
from ui.styles import apply_shared_styles


st.set_page_config(
    page_title="Vehicle Claims Portal",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="expanded",
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
            max-width: 1240px;
            padding-top: 1.8rem;
            padding-bottom: 4rem;
        }

        .portal-hero {
            padding: 0.8rem 0 1.35rem 0;
        }

        .portal-kicker,
        .decision-kicker {
            color: #0f6cbd;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .portal-title {
            margin: 0.35rem 0 0.55rem 0;
            color: #102a43;
            font-size: clamp(2rem, 4vw, 3.2rem);
            line-height: 1.08;
            letter-spacing: -0.04em;
        }

        .portal-subtitle {
            max-width: 780px;
            margin: 0;
            color: #52667a;
            font-size: 1.02rem;
            line-height: 1.65;
        }

        .process-steps {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            margin: 0.15rem 0 1.3rem 0;
            overflow: hidden;
            border: 1px solid #d9e2ec;
            border-radius: 14px;
            background: #ffffff;
            box-shadow: 0 8px 25px rgba(16, 42, 67, 0.05);
        }

        .process-step {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            padding: 0.85rem 1rem;
            color: #627d98;
            font-size: 0.86rem;
            font-weight: 700;
            border-right: 1px solid #e7edf3;
        }

        .process-step:last-child { border-right: 0; }

        .process-step.active {
            color: #0b4f87;
            background: #edf6ff;
        }

        .process-step.completed {
            color: #0b6847;
            background: #f0faf5;
        }

        .process-step.completed .step-number {
            background: #11875d;
        }

        .step-number {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.75rem;
            height: 1.75rem;
            border-radius: 50%;
            color: #ffffff;
            background: #0f6cbd;
            font-size: 0.78rem;
            font-weight: 800;
        }

        .section-heading {
            margin-bottom: 0.15rem;
            color: #102a43;
            font-size: 1.22rem;
            font-weight: 800;
        }

        .section-copy {
            margin: 0 0 0.9rem 0;
            color: #6b7f93;
            font-size: 0.88rem;
            line-height: 1.55;
        }

        .evidence-checklist {
            margin: 0.6rem 0 1rem 0;
            padding: 0.85rem 1rem;
            border-left: 4px solid #0f6cbd;
            border-radius: 8px;
            color: #425b72;
            background: #edf6ff;
            font-size: 0.84rem;
            line-height: 1.65;
        }

        .decision-card {
            margin: 0.5rem 0 1.2rem 0;
            padding: 1.35rem 1.5rem;
            border: 1px solid #d9e2ec;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 12px 35px rgba(16, 42, 67, 0.08);
        }

        .decision-card.pass {
            border-left: 5px solid #11875d;
            background: linear-gradient(100deg, #edf9f3, #ffffff 46%);
        }

        .decision-card.review {
            border-left: 5px solid #d98700;
            background: linear-gradient(100deg, #fff8e8, #ffffff 46%);
        }

        .decision-card.fail {
            border-left: 5px solid #c83b3b;
            background: linear-gradient(100deg, #fff1f1, #ffffff 46%);
        }

        .decision-title {
            margin: 0.35rem 0 0.25rem 0;
            color: #102a43;
            font-size: 1.55rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }

        .decision-copy {
            margin: 0;
            color: #52667a;
            line-height: 1.55;
        }

        .status-pill {
            display: inline-block;
            padding: 0.24rem 0.6rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 800;
            letter-spacing: 0.06em;
        }

        .status-pill.pass {
            color: #0b6847;
            background: #e3f5ec;
            border: 1px solid #a8dfc7;
        }

        .status-pill.review {
            color: #965d00;
            background: #fff1cc;
            border: 1px solid #efd187;
        }

        .status-pill.fail {
            color: #a12626;
            background: #ffe3e3;
            border: 1px solid #efb2b2;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 255, 0.96);
            border-color: #d9e2ec !important;
            border-radius: 16px;
            box-shadow: 0 8px 25px rgba(16, 42, 67, 0.05);
        }

        div[data-testid="stMetric"] {
            min-height: 108px;
            padding: 0.95rem;
            border: 1px solid #e0e7ef;
            border-radius: 13px;
            background: #ffffff;
        }

        div[data-testid="stMetricLabel"] { color: #627d98; }
        div[data-testid="stMetricValue"] { color: #102a43; font-weight: 750; }

        div[data-testid="stFileUploaderDropzone"] {
            border: 1px dashed #7eb5df;
            border-radius: 13px;
            background: #f4f9fd;
        }

        .stButton > button {
            min-height: 2.75rem;
            padding: 0.6rem 1rem;
            border-radius: 9px;
            font-weight: 750;
            box-shadow: none;
        }

        .stButton > button[kind="primary"] {
            color: white;
            border: 1px solid #0f6cbd;
            background: #0f6cbd;
            box-shadow: 0 5px 14px rgba(15, 108, 189, 0.18);
        }

        .stButton > button[kind="primary"]:hover {
            color: white;
            border-color: #0b5a9d;
            background: #0b5a9d;
        }

        .stButton > button[kind="secondary"] {
            color: #0f5f9f;
            border: 1px solid #b8cadb;
            background: #ffffff;
        }

        .stButton > button[kind="secondary"]:hover {
            color: #0b4f87;
            border-color: #7aa7ca;
            background: #f3f8fc;
        }

        div[data-testid="stExpander"] {
            border: 1px solid #d9e2ec;
            border-radius: 13px;
            background: #ffffff;
        }

        .small-note {
            color: #6b7f93;
            font-size: 0.82rem;
            line-height: 1.55;
        }

        .upload-card-title {
            min-height: 2.8rem;
            margin: 0 0 0.35rem 0;
            color: #102a43;
            font-size: 1.08rem;
            font-weight: 800;
            line-height: 1.3;
            letter-spacing: -0.015em;
        }

        .upload-required-marker {
            color: #c83b3b;
            font-weight: 850;
        }

        div[class*="_uploader_slot"] {
            min-height: 6.1rem;
        }

        div[class*="_preview_slot"] {
            min-height: 16.8rem;
        }

        div[class*="_input_card"] {
            min-height: 31rem;
        }

        div[class*="_input_card"] div[data-testid="stVerticalBlockBorderWrapper"] {
            overflow: visible !important;
        }

        div[class*="_preview_slot"] div[data-testid="stImage"] img {
            width: 100% !important;
            height: 13.8rem !important;
            object-fit: contain !important;
            object-position: center !important;
        }

        .upload-preview-placeholder {
            height: 13.8rem;
            border: 1px dashed #c7d5e2;
            border-radius: 10px;
            color: #829ab1;
            background: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 0.82rem;
        }

        #MainMenu, footer { visibility: hidden; }

        @media (max-width: 760px) {
            .process-steps { grid-template-columns: 1fr; }
            .process-step { border-right: 0; border-bottom: 1px solid #e7edf3; }
            .process-step:last-child { border-bottom: 0; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

apply_shared_styles()
apply_input_theme()
render_sidebar()


CLAIM_CATEGORIES = [
    "Partial loss (vehicle damage)",
]


STEP_CONTENT = {
    1: {
        "title": "Tell us about the claim",
        "subtitle": (
            "Provide the policyholder and incident information to verify "
            "the policy before submitting evidence."
        ),
    },
    2: {
        "title": "Submit claim evidence",
        "subtitle": (
            "Upload KTP, SIM, STNK, and the required vehicle-damage photos. "
            "Your files will be saved for a claims agent to review."
        ),
    },
    3: {
        "title": "Claim submitted",
        "subtitle": (
            "Your claim and supporting evidence have been received for review."
        ),
    },
}


def initialize_claim_state() -> None:
    if "claim_step" not in st.session_state:
        st.session_state["claim_step"] = 1

    if "claim_draft" not in st.session_state:
        st.session_state["claim_draft"] = {
            "policy_number": "",
            "claimant_name": "",
            "phone_number": "",
            "email_address": "",
            "claim_category": CLAIM_CATEGORIES[0],
            "incident_date": date.today(),
            "incident_location": "",
            "incident_description": "",
            "declaration": False,
        }


def step_class(
    step_number: int,
    current_step: int,
) -> str:
    if step_number < current_step:
        return "process-step completed"

    if step_number == current_step:
        return "process-step active"

    return "process-step"


def normalize_person_name(value: str) -> str:
    return " ".join(value.casefold().split())


def render_claim_header(
    current_step: int,
) -> None:
    content = STEP_CONTENT[current_step]

    st.markdown(
        f"""
        <div class="portal-hero">
            <div class="portal-kicker">Vehicle insurance claims</div>
            <h1 class="portal-title">{content['title']}</h1>
            <p class="portal-subtitle">{content['subtitle']}</p>
        </div>
        <div class="process-steps">
            <div class="{step_class(1, current_step)}">
                <span class="step-number">1</span> Claim details
            </div>
            <div class="{step_class(2, current_step)}">
                <span class="step-number">2</span> Submit evidence
            </div>
            <div class="{step_class(3, current_step)}">
                <span class="step-number">3</span> Review and next step
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_claim_details_step() -> None:
    draft = dict(st.session_state["claim_draft"])

    with st.container(border=True):
        st.markdown(
            '<div class="section-heading">Claim and policy details</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="section-copy">Enter the information used to identify the policyholder and affected policy.</p>',
            unsafe_allow_html=True,
        )

        details_col1, details_col2 = st.columns(2, gap="large")

        with details_col1:
            policy_number = st.text_input(
                "Policy number *",
                value=draft["policy_number"],
                placeholder="For example: POL-2026-000123",
                key="claim_policy_number_input",
            )
            claimant_name = st.text_input(
                "Policyholder name *",
                value=draft["claimant_name"],
                placeholder="Full name on the policy",
                key="claimant_name_input",
            )

        with details_col2:
            phone_number = st.text_input(
                "Mobile number *",
                value=draft["phone_number"],
                placeholder="For claim-status updates",
                key="claim_phone_input",
            )
            email_address = st.text_input(
                "Email address",
                value=draft["email_address"],
                placeholder="Optional",
                key="claim_email_input",
            )

        st.divider()
        st.markdown(
            '<div class="section-heading">Incident details</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="section-copy">Tell us when and where the incident occurred and provide a short chronology.</p>',
            unsafe_allow_html=True,
        )

        incident_col1, incident_col2 = st.columns(2, gap="large")

        with incident_col1:
            category_index = (
                CLAIM_CATEGORIES.index(draft["claim_category"])
                if draft["claim_category"] in CLAIM_CATEGORIES
                else 0
            )
            claim_category = st.selectbox(
                "Claim category *",
                CLAIM_CATEGORIES,
                index=category_index,
                key="claim_category_input",
            )
            incident_date = st.date_input(
                "Incident date *",
                value=draft["incident_date"],
                max_value=date.today(),
                key="claim_incident_date_input",
            )

        with incident_col2:
            incident_location = st.text_input(
                "Incident location *",
                value=draft["incident_location"],
                placeholder="City, road, or nearest landmark",
                key="claim_location_input",
            )
            incident_description = st.text_area(
                "Incident chronology *",
                value=draft["incident_description"],
                placeholder="Briefly explain what happened and which part of the vehicle was affected.",
                height=120,
                key="claim_description_input",
            )

    _, next_column = st.columns([5.4, 1.6])

    with next_column:
        continue_button = st.button(
            "Continue to evidence submission",
            type="primary",
            width="stretch",
            key="continue_to_documents",
        )

    if continue_button:
        updated_draft = {
            **draft,
            "policy_number": policy_number.strip(),
            "claimant_name": claimant_name.strip(),
            "phone_number": phone_number.strip(),
            "email_address": email_address.strip(),
            "claim_category": claim_category,
            "incident_date": incident_date,
            "incident_location": incident_location.strip(),
            "incident_description": incident_description.strip(),
        }
        st.session_state["claim_draft"] = updated_draft

        missing_fields = []

        if not updated_draft["policy_number"]:
            missing_fields.append("Policy number")
        if not updated_draft["claimant_name"]:
            missing_fields.append("Policyholder name")
        if not updated_draft["phone_number"]:
            missing_fields.append("Mobile number")
        if not updated_draft["incident_location"]:
            missing_fields.append("Incident location")
        if not updated_draft["incident_description"]:
            missing_fields.append("Incident chronology")

        if missing_fields:
            render_notice(
                "Complete the following before continuing: "
                + ", ".join(missing_fields)
                + ".",
                "warning",
            )
        else:
            try:
                policy_record = get_policy_record(
                    updated_draft["policy_number"]
                )
            except Exception as error:
                render_notice(
                    "The policy record could not be retrieved: "
                    f"{error}",
                    "error",
                )
                return

            if policy_record is None:
                render_notice(
                    "No matching policy was found. Check the policy number "
                    "and try again.",
                    "error",
                )
                return

            if normalize_person_name(
                updated_draft["claimant_name"]
            ) != normalize_person_name(
                policy_record.customer_name
            ):
                render_notice(
                    "The policyholder name could not be verified against "
                    "the policy record.",
                    "error",
                )
                return

            eligibility = check_policy_eligibility(
                policy_record=policy_record,
                incident_date=updated_draft["incident_date"],
            )

            if not eligibility["eligible"]:
                for explanation in eligibility["explanations"]:
                    render_notice(explanation, "error")
                return

            existing_claim_record = st.session_state.get("claim_record")
            existing_claim_id = None

            if (
                isinstance(existing_claim_record, dict)
                and existing_claim_record.get("policy_number")
                == policy_record.policy_number
            ):
                existing_claim_id = existing_claim_record.get("claim_id")

            claim_record = build_claim_record(
                policy_record=policy_record,
                incident_date=updated_draft["incident_date"],
                incident_location=updated_draft["incident_location"],
                damage_description=updated_draft["incident_description"],
                submitted_claimant_name=updated_draft["claimant_name"],
                claim_id=existing_claim_id,
            )

            st.session_state["claim_policy_record"] = policy_record
            st.session_state["claim_record"] = claim_record
            st.session_state["claim_step"] = 2
            st.rerun()


DOCUMENT_UPLOAD_CONFIG = {
    "ktp": {
        "label": "KTP identity document",
        "help": "Upload the policyholder's KTP image.",
        "bytes_key": "claim_ktp_bytes",
        "name_key": "claim_ktp_name",
        "widget_key": "claim_ktp_input",
    },
    "sim": {
        "label": "SIM driver licence",
        "help": "Upload the driver's SIM image.",
        "bytes_key": "claim_sim_bytes",
        "name_key": "claim_sim_name",
        "widget_key": "claim_sim_input",
    },
    "stnk": {
        "label": "STNK vehicle registration",
        "help": "Upload the insured vehicle's STNK image.",
        "bytes_key": "claim_stnk_bytes",
        "name_key": "claim_stnk_name",
        "widget_key": "claim_stnk_input",
    },
}


VEHICLE_UPLOAD_CONFIG = {
    "primary_damage": {
        "label": "Primary vehicle damage photo *",
        "help": "Show the real vehicle and damaged area clearly in one photo.",
        "bytes_key": "claim_primary_damage_bytes",
        "name_key": "claim_primary_damage_name",
        "widget_key": "claim_primary_damage_input",
        "required": True,
    },
    "additional_1": {
        "label": "Additional photo 1",
        "help": "Optional supporting context or alternate damage view.",
        "bytes_key": "claim_additional_1_bytes",
        "name_key": "claim_additional_1_name",
        "widget_key": "claim_additional_1_input",
        "required": False,
    },
    "additional_2": {
        "label": "Additional photo 2",
        "help": "Optional supporting context or alternate damage view.",
        "bytes_key": "claim_additional_2_bytes",
        "name_key": "claim_additional_2_name",
        "widget_key": "claim_additional_2_input",
        "required": False,
    },
}


def collect_claim_uploads() -> list[ClaimUpload]:
    uploads: list[ClaimUpload] = []

    for document_type, config in DOCUMENT_UPLOAD_CONFIG.items():
        content = st.session_state.get(config["bytes_key"])
        filename = st.session_state.get(config["name_key"])

        if content and filename:
            uploads.append(
                ClaimUpload(
                    evidence_type=document_type,
                    original_filename=filename,
                    content=content,
                )
            )

    for image_slot, config in VEHICLE_UPLOAD_CONFIG.items():
        content = st.session_state.get(config["bytes_key"])
        filename = st.session_state.get(config["name_key"])

        if content and filename:
            uploads.append(
                ClaimUpload(
                    evidence_type="vehicle_image",
                    image_slot=image_slot,
                    original_filename=filename,
                    content=content,
                )
            )

    return uploads


@st.fragment
def render_upload_card(
    *,
    label: str,
    help_text: str,
    widget_key: str,
    bytes_key: str,
    name_key: str,
) -> None:
    is_required = label.rstrip().endswith("*")
    clean_label = label.rstrip().removesuffix("*").rstrip()
    required_marker = (
        '&nbsp;<span class="upload-required-marker" aria-label="required">*</span>'
        if is_required
        else ""
    )

    with st.container(
        border=True,
        key=f"{widget_key}_card",
    ):
        st.markdown(
            f'<div class="upload-card-title">{escape(clean_label)}'
            f"{required_marker}</div>",
            unsafe_allow_html=True,
        )
        st.caption(help_text)
        with st.container(key=f"{widget_key}_uploader_slot"):
            uploaded_file = st.file_uploader(
                label,
                type=["png", "jpg", "jpeg"],
                key=widget_key,
                label_visibility="collapsed",
            )

        if uploaded_file is not None:
            st.session_state[bytes_key] = uploaded_file.getvalue()
            st.session_state[name_key] = uploaded_file.name

        content = st.session_state.get(bytes_key)
        filename = st.session_state.get(name_key)

        with st.container(key=f"{widget_key}_preview_slot"):
            if content and filename:
                st.image(
                    content,
                    caption=filename,
                    width="stretch",
                )
                st.caption(
                    f"{len(content) / (1024 * 1024):.2f} MB "
                    "· Ready to submit"
                )
            else:
                st.markdown(
                    '<div class="upload-preview-placeholder">'
                    "Image preview will appear here."
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.caption("No file selected.")


def render_customer_evidence_step() -> None:
    draft = dict(st.session_state["claim_draft"])
    claim_record = st.session_state.get("claim_record")

    if not isinstance(claim_record, dict):
        render_notice(
            "Verify the claim details before uploading evidence.",
            "warning",
        )
        if st.button("Return to claim details", key="evidence_missing_claim"):
            st.session_state["claim_step"] = 1
            st.rerun()
        return

    vehicle = claim_record.get("vehicle", {})

    with st.container(border=True):
        st.markdown("### Verified policy summary")
        summary1, summary2, summary3 = st.columns(3)
        with summary1:
            st.caption("Policy number")
            st.write(f"**{claim_record['policy_number']}**")
        with summary2:
            st.caption("Policyholder")
            st.write(f"**{claim_record['customer_name']}**")
        with summary3:
            st.caption("Insured vehicle")
            st.write(
                f"**{vehicle.get('make', '')} {vehicle.get('model', '')} · "
                f"{vehicle.get('plate_number', '')}**"
            )

    st.markdown("### Required documents")
    st.caption("Upload clear PNG, JPG, or JPEG images. Maximum size: 10 MB each.")
    document_columns = st.columns(3, gap="large")

    for column, config in zip(
        document_columns,
        DOCUMENT_UPLOAD_CONFIG.values(),
    ):
        with column:
            render_upload_card(
                label=config["label"] + " *",
                help_text=config["help"],
                widget_key=config["widget_key"],
                bytes_key=config["bytes_key"],
                name_key=config["name_key"],
            )

    st.markdown("### Required vehicle photo")
    st.caption(
        "Upload one original photo that clearly shows the real vehicle and damaged area."
    )
    required_columns = st.columns(3, gap="large")
    required_configs = [
        config
        for config in VEHICLE_UPLOAD_CONFIG.values()
        if config["required"]
    ]

    for column, config in zip(required_columns, required_configs):
        with column:
            render_upload_card(
                label=config["label"],
                help_text=config["help"],
                widget_key=config["widget_key"],
                bytes_key=config["bytes_key"],
                name_key=config["name_key"],
            )

    with st.expander("Add optional supporting photos"):
        optional_columns = st.columns(2, gap="large")
        optional_configs = [
            config
            for config in VEHICLE_UPLOAD_CONFIG.values()
            if not config["required"]
        ]
        for column, config in zip(optional_columns, optional_configs):
            with column:
                render_upload_card(
                    label=config["label"],
                    help_text=config["help"],
                    widget_key=config["widget_key"],
                    bytes_key=config["bytes_key"],
                    name_key=config["name_key"],
                )

    declaration = st.checkbox(
        "I confirm that these documents and photos are genuine and relate to this claim.",
        value=draft.get("declaration", False),
        key="claim_submission_declaration_input",
    )
    render_notice(
        "After submission, the documents will be reviewed before the vehicle "
        "damage photo is assessed."
    )

    _, back_column, submit_column = st.columns([4.0, 1.2, 1.5])
    with back_column:
        back_button = st.button(
            "Back to claim details",
            width="stretch",
            key="customer_evidence_back",
        )
    with submit_column:
        submit_button = st.button(
            "Submit claim",
            type="primary",
            width="stretch",
            key="submit_customer_claim",
        )

    if back_button:
        draft["declaration"] = declaration
        st.session_state["claim_draft"] = draft
        st.session_state["claim_step"] = 1
        st.rerun()

    if not submit_button:
        return

    draft["declaration"] = declaration
    st.session_state["claim_draft"] = draft
    missing_evidence = []

    for document_type, config in DOCUMENT_UPLOAD_CONFIG.items():
        if not st.session_state.get(config["bytes_key"]):
            missing_evidence.append(document_type.upper())

    for config in required_configs:
        if not st.session_state.get(config["bytes_key"]):
            missing_evidence.append(config["label"].rstrip(" *"))

    if not declaration:
        missing_evidence.append("Evidence declaration")

    if missing_evidence:
        render_notice(
            "Complete the following before submission: "
            + ", ".join(missing_evidence)
            + ".",
            "warning",
        )
        return

    claim_uploads = collect_claim_uploads()

    with st.spinner("Submitting the claim and supporting evidence..."):
        try:
            submission_result = submit_claim(
                claim_record=claim_record,
                phone_number=draft["phone_number"],
                email_address=draft["email_address"],
                claim_category=draft["claim_category"],
                uploads=claim_uploads,
            )
        except Exception as error:
            render_notice(
                f"The claim could not be submitted: {error}",
                "error",
            )
            return

        try:
            upload_aws_claim_package(
                claim_id=submission_result.claim_id,
                claim_record=claim_record,
                uploads=claim_uploads,
            )
            start_document_processing(submission_result.claim_id)
        except Exception as error:
            st.session_state["claim_background_warning"] = str(error)
        else:
            st.session_state.pop("claim_background_warning", None)

    st.session_state["claim_submission_result"] = submission_result
    st.session_state["claim_step"] = 3
    st.rerun()


def reset_claim_journey() -> None:
    keys_to_clear = [
        "claim_draft",
        "claim_policy_record",
        "claim_record",
        "claim_ktp_bytes",
        "claim_ktp_name",
        "claim_sim_bytes",
        "claim_sim_name",
        "claim_stnk_bytes",
        "claim_stnk_name",
        "claim_image_bytes",
        "claim_image_name",
        "claim_submission_result",
        "claim_background_warning",
        "claim_policy_number",
        "claim_policy_number_input",
        "claimant_name_input",
        "claim_phone_input",
        "claim_email_input",
        "claim_category_input",
        "claim_incident_date_input",
        "claim_location_input",
        "claim_description_input",
        "claim_ktp_input",
        "claim_sim_input",
        "claim_stnk_input",
        "claim_vehicle_image_input",
        "claim_declaration_input",
        "claim_submission_declaration_input",
    ]

    for config in VEHICLE_UPLOAD_CONFIG.values():
        keys_to_clear.extend(
            [
                config["bytes_key"],
                config["name_key"],
                config["widget_key"],
            ]
        )

    for key in keys_to_clear:
        st.session_state.pop(key, None)

    st.session_state["claim_step"] = 1


def render_submission_confirmation() -> None:
    result = st.session_state.get("claim_submission_result")

    if not isinstance(result, ClaimSubmissionResult):
        render_notice(
            "No submitted claim is available. "
            "Return to the evidence page and submit the claim.",
            "warning",
        )
        if st.button("Return to evidence submission", key="confirmation_missing"):
            st.session_state["claim_step"] = 2
            st.rerun()
        return

    render_notice(
        "Your vehicle-damage claim was submitted successfully.",
        "success",
    )

    with st.container(border=True):
        st.markdown("### Submission confirmation")
        claim_column, status_column, files_column = st.columns(3)
        with claim_column:
            st.caption("Claim ID")
            st.markdown(f"### {result.claim_id}")
        with status_column:
            st.caption("Current status")
            st.markdown(f"### {result.claim_status}")
        with files_column:
            st.caption("Files received")
            st.markdown(f"### {result.stored_file_count}")

        render_notice("Your claim has been received and is pending initial review.")
        background_warning = st.session_state.get("claim_background_warning")
        if background_warning:
            render_notice(
                "The claim was received, but its initial review could not be started. "
                "Claims staff have been notified.",
                "warning",
            )
        st.caption(
            "Keep the claim ID to track progress and respond to any requests "
            "for additional information."
        )

    _, track_column, new_claim_column = st.columns(
        [3.2, 1.35, 1.35],
        gap="small",
        vertical_alignment="center",
    )
    with track_column:
        if st.button(
            "Track this claim",
            icon=":material/search:",
            width="stretch",
            key="confirmation_track_claim",
        ):
            st.session_state["tracked_claim_id"] = result.claim_id
            st.switch_page("pages/2_Claim_Status.py")
    with new_claim_column:
        if st.button(
            "Start another claim",
            type="primary",
            width="stretch",
            key="confirmation_start_another_claim",
        ):
            reset_claim_journey()
            st.rerun()


initialize_claim_state()

current_step = int(st.session_state.get("claim_step", 1))

if current_step not in {1, 2, 3}:
    current_step = 1
    st.session_state["claim_step"] = 1

render_claim_header(current_step)

if current_step == 1:
    render_claim_details_step()
elif current_step == 2:
    render_customer_evidence_step()
else:
    render_submission_confirmation()
