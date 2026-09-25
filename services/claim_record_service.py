from datetime import date
from uuid import uuid4

from services.policy_models import (
    PolicyRecord,
)


def generate_claim_id() -> str:
    identifier = (
        uuid4().hex[:8].upper()
    )

    return f"CLM-DEMO-{identifier}"


def normalize_date(
    value: date | str,
) -> str:
    if isinstance(value, date):
        return value.isoformat()

    return str(value)


def check_policy_eligibility(
    *,
    policy_record: PolicyRecord,
    incident_date: date | str,
) -> dict:
    incident_date_text = normalize_date(
        incident_date
    )

    incident = date.fromisoformat(
        incident_date_text
    )

    coverage_start = date.fromisoformat(
        policy_record.coverage_start_date
    )

    coverage_end = date.fromisoformat(
        policy_record.coverage_end_date
    )

    findings: list[str] = []
    explanations: list[str] = []

    if (
        policy_record.policy_status.upper()
        != "ACTIVE"
    ):
        findings.append(
            "POLICY_NOT_ACTIVE"
        )

        explanations.append(
            "The policy is not active."
        )

    if not (
        coverage_start
        <= incident
        <= coverage_end
    ):
        findings.append(
            "INCIDENT_OUTSIDE_COVERAGE_PERIOD"
        )

        explanations.append(
            "The incident date is outside the "
            "policy coverage period."
        )

    if not findings:
        explanations.append(
            "The policy is active and the incident "
            "date is within the coverage period."
        )

    return {
        "eligible": not findings,
        "findings": findings,
        "explanations": explanations,
    }


def build_claim_record(
    *,
    policy_record: PolicyRecord,
    incident_date: date | str,
    incident_location: str,
    damage_description: str,
    submitted_claimant_name: str,
    claim_id: str | None = None,
) -> dict:
    resolved_claim_id = (
        claim_id
        or generate_claim_id()
    )

    return {
        "test_data_notice": (
            "Synthetic data for local demonstration "
            "testing only"
        ),
        "claim_id": resolved_claim_id,
        "policy_number": (
            policy_record.policy_number
        ),
        "customer_id": (
            policy_record.customer_id
        ),
        "customer_name": (
            policy_record.customer_name
        ),
        "submitted_claimant_name": (
            submitted_claimant_name.strip()
        ),
        "identity_number": (
            policy_record.identity_number
        ),
        "date_of_birth": (
            policy_record.date_of_birth
        ),
        "address": policy_record.address,
        "sim_number": (
            policy_record.sim_number
        ),
        "sim_class": (
            policy_record.sim_class
        ),
        "sim_expiration_date": (
            policy_record.sim_expiration_date
        ),
        "incident_date": normalize_date(
            incident_date
        ),
        "incident_location": (
            incident_location.strip()
        ),
        "damage_description": (
            damage_description.strip()
        ),
        "vehicle": {
            "vehicle_id": (
                policy_record.vehicle.vehicle_id
            ),
            "plate_number": (
                policy_record.vehicle.plate_number
            ),
            "year": (
                policy_record.vehicle.year
            ),
            "make": (
                policy_record.vehicle.make
            ),
            "model": (
                policy_record.vehicle.model
            ),
            "chassis_number": (
                policy_record
                .vehicle
                .chassis_number
            ),
            "engine_number": (
                policy_record
                .vehicle
                .engine_number
            ),
            "registration_expiration_date": (
                policy_record
                .vehicle
                .registration_expiration_date
            ),
            "coverage_type": (
                policy_record.coverage_type
            ),
        },
        "document_references": {},
    }
