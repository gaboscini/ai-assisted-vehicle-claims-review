from __future__ import annotations

from html import escape

import streamlit as st

from services.agent_claim_service import (
    AgentClaimDetail,
    AgentClaimFile,
    AgentClaimSummary,
    get_agent_claim,
    list_agent_claims,
)
from services import aws_claim_service
from services.aws_claim_workflow_service import (
    submit_agent_document_decision,
    submit_agent_final_decision,
)
from services.claim_workflow_service import (
    EVIDENCE_LABELS,
)
from services.claim_report_service import (
    EXCEL_MIME_TYPE,
    agent_report_filename,
    build_agent_claim_assessment_report,
)
from ui.input_theme import apply_input_theme
from ui.notices import render_notice
from ui.sidebar import render_sidebar
from ui.styles import apply_shared_styles


st.set_page_config(
    page_title="Claims Agent Dashboard",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .stApp { background: #f4f7fb; }
        .block-container {
            max-width: 1280px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }
        .agent-kicker {
            color: #0f6cbd;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .agent-title {
            margin: 0.35rem 0 0.45rem 0;
            color: #102a43;
            font-size: clamp(2rem, 4vw, 3rem);
            line-height: 1.1;
            letter-spacing: -0.04em;
        }
        .agent-subtitle {
            max-width: 780px;
            margin: 0 0 1.3rem 0;
            color: #627d98;
            line-height: 1.6;
        }
        .section-title {
            margin: 0 0 0.2rem 0;
            color: #102a43;
            font-size: 1.15rem;
            font-weight: 800;
        }
        .section-copy {
            margin: 0 0 0.9rem 0;
            color: #71869a;
            font-size: 0.86rem;
        }
        .status-strip {
            margin-bottom: 1rem;
            padding: 0.85rem 1rem;
            border-left: 4px solid #0f6cbd;
            border-radius: 9px;
            color: #334e68;
            background: #edf6ff;
        }
        .evidence-meta {
            color: #71869a;
            font-size: 0.78rem;
            line-height: 1.45;
        }
        div[data-testid="stMetric"] {
            min-height: 105px;
            padding: 0.9rem 1rem;
            border: 1px solid #d9e2ec;
            border-radius: 13px;
            background: #ffffff;
        }
        div[data-testid="stMetricValue"] {
            font-size: clamp(1.25rem, 2.2vw, 1.9rem);
            line-height: 1.15;
        }
        div[data-testid="stMetricValue"] > div {
            overflow: visible;
            text-overflow: clip;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        .claim-summary-card {
            min-height: 106px;
            padding: 0.95rem 1rem;
            border: 1px solid #d9e2ec;
            border-radius: 13px;
            background: #ffffff;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        .claim-summary-label {
            margin-bottom: 0.55rem;
            color: #52667a;
            font-size: 0.8rem;
            font-weight: 650;
        }
        .claim-summary-value {
            color: #102a43;
            font-size: clamp(1rem, 1.55vw, 1.22rem);
            font-weight: 650;
            line-height: 1.25;
            overflow-wrap: anywhere;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #d9e2ec;
            border-radius: 12px;
            overflow: hidden;
        }
        .stButton > button {
            min-height: 2.8rem;
            border-radius: 10px;
            font-weight: 750;
        }
        #MainMenu, footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

apply_shared_styles()
apply_input_theme()
render_sidebar()


DOCUMENT_LABELS = {
    "ktp": "KTP identity document",
    "sim": "SIM driver licence",
    "stnk": "STNK vehicle registration",
}

IMAGE_SLOT_LABELS = {
    "primary_damage": "Primary vehicle damage photo",
    "full_context": "Full vehicle and context",
    "damage_closeup": "Damage close-up",
    "alternate_angle": "Alternate damage angle",
    "additional_1": "Additional photo 1",
    "additional_2": "Additional photo 2",
}

AGENT_ACTIONS = {
    "Approve claim": "APPROVE",
    "Request more information": "REQUEST_MORE_INFORMATION",
    "Mark for investigation": "INVESTIGATE",
    "Reject claim": "REJECT",
}

DOCUMENT_REVIEW_STAGES = {
    "DOCUMENT_QUEUED",
    "DOCUMENT_PROCESSING",
    "DOCUMENT_REVIEW",
    "DOCUMENT_FAILED",
}

IMAGE_REVIEW_STAGES = {
    "IMAGE_QUEUED",
    "IMAGE_PROCESSING",
    "FINAL_REVIEW",
    "LEGACY_FINAL_REVIEW",
    "IMAGE_FAILED",
}

FOLLOW_UP_STAGES = {
    "WAITING_FOR_EVIDENCE",
}


def image_assessment_is_authorized(
    claim: object | None,
    aws_status: dict | None = None,
) -> bool:
    if claim is None:
        return False

    agent_decision = str(
        getattr(claim, "agent_decision", "") or ""
    ).upper()
    processing_stage = str(
        getattr(claim, "processing_stage", "") or ""
    ).upper()
    aws_agent_decision = str(
        (aws_status or {}).get("agent_document_decision", "") or ""
    ).upper()
    aws_processing_stage = str(
        (aws_status or {}).get("processing_stage", "") or ""
    ).upper()

    return (
        agent_decision == "PROCEED_TO_IMAGE_ASSESSMENT"
        or processing_stage in IMAGE_REVIEW_STAGES
        or bool((aws_status or {}).get("image_assessment_allowed"))
        or aws_agent_decision == "APPROVED"
        or aws_processing_stage
        in {
            "DOCUMENTS_APPROVED",
            "IMAGE_ASSESSMENT_IN_PROGRESS",
            "IMAGE_ASSESSMENT_COMPLETE",
        }
    )


@st.cache_data(ttl=60, show_spinner=False)
def get_cached_aws_claim_assessment(claim_id: str) -> dict | None:
    try:
        return aws_claim_service.get_aws_claim_assessment(claim_id)
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def get_cached_aws_claim_record(claim_id: str) -> dict | None:
    try:
        return aws_claim_service.get_aws_claim_record(claim_id)
    except Exception:
        return None


@st.cache_data(ttl=30, show_spinner=False)
def get_cached_aws_claim_statuses(
    claim_ids: tuple[str, ...],
) -> dict[str, dict]:
    try:
        batch_reader = getattr(
            aws_claim_service,
            "get_aws_claim_statuses",
            None,
        )
        if batch_reader is not None:
            return batch_reader(claim_ids)

        statuses = {}
        for claim_id in claim_ids:
            status = aws_claim_service.get_aws_claim_status(
                claim_id
            )
            if status is not None:
                statuses[claim_id] = status
        return statuses
    except Exception:
        return {}


def format_size(file_size_bytes: int) -> str:
    return f"{file_size_bytes / (1024 * 1024):.2f} MB"


def render_file_preview(
    claim_file: AgentClaimFile,
    *,
    label: str,
) -> None:
    with st.container(border=True):
        st.markdown(f"#### {label}")

        if claim_file.absolute_path.is_file():
            st.image(
                str(claim_file.absolute_path),
                width="stretch",
            )
        else:
            render_notice("The submitted file could not be found.", "warning")

        st.write(f"**{claim_file.original_filename}**")
        st.markdown(
            f'<div class="evidence-meta">{format_size(claim_file.file_size_bytes)} · '
            f"Uploaded {claim_file.uploaded_at}</div>",
            unsafe_allow_html=True,
        )


def render_file_grid(
    files: list[AgentClaimFile],
    *,
    labels: dict[str, str],
    use_image_slot: bool,
) -> None:
    if not files:
        render_notice("No files were submitted in this section.")
        return

    for row_start in range(0, len(files), 3):
        row_files = files[row_start : row_start + 3]
        columns = st.columns(3, gap="large")

        for column, claim_file in zip(columns, row_files):
            key = (
                claim_file.image_slot
                if use_image_slot
                else claim_file.evidence_type
            )
            label = labels.get(
                key or "",
                key.replace("_", " ").title() if key else "Evidence",
            )
            with column:
                render_file_preview(claim_file, label=label)


def display_label(value: str | None) -> str:
    return (value or "unknown").replace("_", " ").title()


def review_stage_label(stage: str) -> str:
    return {
        "DOCUMENT_QUEUED": "Document review pending",
        "DOCUMENT_PROCESSING": "Document review in progress",
        "DOCUMENT_REVIEW": "Document decision required",
        "DOCUMENT_FAILED": "Document review exception",
        "IMAGE_QUEUED": "Image review pending",
        "IMAGE_PROCESSING": "Image review in progress",
        "FINAL_REVIEW": "Final decision required",
        "LEGACY_FINAL_REVIEW": "Final decision required",
        "IMAGE_FAILED": "Image review exception",
        "WAITING_FOR_EVIDENCE": "Waiting for customer",
        "INVESTIGATION": "Investigation",
        "COMPLETED": "Completed",
    }.get(stage, display_label(stage))


def resolve_processing_stage(
    claim,
    *,
    aws_status: dict | None = None,
    image_assessment_authorized: bool = False,
) -> str:
    """Return the workflow stage without performing network requests."""
    aws_claim_status = str(
        (aws_status or {}).get("claim_status", "")
    ).upper()
    if aws_claim_status in {"APPROVED", "REJECTED"}:
        return "COMPLETED"
    if aws_claim_status == "INVESTIGATION":
        return "INVESTIGATION"
    if aws_claim_status == "NEEDS_INFORMATION":
        return "WAITING_FOR_EVIDENCE"

    status = getattr(claim, "claim_status", "")
    if status in {"APPROVED", "REJECTED"}:
        return "COMPLETED"
    if status == "INVESTIGATION":
        return "INVESTIGATION"
    if status == "NEEDS_INFORMATION":
        return "WAITING_FOR_EVIDENCE"

    aws_stage = str(
        (aws_status or {}).get("processing_stage", "")
    ).upper()
    aws_stage_mapping = {
        "DOCUMENT_PROCESSING_STARTED": "DOCUMENT_PROCESSING",
        "DOCUMENT_REVIEW_REQUIRED": "DOCUMENT_REVIEW",
        "NEEDS_INFORMATION": "WAITING_FOR_EVIDENCE",
        "DOCUMENTS_REJECTED": "COMPLETED",
        "IMAGE_ASSESSMENT_START_FAILED": "IMAGE_FAILED",
        "WAITING_FOR_EVIDENCE": "WAITING_FOR_EVIDENCE",
        "INVESTIGATION": "INVESTIGATION",
        "COMPLETED": "COMPLETED",
    }
    if image_assessment_authorized:
        aws_stage_mapping.update(
            {
                "DOCUMENTS_VALID": "IMAGE_QUEUED",
                "DOCUMENTS_APPROVED": "IMAGE_QUEUED",
                "IMAGE_ASSESSMENT_IN_PROGRESS": "IMAGE_PROCESSING",
                "IMAGE_ASSESSMENT_COMPLETE": "FINAL_REVIEW",
            }
        )
    elif aws_stage in {
        "DOCUMENTS_VALID",
        "IMAGE_ASSESSMENT_IN_PROGRESS",
        "IMAGE_ASSESSMENT_COMPLETE",
    }:
        return "DOCUMENT_REVIEW"

    if aws_stage in aws_stage_mapping:
        return aws_stage_mapping[aws_stage]

    stage = getattr(claim, "processing_stage", None)
    if stage:
        return stage

    return "DOCUMENT_QUEUED"


def render_claim_summary_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="claim-summary-card">
            <div class="claim-summary-label">{escape(label)}</div>
            <div class="claim-summary-value">{escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_percentage(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "—"


def assessment_status_label(status: object) -> str:
    normalized_status = str(status or "").upper()
    return {
        "PASS": "✅ PASS",
        "VALID": "✅ VALID",
        "FAIL": "❌ FAIL",
        "INVALID": "❌ INVALID",
        "REVIEW": "⚠️ REVIEW",
        "NEEDS_REVIEW": "⚠️ NEEDS REVIEW",
        "NOT_SCORED": "— NOT SCORED",
    }.get(normalized_status, display_label(normalized_status))


def render_aws_document_assessment(result: dict) -> None:
    package_status = str(result.get("package_status", "unknown"))
    next_action = str(result.get("next_action", "unknown"))
    document_results = result.get("document_results", {})

    metric1, metric2, metric3 = st.columns(3, gap="medium")
    with metric1:
        render_claim_summary_card(
            "Package status",
            display_label(package_status),
        )
    with metric2:
        render_claim_summary_card(
            "Next action",
            display_label(next_action),
        )
    with metric3:
        render_claim_summary_card(
            "Documents checked",
            f"{len(document_results)} of 3",
        )

    st.markdown(
        '<div class="assessment-section-spacer" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )

    if package_status == "valid":
        render_notice(
            "All required documents passed the configured validation rules.",
            "success",
        )
    elif package_status in {"invalid", "incomplete"}:
        render_notice(
            "One or more required documents did not pass validation.",
            "error",
        )
    else:
        render_notice(
            "One or more document findings require claims-agent review.",
            "warning",
        )

    st.caption(
        f"Threshold profile: {result.get('threshold_profile', 'Not specified')}"
    )

    for document_type in ("ktp", "sim", "stnk"):
        document = document_results.get(document_type)
        document_name = DOCUMENT_LABELS[document_type]

        if document is None:
            render_notice(f"{document_name}: result not available", "error")
            continue

        document_status = str(
            document.get("document_status", "unknown")
        ).upper()
        expander_label = (
            f"{document_name} — "
            f"{assessment_status_label(document_status)}"
        )

        with st.expander(expander_label, expanded=document_status != "VALID"):
            type_column, confidence_column, threshold_column = st.columns(
                3,
                gap="medium",
            )
            detected_document_type = str(
                document.get("detected_document_type")
                or document_type
            ).upper()
            with type_column:
                render_claim_summary_card(
                    "Detected document type",
                    detected_document_type,
                )
            with confidence_column:
                render_claim_summary_card(
                    "Document-type confidence",
                    format_percentage(
                        document.get("document_type_confidence_score")
                    ),
                )
            with threshold_column:
                render_claim_summary_card(
                    "Required threshold",
                    format_percentage(
                        document.get("document_type_confidence_threshold")
                    ),
                )

            st.markdown(
                '<div class="assessment-section-spacer" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )

            field_rows = []
            for field in document.get("field_results", []):
                extracted_value = field.get("extracted_value")
                expected_value = field.get("expected_value")
                field_rows.append(
                    {
                        "Field": field.get(
                            "display_name",
                            display_label(field.get("field_name")),
                        ),
                        "Extracted result": (
                            str(extracted_value)
                            if extracted_value is not None
                            else "Not extracted"
                        ),
                        "Confidence": format_percentage(
                            field.get("extraction_confidence_score")
                        ),
                        "Threshold": format_percentage(
                            field.get("confidence_threshold")
                        ),
                        "Match score": format_percentage(
                            field.get("match_score")
                        ),
                        "Status": assessment_status_label(
                            field.get("status")
                        ),
                        "Expected value": (
                            str(expected_value)
                            if expected_value is not None
                            else "—"
                        ),
                    }
                )

            st.dataframe(
                field_rows,
                hide_index=True,
                width="stretch",
                column_config={
                    "Field": st.column_config.TextColumn(width="medium"),
                    "Extracted result": st.column_config.TextColumn(width="medium"),
                    "Confidence": st.column_config.TextColumn(width="small"),
                    "Threshold": st.column_config.TextColumn(width="small"),
                    "Match score": st.column_config.TextColumn(width="small"),
                    "Status": st.column_config.TextColumn(width="small"),
                    "Expected value": st.column_config.TextColumn(width="medium"),
                },
            )

            findings = document.get("findings", [])
            if findings:
                st.markdown("**Findings**")
                for finding in findings:
                    st.write(f"- {display_label(str(finding))}")


def render_aws_image_assessment(result: dict) -> None:
    damage = result.get("damage_assessment", {})
    recommendation = str(
        result.get("final_recommendation", "unknown")
    )

    metric1, metric2, metric3, metric4 = st.columns(4, gap="medium")
    metric1.metric(
        "Evidence suitability",
        format_percentage(result.get("evidence_suitability_score")),
    )
    metric2.metric(
        "Evidence status",
        display_label(result.get("evidence_status")),
    )
    metric3.metric(
        "Visible severity",
        display_label(damage.get("severity")),
    )
    metric4.metric(
        "Recommendation",
        display_label(recommendation),
    )

    if recommendation == "PROCEED_TO_REVIEW":
        render_notice(
            "Recommendation: Continue to claims-agent review",
            "success",
        )
    elif recommendation in {
        "ESCALATE_FOR_REVIEW",
        "ESCALATE_FOR_INVESTIGATION",
    }:
        render_notice(
            "Recommendation: Detailed claims-agent review required",
            "warning",
        )
    elif recommendation == "REQUEST_BETTER_IMAGE":
        render_notice(
            "Recommendation: Request a replacement vehicle photo",
            "error",
        )
    else:
        render_notice(f"Recommendation: {display_label(recommendation)}")

    reasons = result.get("recommendation_reasons", [])
    for reason in reasons:
        st.write(f"- {reason}")

    st.markdown("### Evidence checks")
    evidence_rows = []
    for check in result.get("evidence_checks", []):
        evidence_rows.append(
            {
                "Check": check.get(
                    "display_name",
                    display_label(check.get("field")),
                ),
                "Result": display_label(str(check.get("result"))),
                "Confidence": format_percentage(
                    check.get("confidence_score")
                ),
                "Threshold": format_percentage(
                    check.get("confidence_threshold")
                ),
                "Status": assessment_status_label(check.get("status")),
            }
        )

    st.dataframe(
        evidence_rows,
        hide_index=True,
        width="stretch",
        column_config={
            "Check": st.column_config.TextColumn(width="medium"),
            "Result": st.column_config.TextColumn(width="medium"),
            "Confidence": st.column_config.TextColumn(width="small"),
            "Threshold": st.column_config.TextColumn(width="small"),
            "Status": st.column_config.TextColumn(width="small"),
        },
    )

    st.markdown("### Visible damage")
    damage_column, recommendation_column = st.columns(2, gap="large")
    with damage_column:
        st.write(
            "**Location:** "
            + (
                ", ".join(
                    display_label(item)
                    for item in damage.get("damage_location", [])
                )
                or "None reported"
            )
        )
        st.write(
            "**Classification:** "
            + (
                ", ".join(
                    display_label(item)
                    for item in damage.get("damage_classification", [])
                )
                or "None reported"
            )
        )
        st.write(
            "**Damaged parts:** "
            + (
                ", ".join(
                    display_label(item)
                    for item in damage.get("damaged_parts", [])
                )
                or "None reported"
            )
        )
    with recommendation_column:
        st.write(
            "**Preliminary repair recommendation:** "
            + display_label(damage.get("repair_recommendation"))
        )
        st.write(
            "**Recommendation confidence:** "
            + format_percentage(
                damage.get("repair_recommendation_confidence")
            )
        )

    summary = damage.get("analyst_summary")
    if summary:
        st.markdown("### Assessment summary")
        st.write(summary)

    limitations = damage.get("limitations", [])
    if limitations:
        st.markdown("### Limitations")
        for limitation in limitations:
            st.write(f"- {limitation}")


@st.dialog("Assessment details", width="large")
def render_ai_result_dialog(claim_id: str) -> None:
    st.caption(f"Claim {claim_id}")
    claim = get_agent_claim(claim_id)
    aws_assessment = get_cached_aws_claim_assessment(claim_id) or {}
    aws_document_result = aws_assessment.get("document_result")
    image_assessment_authorized = image_assessment_is_authorized(
        claim,
        aws_assessment.get("summary"),
    )
    aws_image_result = (
        aws_assessment.get("image_result")
        if image_assessment_authorized
        else None
    )

    if (
        aws_document_result is None
        and aws_image_result is None
    ):
        render_notice(
            "Assessment results are not available yet. Close this window and "
            "return after the initial review is complete."
        )
        return

    try:
        report_data = build_agent_claim_assessment_report(
            claim_id=claim_id,
            claim_record=get_cached_aws_claim_record(claim_id),
            claim_status=aws_assessment.get("summary"),
            document_result=aws_document_result,
            image_result=aws_image_result,
            local_claim=claim,
        )
    except Exception as error:
        render_notice(
            f"The Excel assessment report could not be prepared: {error}",
            "warning",
        )
    else:
        _, download_column = st.columns([3.2, 1.4])
        with download_column:
            st.download_button(
                "Download Excel report",
                data=report_data,
                file_name=agent_report_filename(claim_id),
                mime=EXCEL_MIME_TYPE,
                icon=":material/download:",
                width="stretch",
                on_click="ignore",
                key=f"download_agent_report_{claim_id}",
            )

    document_tab, image_tab = st.tabs(
        ["Document assessment", "Image assessment"]
    )

    with document_tab:
        if aws_document_result is not None:
            render_aws_document_assessment(aws_document_result)
        else:
            render_notice("A document assessment is not available for this claim.")

    with image_tab:
        if aws_image_result is not None:
            render_aws_image_assessment(aws_image_result)
        else:
            render_notice(
                "Vehicle-photo assessment is locked until a claims agent "
                "approves the document review."
            )


def render_claim_detail(claim: AgentClaimDetail) -> None:
    st.divider()
    st.markdown('<div class="section-title">Selected claim</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-copy">Review the submission, validation results, and current review stage.</p>',
        unsafe_allow_html=True,
    )

    aws_assessment = get_cached_aws_claim_assessment(claim.claim_id) or {}
    aws_status = aws_assessment.get("summary")
    aws_document_result = aws_assessment.get("document_result")
    image_assessment_authorized = image_assessment_is_authorized(
        claim,
        aws_status,
    )
    aws_image_result = (
        aws_assessment.get("image_result")
        if image_assessment_authorized
        else None
    )
    stage = resolve_processing_stage(
        claim,
        aws_status=aws_status,
        image_assessment_authorized=image_assessment_authorized,
    )
    aws_claim_status = str(
        (aws_status or {}).get("claim_status", "")
    ).upper()
    effective_claim_status = aws_claim_status or claim.claim_status
    summary_status = (
        display_label(effective_claim_status)
        if effective_claim_status in {
            "APPROVED",
            "REJECTED",
            "NEEDS_INFORMATION",
            "INVESTIGATION",
        }
        else review_stage_label(stage)
    )

    claim_column, policy_column, customer_column, status_column = st.columns(
        4,
        gap="medium",
    )
    with claim_column:
        render_claim_summary_card("Claim ID", claim.claim_id)
    with policy_column:
        render_claim_summary_card("Policy", claim.policy_number)
    with customer_column:
        render_claim_summary_card("Customer", claim.claimant_name or "—")
    with status_column:
        render_claim_summary_card("Status", summary_status)

    details_tab, evidence_tab = st.tabs(["Claim details", "Submitted evidence"])

    with details_tab:
        with st.container(border=True):
            st.markdown("### Incident information")
            left, right = st.columns(2, gap="large")
            with left:
                st.caption("Claim category")
                st.write(claim.claim_category or "—")
                st.caption("Incident date")
                st.write(claim.incident_date)
                st.caption("Incident location")
                st.write(claim.incident_location)
            with right:
                st.caption("Customer ID")
                st.write(claim.customer_id or "—")
                st.caption("Mobile number")
                st.write(claim.phone_number or "—")
                st.caption("Email address")
                st.write(claim.email_address or "—")

            st.caption("Incident chronology")
            st.write(claim.damage_description)

        _, assessment_button_column = st.columns([4.7, 1.3])
        with assessment_button_column:
            if st.button(
                "Assessment results",
                icon=":material/analytics:",
                width="stretch",
                key=f"incident_assessment_{claim.claim_id}",
            ):
                render_ai_result_dialog(claim.claim_id)

    with evidence_tab:
        document_files = [
            claim_file
            for claim_file in claim.files
            if claim_file.evidence_type in DOCUMENT_LABELS
        ]
        vehicle_files = [
            claim_file
            for claim_file in claim.files
            if claim_file.evidence_type == "vehicle_image"
        ]

        st.markdown("### Supporting documents")
        render_file_grid(
            document_files,
            labels=DOCUMENT_LABELS,
            use_image_slot=False,
        )
        st.markdown("### Vehicle photos")
        render_file_grid(
            vehicle_files,
            labels=IMAGE_SLOT_LABELS,
            use_image_slot=True,
        )

    stage_messages = {
        "DOCUMENT_QUEUED": "Initial document review is pending.",
        "DOCUMENT_PROCESSING": "Document review is in progress.",
        "DOCUMENT_REVIEW": "Document results are ready for a decision.",
        "DOCUMENT_FAILED": "Document validation requires attention.",
        "IMAGE_QUEUED": "Vehicle-photo review is pending.",
        "IMAGE_PROCESSING": "Vehicle-photo review is in progress.",
        "FINAL_REVIEW": "Results are ready for the final claim decision.",
        "LEGACY_FINAL_REVIEW": "Results are ready for the final claim decision.",
        "IMAGE_FAILED": "Vehicle-photo review requires attention.",
        "WAITING_FOR_EVIDENCE": "The customer must submit requested replacement evidence.",
        "INVESTIGATION": "The claim is marked for investigation.",
        "COMPLETED": "A final claim decision has been recorded.",
    }
    st.markdown(
        f'<div class="status-strip"><strong>Review stage:</strong> '
        f'{review_stage_label(stage)}. {stage_messages.get(stage, "Review the current claim status.")}</div>',
        unsafe_allow_html=True,
    )
    if stage in {"DOCUMENT_QUEUED", "DOCUMENT_PROCESSING", "IMAGE_QUEUED", "IMAGE_PROCESSING"}:
        render_notice(
            "Review is in progress. Refresh this page to load the latest status."
        )
        if st.button("Refresh status", key=f"refresh_{claim.claim_id}"):
            get_cached_aws_claim_assessment.clear()
            get_cached_aws_claim_statuses.clear()
            refreshed_assessment = (
                get_cached_aws_claim_assessment(claim.claim_id)
                or {}
            )
            st.rerun()

    elif stage == "DOCUMENT_FAILED":
        render_notice(
            "Document processing requires attention in the AWS workflow.",
            "warning",
        )

    elif stage == "IMAGE_FAILED":
        render_notice(
            "Vehicle-photo processing requires attention in the AWS workflow.",
            "warning",
        )

    elif stage == "DOCUMENT_REVIEW" and aws_document_result:
        package_status = str(
            aws_document_result.get("package_status", "unknown")
        ).lower()
        next_action = str(
            aws_document_result.get(
                "next_action",
                "ESCALATE_FOR_REVIEW",
            )
        )

        st.divider()
        st.markdown("## Document review decision")
        if package_status == "valid":
            render_notice(
                "Recommendation: Continue to vehicle-photo assessment",
                "success",
            )
        elif package_status in {"invalid", "incomplete"}:
            render_notice(
                "Recommendation: Request corrected or missing documents",
                "error",
            )
        else:
            render_notice(
                "Recommendation: Verify the document findings",
                "warning",
            )

        st.caption(
            "Approving this stage does not approve the insurance claim. "
            "It only authorizes assessment of the submitted vehicle photo."
        )
        render_notice(
            "A claims-agent decision is required before vehicle-photo "
            "assessment can begin."
        )
        st.caption(f"Current system recommendation: {display_label(next_action)}")

        document_actions = {
            "Continue to vehicle-photo assessment": "APPROVE",
            "Request more information": "REQUEST_MORE_INFORMATION",
            "Reject claim": "REJECT",
        }
        recommended_label = (
            "Continue to vehicle-photo assessment"
            if package_status == "valid"
            else "Request more information"
        )

        with st.container(border=True):
            action_key = f"document_action_{claim.claim_id}"
            evidence_key = f"document_evidence_{claim.claim_id}"
            reason_key = f"document_reason_{claim.claim_id}"
            action_label = st.selectbox(
                "Action",
                options=list(document_actions),
                index=list(document_actions).index(recommended_label),
                key=action_key,
            )
            requires_evidence = (
                document_actions[action_label]
                == "REQUEST_MORE_INFORMATION"
            )
            if (
                not requires_evidence
                and st.session_state.get(evidence_key)
            ):
                st.session_state[evidence_key] = []
            requested_labels = st.multiselect(
                (
                    "Evidence to replace *"
                    if requires_evidence
                    else "Evidence to replace"
                ),
                options=list(EVIDENCE_LABELS),
                format_func=lambda key: EVIDENCE_LABELS[key],
                help=(
                    "Select the items the customer must replace when "
                    "requesting more information."
                ),
                disabled=not requires_evidence,
                key=evidence_key,
            )
            reason = st.text_area(
                "Decision reason (optional)",
                placeholder=(
                    "Add a note for this decision, if needed."
                ),
                height=110,
                key=reason_key,
            )
            save_action = st.button(
                "Save document decision",
                type="primary",
                width="stretch",
                key=f"save_document_decision_{claim.claim_id}",
            )

        if save_action:
            aws_decision = document_actions[action_label]
            try:
                if (
                    aws_decision == "APPROVE"
                    and package_status != "valid"
                ):
                    raise ValueError(
                        "Only a valid document package can continue to "
                        "vehicle-photo assessment."
                    )
                if (
                    aws_decision == "REQUEST_MORE_INFORMATION"
                    and not requested_labels
                ):
                    raise ValueError(
                        "Select at least one item of evidence to replace."
                    )

                submit_agent_document_decision(
                    claim.claim_id,
                    decision=aws_decision,
                    reason=reason,
                    requested_evidence=requested_labels,
                )
            except Exception as error:
                render_notice(
                    f"The document decision could not be saved: {error}",
                    "error",
                )
            else:
                get_cached_aws_claim_assessment.clear()
                get_cached_aws_claim_statuses.clear()
                st.session_state.pop("agent_dialog_claim_id", None)
                st.rerun()

    elif stage == "FINAL_REVIEW" and aws_image_result:
        st.divider()
        st.markdown("## Final claims-agent decision")
        st.caption(
            "Document and vehicle-photo results are complete. Review the findings before recording the final decision."
        )
        with st.container(border=True):
            action_key = f"final_action_{claim.claim_id}"
            evidence_key = f"final_evidence_{claim.claim_id}"
            reason_key = f"final_reason_{claim.claim_id}"
            action_label = st.selectbox(
                "Action",
                options=list(AGENT_ACTIONS),
                key=action_key,
            )
            requires_evidence = (
                AGENT_ACTIONS[action_label]
                == "REQUEST_MORE_INFORMATION"
            )
            if (
                not requires_evidence
                and st.session_state.get(evidence_key)
            ):
                st.session_state[evidence_key] = []
            requested_labels = st.multiselect(
                (
                    "Evidence to replace *"
                    if requires_evidence
                    else "Evidence to replace"
                ),
                options=list(EVIDENCE_LABELS),
                format_func=lambda key: EVIDENCE_LABELS[key],
                help=(
                    "Select the items the customer must replace when "
                    "requesting more information."
                ),
                disabled=not requires_evidence,
                key=evidence_key,
            )
            reason = st.text_area(
                "Decision reason (optional)",
                placeholder=(
                    "Add a note for this decision, if needed."
                ),
                height=110,
                key=reason_key,
            )
            save_action = st.button(
                "Save final decision",
                type="primary",
                width="stretch",
                key=f"save_final_decision_{claim.claim_id}",
            )

        if save_action:
            try:
                submit_agent_final_decision(
                    claim.claim_id,
                    decision=AGENT_ACTIONS[action_label],
                    reason=reason,
                    requested_evidence=requested_labels,
                )
            except Exception as error:
                render_notice(
                    f"The final decision could not be saved: {error}",
                    "error",
                )
            else:
                get_cached_aws_claim_assessment.clear()
                get_cached_aws_claim_statuses.clear()
                render_notice(
                    "The final decision and customer status were saved.",
                    "success",
                )
                st.rerun()

    elif (
        (aws_status or {}).get("agent_final_decision")
        or claim.agent_decision
    ):
        st.divider()
        with st.container(border=True):
            st.markdown("### Saved agent decision")
            saved_decision = (
                (aws_status or {}).get("agent_final_decision")
                or claim.agent_decision
            )
            saved_status = (
                (aws_status or {}).get("claim_status")
                or claim.claim_status
            )
            saved_reason = (
                (aws_status or {}).get("agent_final_decision_reason")
                or claim.agent_reason
            )
            decision_col, status_col = st.columns(2)
            with decision_col:
                render_claim_summary_card(
                    "Action",
                    display_label(saved_decision),
                )
            with status_col:
                render_claim_summary_card(
                    "Claim status",
                    display_label(saved_status),
                )
            st.caption("Reason")
            st.write(saved_reason or "No reason recorded.")


st.markdown(
    """
    <div class="agent-kicker">Claims operations</div>
    <h1 class="agent-title">Claims agent dashboard</h1>
    <p class="agent-subtitle">
        Review submitted evidence, confirm the next review stage, and record
        the final claim decision.
    </p>
    """,
    unsafe_allow_html=True,
)

try:
    claims = list_agent_claims()
except Exception as error:
    render_notice(f"Submitted claims could not be loaded: {error}", "error")
    st.stop()

if not claims:
    render_notice(
        "No submitted claims are available. Submit a customer claim first, then return to this dashboard."
    )
    st.stop()

st.markdown('<div class="section-title">Submitted claims</div>', unsafe_allow_html=True)
st.markdown(
    '<p class="section-copy">Claims are grouped by their current review stage. '
    'Select a row to review its incident information, or use the search icon '
    'to open the assessment results.</p>',
    unsafe_allow_html=True,
)


def claim_queue_name(
    claim: AgentClaimSummary,
    aws_status: dict | None = None,
) -> str:
    stage = resolve_processing_stage(
        claim,
        aws_status=aws_status,
        image_assessment_authorized=image_assessment_is_authorized(
            claim,
            aws_status,
        ),
    )
    if stage in DOCUMENT_REVIEW_STAGES:
        return "document"
    if stage in IMAGE_REVIEW_STAGES:
        return "image"
    if stage in FOLLOW_UP_STAGES:
        return "follow_up"
    return "completed"


def handle_assessment_button_click(
    *,
    click_state_key: str,
    pending_state_key: str,
    claim_ids: tuple[str, ...],
) -> None:
    click = st.session_state.get(click_state_key)
    if not click:
        return

    selected_index = int(click["row"])
    if not 0 <= selected_index < len(claim_ids):
        return

    st.session_state[pending_state_key] = claim_ids[selected_index]


def render_claim_queue(
    queue_claims: list[AgentClaimSummary],
    *,
    queue_key: str,
    empty_message: str,
    aws_statuses: dict[str, dict],
) -> None:
    if not queue_claims:
        render_notice(empty_message)
        return

    dataframe_key = f"{queue_key}_claims_table"
    click_state_key = f"{queue_key}_assessment_button_click"
    pending_state_key = f"{queue_key}_pending_assessment_claim_id"
    claim_ids = tuple(claim.claim_id for claim in queue_claims)

    claim_table_event = st.dataframe(
        [
            {
                "Claim ID": claim.claim_id,
                "Customer": claim.claimant_name,
                "Policy number": claim.policy_number,
                "Incident date": claim.incident_date,
                "Status": display_label(
                    str(
                        aws_statuses.get(
                            claim.claim_id,
                            {},
                        ).get("claim_status")
                        or claim.claim_status
                    )
                ),
                "Review stage": review_stage_label(
                    resolve_processing_stage(
                        claim,
                        aws_status=aws_statuses.get(
                            claim.claim_id
                        ),
                        image_assessment_authorized=(
                            image_assessment_is_authorized(
                                claim,
                                aws_statuses.get(claim.claim_id),
                            )
                        ),
                    )
                ),
                "Submitted": claim.created_at,
                "View assessment": ":material/search:",
            }
            for claim in queue_claims
        ],
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=dataframe_key,
        column_config={
            "View assessment": st.column_config.ButtonColumn(
                "",
                help="View assessment results",
                width=54,
                alignment="center",
                type="tertiary",
                on_click=handle_assessment_button_click,
                kwargs={
                    "click_state_key": click_state_key,
                    "pending_state_key": pending_state_key,
                    "claim_ids": claim_ids,
                },
                key=click_state_key,
            ),
        },
    )

    pending_claim_id = st.session_state.pop(
        pending_state_key,
        None,
    )
    if pending_claim_id:
        render_ai_result_dialog(pending_claim_id)

    selected_rows = list(claim_table_event.selection.rows)
    if not selected_rows:
        render_notice("Select a claim row to review the incident information.")
        return

    selected_index = selected_rows[0]
    if not 0 <= selected_index < len(queue_claims):
        render_notice(
            "The selected claim is no longer available in this queue.",
            "warning",
        )
        return

    selected_claim_id = queue_claims[selected_index].claim_id
    st.session_state["agent_selected_claim_id"] = selected_claim_id

    try:
        selected_claim = get_agent_claim(selected_claim_id)
    except Exception as error:
        render_notice(
            f"The selected claim could not be opened: {error}",
            "error",
        )
        return

    if selected_claim is None:
        render_notice("The selected claim no longer exists.", "warning")
        return

    render_claim_detail(selected_claim)


aws_statuses = get_cached_aws_claim_statuses(
    tuple(claim.claim_id for claim in claims)
)

document_claims = [
    claim
    for claim in claims
    if claim_queue_name(
        claim,
        aws_statuses.get(claim.claim_id),
    )
    == "document"
]
image_claims = [
    claim
    for claim in claims
    if claim_queue_name(
        claim,
        aws_statuses.get(claim.claim_id),
    )
    == "image"
]
follow_up_claims = [
    claim
    for claim in claims
    if claim_queue_name(
        claim,
        aws_statuses.get(claim.claim_id),
    )
    == "follow_up"
]
completed_claims = [
    claim
    for claim in claims
    if claim_queue_name(
        claim,
        aws_statuses.get(claim.claim_id),
    )
    == "completed"
]

document_tab, image_tab, follow_up_tab, completed_tab = st.tabs(
    [
        f"Document review ({len(document_claims)})",
        f"Image review ({len(image_claims)})",
        f"Follow-up ({len(follow_up_claims)})",
        f"Completed ({len(completed_claims)})",
    ]
)

with document_tab:
    st.caption(
        "Claims awaiting document processing, validation, or a document-stage "
        "decision."
    )
    render_claim_queue(
        document_claims,
        queue_key="document_review",
        empty_message="No claims currently require document review.",
        aws_statuses=aws_statuses,
    )

with image_tab:
    st.caption(
        "Claims whose documents were approved and are awaiting image processing "
        "or a final decision."
    )
    render_claim_queue(
        image_claims,
        queue_key="image_review",
        empty_message="No claims currently require image review.",
        aws_statuses=aws_statuses,
    )

with follow_up_tab:
    st.caption(
        "Claims waiting for customer evidence or currently under investigation."
    )
    render_claim_queue(
        follow_up_claims,
        queue_key="follow_up",
        empty_message="No claims currently require follow-up.",
        aws_statuses=aws_statuses,
    )

with completed_tab:
    st.caption(
        "Claims with a recorded final approval or rejection."
    )
    render_claim_queue(
        completed_claims,
        queue_key="completed",
        empty_message="No claims have been completed yet.",
        aws_statuses=aws_statuses,
    )
