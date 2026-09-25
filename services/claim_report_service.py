from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
import json
import re
from typing import Any, Iterable

import xlsxwriter


EXCEL_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

DOCUMENT_LABELS = {
    "ktp": "KTP identity document",
    "sim": "SIM driver licence",
    "stnk": "STNK vehicle registration",
}

COLORS = {
    "navy": "#102A43",
    "blue": "#0F6CBD",
    "blue_light": "#EAF3FB",
    "green": "#16794A",
    "green_light": "#E8F5EE",
    "amber": "#A15C00",
    "amber_light": "#FFF4E5",
    "red": "#B42318",
    "red_light": "#FDECEC",
    "gray": "#627D98",
    "gray_light": "#F4F7FB",
    "border": "#D9E2EC",
    "white": "#FFFFFF",
}


def _object_dict(value: object | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if is_dataclass(value):
        return asdict(value)
    return {
        key: item
        for key, item in vars(value).items()
        if not key.startswith("_")
    }


def _first_value(*values: object, default: object = "") -> object:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def _display(value: object) -> str:
    if value is None or value == "":
        return "Not available"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_display(item) for item in value) or "None"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, default=str)

    text = str(value).strip()
    if not text:
        return "Not available"
    if re.fullmatch(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+", text):
        return text.replace("_", " ").title()
    return text


def _score_fraction(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1:
        number /= 100
    return max(0.0, min(number, 1.0))


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    elif value:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.strptime(text, "%Y-%m-%d")
            except ValueError:
                return None
    else:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _safe_filename_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned.strip("_") or "claim"


def agent_report_filename(claim_id: str) -> str:
    return f"{_safe_filename_component(claim_id)}_assessment_report.xlsx"


def customer_report_filename(claim_id: str) -> str:
    return f"{_safe_filename_component(claim_id)}_claim_report.xlsx"


def _make_formats(workbook: xlsxwriter.Workbook) -> dict[str, Any]:
    base = {
        "font_name": "Aptos",
        "font_size": 10,
        "font_color": COLORS["navy"],
        "valign": "vcenter",
    }
    return {
        "title": workbook.add_format(
            {
                **base,
                "font_size": 20,
                "bold": True,
                "font_color": COLORS["white"],
                "bg_color": COLORS["blue"],
                "align": "left",
            }
        ),
        "subtitle": workbook.add_format(
            {
                **base,
                "font_size": 10,
                "font_color": COLORS["gray"],
                "italic": True,
            }
        ),
        "section": workbook.add_format(
            {
                **base,
                "font_size": 12,
                "bold": True,
                "font_color": COLORS["white"],
                "bg_color": COLORS["navy"],
                "align": "left",
            }
        ),
        "label": workbook.add_format(
            {
                **base,
                "bold": True,
                "font_color": COLORS["gray"],
                "bg_color": COLORS["gray_light"],
                "border": 1,
                "border_color": COLORS["border"],
                "text_wrap": True,
            }
        ),
        "value": workbook.add_format(
            {
                **base,
                "bg_color": COLORS["white"],
                "border": 1,
                "border_color": COLORS["border"],
                "text_wrap": True,
            }
        ),
        "value_bold": workbook.add_format(
            {
                **base,
                "bold": True,
                "bg_color": COLORS["white"],
                "border": 1,
                "border_color": COLORS["border"],
                "text_wrap": True,
            }
        ),
        "date": workbook.add_format(
            {
                **base,
                "num_format": "yyyy-mm-dd",
                "bg_color": COLORS["white"],
                "border": 1,
                "border_color": COLORS["border"],
            }
        ),
        "datetime": workbook.add_format(
            {
                **base,
                "num_format": "yyyy-mm-dd hh:mm",
                "bg_color": COLORS["white"],
                "border": 1,
                "border_color": COLORS["border"],
            }
        ),
        "percent": workbook.add_format(
            {
                **base,
                "num_format": "0.00%",
                "align": "right",
            }
        ),
        "table_text": workbook.add_format(
            {
                **base,
                "text_wrap": True,
                "bottom": 1,
                "bottom_color": COLORS["border"],
            }
        ),
        "pass": workbook.add_format(
            {
                **base,
                "bold": True,
                "font_color": COLORS["green"],
                "bg_color": COLORS["green_light"],
            }
        ),
        "review": workbook.add_format(
            {
                **base,
                "bold": True,
                "font_color": COLORS["amber"],
                "bg_color": COLORS["amber_light"],
            }
        ),
        "fail": workbook.add_format(
            {
                **base,
                "bold": True,
                "font_color": COLORS["red"],
                "bg_color": COLORS["red_light"],
            }
        ),
        "note": workbook.add_format(
            {
                **base,
                "font_color": COLORS["gray"],
                "bg_color": COLORS["blue_light"],
                "text_wrap": True,
                "border": 1,
                "border_color": COLORS["border"],
            }
        ),
    }


def _status_format(formats: dict[str, Any], status: object):
    normalized = str(status or "").upper()
    if normalized in {"PASS", "VALID", "ELIGIBLE", "APPROVED", "COMPLETED"}:
        return formats["pass"]
    if normalized in {
        "REVIEW",
        "NEEDS_REVIEW",
        "NEEDS_INFORMATION",
        "INVESTIGATION",
        "ESCALATE_FOR_REVIEW",
        "ESCALATE_FOR_INVESTIGATION",
        "PENDING",
    }:
        return formats["review"]
    if normalized in {"FAIL", "INVALID", "INELIGIBLE", "REJECTED"}:
        return formats["fail"]
    return formats["value"]


def _prepare_sheet(
    workbook: xlsxwriter.Workbook,
    sheet_name: str,
    title: str,
    subtitle: str,
    *,
    last_column: int,
) -> tuple[xlsxwriter.worksheet.Worksheet, dict[str, Any], int]:
    worksheet = workbook.add_worksheet(sheet_name)
    formats = _make_formats(workbook)
    worksheet.hide_gridlines(2)
    worksheet.set_zoom(90)
    worksheet.set_landscape()
    worksheet.fit_to_pages(1, 0)
    worksheet.set_margins(0.35, 0.35, 0.5, 0.5)
    worksheet.merge_range(0, 0, 1, last_column, title, formats["title"])
    worksheet.merge_range(2, 0, 2, last_column, subtitle, formats["subtitle"])
    worksheet.set_row(0, 25)
    worksheet.set_row(1, 10)
    worksheet.set_row(2, 22)
    return worksheet, formats, 4


def _write_section(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    title: str,
    *,
    last_column: int,
) -> int:
    worksheet.merge_range(row, 0, row, last_column, title, formats["section"])
    worksheet.set_row(row, 22)
    return row + 1


def _write_value(
    worksheet: xlsxwriter.worksheet.Worksheet,
    row: int,
    column: int,
    value: object,
    formats: dict[str, Any],
    *,
    bold: bool = False,
) -> None:
    parsed = _parse_datetime(value)
    if parsed is not None and isinstance(value, (date, datetime)):
        worksheet.write_datetime(row, column, parsed, formats["datetime"])
        return
    if parsed is not None and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:T.*)?",
        str(value),
    ):
        selected_format = (
            formats["date"]
            if len(str(value)) == 10
            else formats["datetime"]
        )
        worksheet.write_datetime(row, column, parsed, selected_format)
        return
    worksheet.write(
        row,
        column,
        _display(value),
        formats["value_bold"] if bold else formats["value"],
    )


