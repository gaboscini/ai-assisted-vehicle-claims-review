from copy import deepcopy
from pathlib import Path

from scripts.generate_synthetic_ktp import generate_ktp
from scripts.generate_synthetic_sim import generate_sim
from scripts.generate_synthetic_stnk import generate_stnk


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FOLDER = PROJECT_ROOT / "tests" / "fixtures" / "document_claims"

BASE_RECORD = {
    "customer_name": "Alex Rivera",
    "identity_number": "KTP-TEST-000001",
    "date_of_birth": "1990-04-15",
    "address": "100 Example Avenue, Example City",
    "sim_number": "SIM-TEST-000001",
    "sim_class": "A",
    "sim_expiration_date": "2028-04-15",
    "vehicle": {
        "plate_number": "EXAMPLE-1234",
        "year": 2022,
        "make": "Toyota",
        "model": "Avanza",
        "chassis_number": "CHASSIS-DEMO-000001",
        "engine_number": "ENGINE-DEMO-000001",
        "registration_expiration_date": "2027-12-31",
    },
}


def scenario_records() -> dict[str, dict[str, dict | None]]:
    valid = deepcopy(BASE_RECORD)

    name_mismatch_ktp = deepcopy(BASE_RECORD)
    name_mismatch_ktp["customer_name"] = "Morgan Lee"
    name_mismatch_ktp["identity_number"] = "KTP-TEST-000002"

    expired_sim = deepcopy(BASE_RECORD)
    expired_sim["sim_expiration_date"] = "2025-04-15"

    plate_mismatch_stnk = deepcopy(BASE_RECORD)
    plate_mismatch_stnk["vehicle"]["plate_number"] = "EXAMPLE-9999"

    return {
        "claim_001_valid": {
            "ktp": valid,
            "sim": valid,
            "stnk": valid,
        },
        "claim_002_name_mismatch": {
            "ktp": name_mismatch_ktp,
            "sim": valid,
            "stnk": valid,
        },
        "claim_003_expired_sim": {
            "ktp": valid,
            "sim": expired_sim,
            "stnk": valid,
        },
        "claim_004_plate_mismatch": {
            "ktp": valid,
            "sim": valid,
            "stnk": plate_mismatch_stnk,
        },
        "claim_005_missing_sim": {
            "ktp": valid,
            "sim": None,
            "stnk": valid,
        },
    }


def generate_images() -> list[Path]:
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    generated_paths: list[Path] = []
    generators = {
        "ktp": generate_ktp,
        "sim": generate_sim,
        "stnk": generate_stnk,
    }

    for scenario_name, documents in scenario_records().items():
        for document_type, record in documents.items():
            output_path = (
                OUTPUT_FOLDER
                / scenario_name
                / "documents"
                / f"{document_type}.png"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if record is None:
                output_path.unlink(missing_ok=True)
                continue

            generators[document_type](record, output_path=output_path)
            generated_paths.append(output_path)

    return generated_paths


def main() -> None:
    generated_paths = generate_images()
    print(f"Generated {len(generated_paths)} document test images.")
    for path in generated_paths:
        print(path)


if __name__ == "__main__":
    main()
