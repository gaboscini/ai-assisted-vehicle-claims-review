from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from services.aws_claim_service import (
    get_aws_claim_record,
    get_aws_claim_status,
    prepare_aws_claim_resubmission,
    upload_aws_replacement_evidence,
)
from services.aws_claim_workflow_service import (
    start_document_processing,
    start_vehicle_image_processing,
)
from services.claim_workflow_service import (
    EVIDENCE_LABELS,
    get_customer_claim_status,
    make_replacement_upload,
)
from services.claim_report_service import (
    EXCEL_MIME_TYPE,
    build_customer_claim_report,
    customer_report_filename,
)
from ui.input_theme import apply_input_theme
from ui.notices import render_notice
from ui.sidebar import render_sidebar
from ui.styles import apply_shared_styles


st.set_page_config(
    page_title="Track Vehicle Claim",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .stApp { background: #f4f7fb; }
        .block-container {
            max-width: 1080px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        .status-kicker {
            color: #0f6cbd;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .status-title {
            margin: 0.35rem 0 0.45rem 0;
            color: #102a43;
            font-size: clamp(2rem, 4vw, 3rem);
            line-height: 1.1;
            letter-spacing: -0.04em;
        }
        .status-subtitle {
            max-width: 720px;
            margin: 0 0 1.3rem 0;
            color: #627d98;
            line-height: 1.6;
        }
        div[data-testid="stMetric"] {
            min-height: 102px;
            padding: 0.9rem 1rem;
            border: 1px solid #d9e2ec;
            border-radius: 13px;
            background: #ffffff;
        }
        .tracking-summary-card {
            min-height: 108px;
            padding: 0.95rem 1rem;
            border: 1px solid #d9e2ec;
            border-radius: 13px;
            background: #ffffff;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .tracking-summary-label {
            margin-bottom: 0.55rem;
            color: #52667a;
            font-size: 0.8rem;
            font-weight: 650;
        }
        .tracking-summary-value {
            color: #102a43;
            font-size: clamp(1rem, 1.55vw, 1.22rem);
            font-weight: 650;
            line-height: 1.25;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        .tracking-section-gap {
            height: 1rem;
        }
        .replacement-card-title {
            min-height: 3.25rem;
            margin: 0 0 0.35rem 0;
            color: #102a43;
            font-size: 1.05rem;
            font-weight: 800;
            line-height: 1.25;
        }
        .stButton > button {
            min-height: 2.8rem;
            border-radius: 10px;
            font-weight: 750;
        }
        .st-key-claim_lookup_controls div[data-testid="stTextInput"],
        .st-key-claim_lookup_controls div[data-testid="stButton"] {
            margin-bottom: 0 !important;
        }
        #MainMenu, footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

apply_shared_styles()
apply_input_theme()
render_sidebar()


def render_tracking_summary_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="tracking-summary-card">
            <div class="tracking-summary-label">{escape(label)}</div>
            <div class="tracking-summary-value">{escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_updated_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return value
    return parsed.strftime("%d %b %Y, %I:%M %p")


def customer_status_message(local_claim) -> str:
    if local_claim is None:
        return "Your claim is being reviewed."
    if local_claim.claim_status == "SUBMITTED":
        return "We have received your claim. It is currently under review."
    if local_claim.claim_status == "READY_FOR_REVIEW":
        return "Your claim review is in progress."
    return (
        local_claim.customer_message
        or "Your claim is being reviewed."
    )


def resolve_customer_status(
    aws_status: dict | None,
    local_claim=None,
) -> tuple[str, str, str]:
    if aws_status is None and local_claim is not None:
        return (
            local_claim.claim_status.replace("_", " ").title(),
            customer_status_message(local_claim),
            local_claim.updated_at,
        )

    if aws_status is None:
        return (
            "Submitted",
            "We have received your claim. Initial checks are being prepared.",
            "",
        )

    aws_claim_status = str(
        aws_status.get("claim_status", "")
    ).upper()
    if aws_claim_status in {
        "APPROVED",
        "REJECTED",
        "NEEDS_INFORMATION",
        "INVESTIGATION",
    }:
        message = str(
            aws_status.get("customer_message")
            or "Your claim status has been updated."
        )
        return (
            aws_claim_status.replace("_", " ").title(),
            message,
            str(
                aws_status.get("updated_at")
                or getattr(local_claim, "updated_at", "")
            ),
        )

    processing_stage = str(
        aws_status.get("processing_stage", "")
    ).upper()

    stage_messages = {
        "DOCUMENTS_VALID": (
            "Document Review",
            "Your documents passed the initial checks and are awaiting "
            "review by a claims officer.",
        ),
        "DOCUMENT_REVIEW_REQUIRED": (
            "Document Review",
            "Your submitted documents require additional review "
            "by a claims officer.",
        ),
        "WAITING_FOR_EVIDENCE": (
            "Needs Information",
            str(
                aws_status.get("customer_message")
                or "Replacement evidence is required."
            ),
        ),
        "DOCUMENT_RESUBMITTED": (
            "Submitted",
            "Your replacement evidence was received and is under review.",
        ),
        "DOCUMENT_PROCESSING": (
            "Review in Progress",
            "Your replacement documents are being checked.",
        ),
        "IMAGE_RESUBMITTED": (
            "Submitted",
            "Your replacement vehicle photo was received and is under review.",
        ),
        "IMAGE_ASSESSMENT_IN_PROGRESS": (
            "Review in Progress",
            "Your submitted claim is currently being reviewed by a "
            "claims officer.",
        ),
        "IMAGE_ASSESSMENT_COMPLETE": (
            "Review in Progress",
            "A claims officer is reviewing your submission and will "
            "determine the next step.",
        ),
    }

    display_status, message = stage_messages.get(
        processing_stage,
        (
            "Review in Progress",
            "Your submitted claim is currently being reviewed.",
        ),
    )

    return (
        display_status,
        message,
        str(
            aws_status.get("updated_at")
            or getattr(local_claim, "updated_at", "")
        ),
    )


st.markdown(
    """
    <div class="status-kicker">Customer claim service</div>
    <h1 class="status-title">Track your vehicle claim</h1>
    <p class="status-subtitle">
        Enter the claim ID from your submission confirmation to see its current
        status and respond when replacement evidence is requested.
    </p>
    """,
    unsafe_allow_html=True,
)

submission_result = st.session_state.get("claim_submission_result")
default_claim_id = getattr(submission_result, "claim_id", "")

with st.container(key="claim_lookup_controls"):
    lookup_column, button_column = st.columns(
        [4.5, 1.2],
        gap="medium",
        vertical_alignment="bottom",
    )
    with lookup_column:
        entered_claim_id = st.text_input(
            "Claim ID",
            value=st.session_state.get("tracked_claim_id", default_claim_id),
            placeholder="Enter your claim ID",
        )
    with button_column:
        lookup_clicked = st.button(
            "Check status",
            type="primary",
            width="stretch",
        )

if lookup_clicked:
    st.session_state["tracked_claim_id"] = entered_claim_id.strip().upper()

tracked_claim_id = st.session_state.get("tracked_claim_id", "")
if not tracked_claim_id and default_claim_id:
    tracked_claim_id = default_claim_id
    st.session_state["tracked_claim_id"] = tracked_claim_id

if not tracked_claim_id:
    render_notice("Enter a claim ID to view its current status.")
    st.stop()

try:
    aws_status = get_aws_claim_status(tracked_claim_id)
    aws_claim_record = get_aws_claim_record(tracked_claim_id)
except Exception as error:
    render_notice(
        f"The claim status could not be loaded from AWS: {error}",
        "error",
    )
    st.stop()

try:
    local_claim = get_customer_claim_status(tracked_claim_id)
except Exception:
    local_claim = None

if aws_status is None and aws_claim_record is None and local_claim is None:
    render_notice("No claim was found with that claim ID.", "warning")
    st.stop()

claim_id = tracked_claim_id.strip().upper()
policy_number = str(
    (aws_status or {}).get("policy_number")
    or (aws_claim_record or {}).get("policy_number")
    or getattr(local_claim, "policy_number", "")
)
incident_date = str(
    (aws_claim_record or {}).get("incident_date")
    or getattr(local_claim, "incident_date", "")
)

display_status, status_message, status_updated_at = (
    resolve_customer_status(aws_status, local_claim)
)

st.divider()
claim_column, policy_column, date_column, status_column = st.columns(
    4,
    gap="medium",
)
with claim_column:
    render_tracking_summary_card("Claim ID", claim_id)
with policy_column:
    render_tracking_summary_card("Policy number", policy_number or "—")
with date_column:
    render_tracking_summary_card("Incident date", incident_date or "—")
with status_column:
    render_tracking_summary_card(
        "Status",
        display_status,
    )

st.markdown('<div class="tracking-section-gap"></div>', unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("### Latest update")
    render_notice(status_message)
    st.caption(
        "Last updated: "
        + (
            format_updated_at(status_updated_at)
            if status_updated_at
            else "Not available"
        )
    )

try:
    customer_report_data = build_customer_claim_report(
        claim_id=claim_id,
        claim_record=aws_claim_record,
        claim_status=aws_status,
        display_status=display_status,
        status_message=status_message,
        local_claim=local_claim,
    )
except Exception as error:
    render_notice(
        f"The Excel claim report could not be prepared: {error}",
        "warning",
    )
else:
    _, report_column = st.columns([4.4, 1.6])
    with report_column:
        st.download_button(
            "Download claim report",
            data=customer_report_data,
            file_name=customer_report_filename(claim_id),
            mime=EXCEL_MIME_TYPE,
            icon=":material/download:",
            width="stretch",
            on_click="ignore",
            key=f"download_customer_report_{claim_id}",
        )

aws_claim_status = str(
    (aws_status or {}).get("claim_status", "")
).upper()
needs_replacement_evidence = (
    aws_claim_status == "NEEDS_INFORMATION"
    if aws_status is not None
    else getattr(local_claim, "claim_status", "") == "NEEDS_INFORMATION"
)
if not needs_replacement_evidence:
    st.stop()

st.markdown("## Upload requested replacement evidence")
st.caption(
    "Upload every item listed below. Accepted formats are PNG, JPG, and JPEG, up to 10 MB each."
)

replacement_uploads = []
missing_uploads = []

if aws_status is not None:
    requested_evidence = list(
        aws_status.get("requested_evidence") or []
    )
else:
    requested_evidence = list(
        getattr(local_claim, "requested_evidence", ())
    )

if not requested_evidence:
    render_notice(
        "The requested replacement items are not available. "
        "Please contact the claims team.",
        "warning",
    )
    st.stop()

for row_start in range(
    0,
    len(requested_evidence),
    3,
):
    row_evidence = requested_evidence[
        row_start:row_start + 3
    ]
    row_has_upload = any(
        st.session_state.get(
            f"replacement_{claim_id}_{evidence_key}"
        )
        is not None
        for evidence_key in row_evidence
    )
    card_height = (
        440
        if row_has_upload
        else 275
    )

    upload_columns = st.columns(
        3,
        gap="large",
    )

    for column, evidence_key in zip(
        upload_columns,
        row_evidence,
    ):
        label = EVIDENCE_LABELS.get(
            evidence_key,
            evidence_key
            .replace("_", " ")
            .title(),
        )

        with column:
            with st.container(
                border=True,
                height=card_height,
                key=(
                    "replacement_card_"
                    f"{claim_id}_"
                    f"{evidence_key}"
                ),
            ):
                st.markdown(
                    '<div class="replacement-card-title">'
                    f"{escape(label)}</div>",
                    unsafe_allow_html=True,
                )
                uploaded_file = st.file_uploader(
                    f"Replacement {label} *",
                    type=["png", "jpg", "jpeg"],
                    key=(
                        f"replacement_"
                        f"{claim_id}_"
                        f"{evidence_key}"
                    ),
                    label_visibility="collapsed",
                )

                if uploaded_file is None:
                    missing_uploads.append(label)
                    st.caption(
                        "No file selected."
                    )
                else:
                    content = (
                        uploaded_file.getvalue()
                    )
                    st.image(
                        content,
                        caption=uploaded_file.name,
                        width="stretch",
                    )
                    st.caption(
                        f"{len(content) / (1024 * 1024):.2f} MB "
                        "· Ready to resubmit"
                    )
                    replacement_uploads.append(
                        make_replacement_upload(
                            evidence_key,
                            filename=(
                                uploaded_file.name
                            ),
                            content=content,
                        )
                    )

declaration = st.checkbox(
    "I confirm that the replacement evidence is genuine and relates to this claim."
)
_, submit_column = st.columns([4.2, 1.5])
with submit_column:
    resubmit_clicked = st.button(
        "Resubmit evidence",
        type="primary",
        width="stretch",
    )

if resubmit_clicked:
    if missing_uploads:
        render_notice(
            "Upload the following requested evidence: "
            + ", ".join(missing_uploads)
            + ".",
            "warning",
        )
    elif not declaration:
        render_notice(
            "Confirm the evidence declaration before resubmitting.",
            "warning",
        )
    else:
        try:
            upload_aws_replacement_evidence(
                claim_id=claim_id,
                uploads=replacement_uploads,
            )
            replacement_keys = [
                (
                    str(upload.image_slot)
                    if upload.evidence_type == "vehicle_image"
                    else str(upload.evidence_type)
                )
                for upload in replacement_uploads
            ]
            reset_result = prepare_aws_claim_resubmission(
                claim_id,
                replaced_evidence=replacement_keys,
            )
            if reset_result["document_replaced"]:
                start_document_processing(claim_id)
            else:
                start_vehicle_image_processing(claim_id)
        except Exception as error:
            render_notice(
                f"Replacement evidence could not be submitted: {error}",
                "error",
            )
        else:
            render_notice(
                "Replacement evidence received. "
                "The claim returned to Submitted status.",
                "success",
            )
            st.rerun()