def _write_pairs(
    worksheet: xlsxwriter.worksheet.Worksheet,
    formats: dict[str, Any],
    row: int,
    pairs: Iterable[tuple[str, object]],
) -> int:
    entries = list(pairs)
    for index in range(0, len(entries), 2):
        left_label, left_value = entries[index]
        worksheet.write(row, 0, left_label, formats["label"])
        _write_value(worksheet, row, 1, left_value, formats, bold=True)
        if index + 1 < len(entries):
            right_label, right_value = entries[index + 1]
            worksheet.write(row, 2, right_label, formats["label"])
            _write_value(worksheet, row, 3, right_value, formats, bold=True)
        else:
            worksheet.write_blank(row, 2, None, formats["label"])
            worksheet.write_blank(row, 3, None, formats["value"])
        worksheet.set_row(row, 28)
        row += 1
    return row


def _write_status_value(
    worksheet: xlsxwriter.worksheet.Worksheet,
    row: int,
    column: int,
    value: object,
    formats: dict[str, Any],
) -> None:
    worksheet.write(
        row,
        column,
        _display(value),
        _status_format(formats, value),
    )


def _new_workbook(output: BytesIO, title: str) -> xlsxwriter.Workbook:
    workbook = xlsxwriter.Workbook(
        output,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        },
    )
    workbook.set_properties(
        {
            "title": title,
            "subject": "Vehicle insurance claim report",
            "author": "Vehicle Insurance Claims Service",
            "company": "Insurance Claims Service",
            "comments": "Generated from the claims review application.",
        }
    )
    return workbook


def build_agent_claim_assessment_report(
    *,
    claim_id: str,
    claim_record: dict | None,
    claim_status: dict | None,
    document_result: dict | None,
    image_result: dict | None,
    local_claim: object | None = None,
) -> bytes:
    record = claim_record or {}
    status = claim_status or {}
    local = _object_dict(local_claim)
    vehicle = record.get("vehicle") or {}
    output = BytesIO()
    workbook = _new_workbook(output, f"Claim assessment - {claim_id}")

    worksheet, formats, row = _prepare_sheet(
        workbook,
        "Claim Summary",
        "Vehicle Insurance Claim Assessment",
        f"Claim {claim_id} | Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        last_column=3,
    )
    worksheet.set_column("A:A", 25)
    worksheet.set_column("B:B", 34)
    worksheet.set_column("C:C", 25)
    worksheet.set_column("D:D", 42)

    row = _write_section(
        worksheet,
        formats,
        row,
        "Claim overview",
        last_column=3,
    )
    summary_pairs = [
        ("Claim ID", claim_id),
        ("Policy number", _first_value(status.get("policy_number"), record.get("policy_number"), local.get("policy_number"))),
        ("Customer", _first_value(record.get("submitted_claimant_name"), record.get("customer_name"), local.get("claimant_name"))),
        ("Customer ID", _first_value(record.get("customer_id"), local.get("customer_id"))),
        ("Claim status", _first_value(status.get("claim_status"), local.get("claim_status"), "In review")),
        ("Processing stage", _first_value(status.get("processing_stage"), local.get("processing_stage"))),
        ("Next action", status.get("next_action")),
        ("Updated at", _first_value(status.get("updated_at"), local.get("created_at"))),
    ]
    row = _write_pairs(worksheet, formats, row, summary_pairs)
    row += 1

    row = _write_section(
        worksheet,
        formats,
        row,
        "Incident and vehicle",
        last_column=3,
    )
    incident_pairs = [
        ("Incident date", _first_value(record.get("incident_date"), local.get("incident_date"))),
        ("Incident location", _first_value(record.get("incident_location"), local.get("incident_location"))),
        ("Claim category", local.get("claim_category")),
        ("Damage description", _first_value(record.get("damage_description"), local.get("damage_description"))),
        ("Vehicle", " ".join(str(item) for item in (vehicle.get("year"), vehicle.get("make"), vehicle.get("model")) if item)),
        ("Plate number", vehicle.get("plate_number")),
        ("Coverage type", vehicle.get("coverage_type")),
        ("Chassis number", vehicle.get("chassis_number")),
    ]
    row = _write_pairs(worksheet, formats, row, incident_pairs)
    row += 1

    row = _write_section(
        worksheet,
        formats,
        row,
        "Assessment outcome",
        last_column=3,
    )
    image_damage = (image_result or {}).get("damage_assessment") or {}
    outcome_pairs = [
        ("Document package", (document_result or {}).get("package_status")),
        ("Document next action", (document_result or {}).get("next_action")),
        ("Image evidence", (image_result or {}).get("evidence_status")),
        ("Evidence suitability", f"{(image_result or {}).get('evidence_suitability_score')}%" if (image_result or {}).get("evidence_suitability_score") is not None else None),
        ("Visible severity", image_damage.get("severity")),
        ("Image recommendation", (image_result or {}).get("final_recommendation")),
        ("Repair recommendation", image_damage.get("repair_recommendation")),
        ("Final agent decision", _first_value(status.get("agent_final_decision"), status.get("agent_document_decision"), local.get("agent_decision"))),
    ]
    row = _write_pairs(worksheet, formats, row, outcome_pairs)
    row += 1

    row = _write_section(
        worksheet,
        formats,
        row,
        "Decision and communication",
        last_column=3,
    )
    row = _write_pairs(
        worksheet,
        formats,
        row,
        [
            ("Decision reason", _first_value(status.get("agent_final_decision_reason"), status.get("agent_document_decision_reason"), local.get("agent_reason"))),
            ("Decision by", _first_value(status.get("agent_final_decision_by"), status.get("agent_document_decision_by"))),
            ("Customer message", _first_value(status.get("customer_message"), local.get("customer_message"))),
            ("Requested evidence", _first_value(status.get("requested_evidence"), local.get("requested_evidence"))),
        ],
    )
    worksheet.freeze_panes(4, 0)

    _write_agent_document_sheet(workbook, claim_id, document_result)
    _write_agent_image_sheet(workbook, claim_id, image_result)

    workbook.close()
    return output.getvalue()


def _write_agent_document_sheet(
    workbook: xlsxwriter.Workbook,
    claim_id: str,
    document_result: dict | None,
) -> None:
    result = document_result or {}
    worksheet, formats, row = _prepare_sheet(
        workbook,
        "Document Assessment",
        "Document Assessment",
        f"Claim {claim_id} | KTP, SIM, and STNK validation results",
        last_column=11,
    )
    worksheet.set_column("A:A", 24)
    worksheet.set_column("B:B", 15)
    worksheet.set_column("C:C", 23)
    worksheet.set_column("D:E", 24)
    worksheet.set_column("F:H", 17)
    worksheet.set_column("I:I", 15)
    worksheet.set_column("J:J", 22)
    worksheet.set_column("K:L", 28)

    row = _write_section(
        worksheet,
        formats,
        row,
        "Package summary",
        last_column=11,
    )
    worksheet.write(row, 0, "Package status", formats["label"])
    _write_status_value(worksheet, row, 1, result.get("package_status"), formats)
    worksheet.write(row, 2, "Next action", formats["label"])
    _write_status_value(worksheet, row, 3, result.get("next_action"), formats)
    worksheet.write(row, 4, "Threshold profile", formats["label"])
    worksheet.merge_range(row, 5, row, 7, _display(result.get("threshold_profile")), formats["value"])
    worksheet.write(row, 8, "Documents checked", formats["label"])
    worksheet.merge_range(row, 9, row, 11, f"{len(result.get('document_results') or {})} of 3", formats["value_bold"])
    row += 2

    headers = [
        "Document",
        "Document status",
        "Field",
        "Extracted result",
        "Expected value",
        "Extraction confidence",
        "Required threshold",
        "Match score",
        "Field status",
        "Document-type confidence",
        "Type threshold",
        "Findings",
    ]
    table_rows: list[list[object]] = []
    row_statuses: list[str] = []
    document_results = result.get("document_results") or {}

    for document_type in ("ktp", "sim", "stnk"):
        document = document_results.get(document_type) or {}
        fields = document.get("field_results") or []
        if not fields:
            fields = [{}]
        document_findings = document.get("findings") or []
        for field in fields:
            field_findings = field.get("findings") or []
            findings = list(dict.fromkeys([*document_findings, *field_findings]))
            field_status = str(field.get("status") or document.get("document_status") or "NOT_AVAILABLE")
            row_statuses.append(field_status)
            table_rows.append(
                [
                    DOCUMENT_LABELS.get(document_type, document_type.upper()),
                    _display(document.get("document_status")),
                    _display(field.get("display_name") or field.get("field_name")),
                    _display(field.get("extracted_value")),
                    _display(field.get("expected_value")),
                    _score_fraction(field.get("extraction_confidence_score", field.get("ocr_confidence_score"))),
                    _score_fraction(field.get("confidence_threshold")),
                    _score_fraction(field.get("match_score")),
                    _display(field_status),
                    _score_fraction(document.get("document_type_confidence_score")),
                    _score_fraction(document.get("document_type_confidence_threshold")),
                    _display(findings) if findings else "None",
                ]
            )

    table_start = row
    worksheet.add_table(
        table_start,
        0,
        table_start + len(table_rows),
        len(headers) - 1,
        {
            "name": "DocumentAssessmentTable",
            "style": "Table Style Medium 2",
            "columns": [{"header": header} for header in headers],
            "data": table_rows,
        },
    )
    for data_index, status in enumerate(row_statuses, start=table_start + 1):
        for column in (5, 6, 7, 9, 10):
            value = table_rows[data_index - table_start - 1][column]
            if value is not None:
                worksheet.write_number(data_index, column, value, formats["percent"])
            else:
                worksheet.write_blank(data_index, column, None, formats["table_text"])
        worksheet.write(data_index, 8, _display(status), _status_format(formats, status))
        worksheet.set_row(data_index, 32)
    worksheet.freeze_panes(table_start + 1, 2)


def _write_agent_image_sheet(
    workbook: xlsxwriter.Workbook,
    claim_id: str,
    image_result: dict | None,
) -> None:
    result = image_result or {}
    damage = result.get("damage_assessment") or {}
    synthetic = result.get("synthetic_assessment") or {}
    worksheet, formats, row = _prepare_sheet(
        workbook,
        "Image Assessment",
        "Vehicle Image Assessment",
        f"Claim {claim_id} | Evidence suitability and visible-damage findings",
        last_column=5,
    )
    worksheet.set_column("A:A", 28)
    worksheet.set_column("B:B", 25)
    worksheet.set_column("C:D", 18)
    worksheet.set_column("E:E", 17)
    worksheet.set_column("F:F", 48)

    row = _write_section(
        worksheet,
        formats,
        row,
        "Assessment summary",
        last_column=5,
    )
    summary_pairs = [
        ("Evidence status", result.get("evidence_status")),
        ("Evidence suitability", f"{result.get('evidence_suitability_score')}%" if result.get("evidence_suitability_score") is not None else None),
        ("Final recommendation", result.get("final_recommendation")),
        ("Visible severity", damage.get("severity")),
        ("Repair recommendation", damage.get("repair_recommendation")),
        ("Repair confidence", f"{damage.get('repair_recommendation_confidence')}%" if damage.get("repair_recommendation_confidence") is not None else None),
    ]
    for index in range(0, len(summary_pairs), 2):
        left_label, left_value = summary_pairs[index]
        right_label, right_value = summary_pairs[index + 1]
        worksheet.write(row, 0, left_label, formats["label"])
        _write_status_value(worksheet, row, 1, left_value, formats)
        worksheet.write(row, 3, right_label, formats["label"])
        _write_status_value(worksheet, row, 4, right_value, formats)
        worksheet.write_blank(row, 2, None, formats["value"])
        worksheet.write_blank(row, 5, None, formats["value"])
        row += 1
    row += 1

    row = _write_section(
        worksheet,
        formats,
        row,
        "Evidence checks",
        last_column=5,
    )
    headers = ["Check", "Result", "Confidence", "Threshold", "Status", "Expected"]
    checks = result.get("evidence_checks") or []
    table_rows = [
        [
            _display(check.get("display_name") or check.get("field")),
            _display(check.get("result")),
            _score_fraction(check.get("confidence_score")),
            _score_fraction(check.get("confidence_threshold")),
            _display(check.get("status")),
            _display(check.get("expected")),
        ]
        for check in checks
    ]
    if table_rows:
        table_start = row
        worksheet.add_table(
            table_start,
            0,
            table_start + len(table_rows),
            len(headers) - 1,
            {
                "name": "ImageEvidenceChecksTable",
                "style": "Table Style Medium 2",
                "columns": [{"header": header} for header in headers],
                "data": table_rows,
            },
        )
        for data_index, check in enumerate(checks, start=table_start + 1):
            for column in (2, 3):
                value = table_rows[data_index - table_start - 1][column]
                if value is not None:
                    worksheet.write_number(data_index, column, value, formats["percent"])
                else:
                    worksheet.write_blank(data_index, column, None, formats["table_text"])
            worksheet.write(
                data_index,
                4,
                _display(check.get("status")),
                _status_format(formats, check.get("status")),
            )
        row = table_start + len(table_rows) + 2
    else:
        worksheet.merge_range(row, 0, row, 5, "Image assessment is not available yet.", formats["note"])
        row += 2

    row = _write_section(
        worksheet,
        formats,
        row,
        "Visible damage",
        last_column=5,
    )
    damage_pairs = [
        ("Damage visible", damage.get("damage_visible")),
        ("Location", damage.get("damage_location")),
        ("Classification", damage.get("damage_classification")),
        ("Damaged parts", damage.get("damaged_parts")),
        ("Severity", damage.get("severity")),
        ("Severity confidence", f"{damage.get('severity_confidence')}%" if damage.get("severity_confidence") is not None else None),
        ("Repair recommendation", damage.get("repair_recommendation")),
        ("Recommendation confidence", f"{damage.get('repair_recommendation_confidence')}%" if damage.get("repair_recommendation_confidence") is not None else None),
    ]
    for index in range(0, len(damage_pairs), 2):
        left_label, left_value = damage_pairs[index]
        right_label, right_value = damage_pairs[index + 1]
        worksheet.write(row, 0, left_label, formats["label"])
        worksheet.merge_range(row, 1, row, 2, _display(left_value), formats["value"])
        worksheet.write(row, 3, right_label, formats["label"])
        worksheet.merge_range(row, 4, row, 5, _display(right_value), formats["value"])
        row += 1

    if synthetic:
        row += 1
        row = _write_section(
            worksheet,
            formats,
            row,
            "Synthetic-image screening",
            last_column=5,
        )
        worksheet.write(row, 0, "Risk level", formats["label"])
        _write_status_value(worksheet, row, 1, synthetic.get("risk_level"), formats)
        worksheet.write(row, 2, "Risk score", formats["label"])
        _write_value(worksheet, row, 3, synthetic.get("risk_score"), formats)
        worksheet.write(row, 4, "Assessment confidence", formats["label"])
        _write_value(worksheet, row, 5, f"{synthetic.get('assessment_confidence')}%" if synthetic.get("assessment_confidence") is not None else None, formats)
        row += 1

    summary = damage.get("analyst_summary")
    if summary:
        row += 1
        row = _write_section(
            worksheet,
            formats,
            row,
            "Assessment summary",
            last_column=5,
        )
        worksheet.merge_range(row, 0, row + 2, 5, _display(summary), formats["note"])
        worksheet.set_row(row, 24)
        worksheet.set_row(row + 1, 24)
        worksheet.set_row(row + 2, 24)
        row += 4

    limitations = damage.get("limitations") or []
    if limitations:
        row = _write_section(
            worksheet,
            formats,
            row,
            "Limitations",
            last_column=5,
        )
        for limitation in limitations:
            worksheet.merge_range(row, 0, row, 5, f"- {_display(limitation)}", formats["value"])
            row += 1
    worksheet.freeze_panes(4, 0)


def build_customer_claim_report(
    *,
    claim_id: str,
    claim_record: dict | None,
    claim_status: dict | None,
    display_status: str,
    status_message: str,
    local_claim: object | None = None,
) -> bytes:
    record = claim_record or {}
    status = claim_status or {}
    local = _object_dict(local_claim)
    vehicle = record.get("vehicle") or {}
    output = BytesIO()
    workbook = _new_workbook(output, f"Claim report - {claim_id}")
    worksheet, formats, row = _prepare_sheet(
        workbook,
        "Claim Report",
        "Vehicle Insurance Claim Report",
        f"Claim {claim_id} | Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        last_column=3,
    )
    worksheet.set_column("A:A", 25)
    worksheet.set_column("B:B", 38)
    worksheet.set_column("C:C", 25)
    worksheet.set_column("D:D", 44)

    row = _write_section(
        worksheet,
        formats,
        row,
        "Current claim status",
        last_column=3,
    )
    worksheet.write(row, 0, "Status", formats["label"])
    worksheet.write(row, 1, _display(display_status), _status_format(formats, display_status))
    worksheet.write(row, 2, "Last updated", formats["label"])
    _write_value(
        worksheet,
        row,
        3,
        _first_value(status.get("updated_at"), local.get("updated_at"), local.get("created_at")),
        formats,
    )
    row += 1
    worksheet.write(row, 0, "Latest update", formats["label"])
    worksheet.merge_range(row, 1, row + 1, 3, _display(status_message), formats["note"])
    worksheet.set_row(row, 28)
    worksheet.set_row(row + 1, 28)
    row += 3

    row = _write_section(
        worksheet,
        formats,
        row,
        "Claim details",
        last_column=3,
    )
    row = _write_pairs(
        worksheet,
        formats,
        row,
        [
            ("Claim ID", claim_id),
            ("Policy number", _first_value(status.get("policy_number"), record.get("policy_number"), local.get("policy_number"))),
            ("Policyholder", _first_value(record.get("submitted_claimant_name"), record.get("customer_name"), local.get("claimant_name"))),
            ("Incident date", _first_value(record.get("incident_date"), local.get("incident_date"))),
            ("Incident location", _first_value(record.get("incident_location"), local.get("incident_location"))),
            ("Claim category", local.get("claim_category")),
            ("Damage description", _first_value(record.get("damage_description"), local.get("damage_description"))),
            ("Requested evidence", status.get("requested_evidence")),
        ],
    )
    row += 1

    row = _write_section(
        worksheet,
        formats,
        row,
        "Insured vehicle",
        last_column=3,
    )
    _write_pairs(
        worksheet,
        formats,
        row,
        [
            ("Vehicle", " ".join(str(item) for item in (vehicle.get("year"), vehicle.get("make"), vehicle.get("model")) if item)),
            ("Plate number", vehicle.get("plate_number")),
            ("Coverage type", vehicle.get("coverage_type")),
            ("Registration expiry", vehicle.get("registration_expiration_date")),
        ],
    )

    worksheet.freeze_panes(4, 0)
    workbook.close()
    return output.getvalue()
