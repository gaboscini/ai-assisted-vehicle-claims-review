import sqlite3
from contextlib import closing
from pathlib import Path

from services.policy_models import (
    PolicyRecord,
    VehicleRecord,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "claims_demo.db"
)


def normalize_policy_number(
    policy_number: str,
) -> str:
    return policy_number.strip().upper()


def get_policy_record(
    policy_number: str,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> PolicyRecord | None:
    normalized_policy_number = (
        normalize_policy_number(
            policy_number
        )
    )

    if not normalized_policy_number:
        return None

    if not database_path.exists():
        raise FileNotFoundError(
            "The local insurance database was not "
            f"found: {database_path}. Run "
            "scripts/initialize_database.py first."
        )

    with closing(
        sqlite3.connect(database_path)
    ) as connection:
        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        row = connection.execute(
            """
            SELECT
                p.policy_number,
                p.policy_status,
                p.coverage_type,
                p.coverage_start_date,
                p.coverage_end_date,

                c.customer_id,
                c.full_name AS customer_name,
                c.identity_number,
                c.date_of_birth,
                c.address,
                c.sim_number,
                c.sim_class,
                c.sim_expiration_date,

                v.vehicle_id,
                v.plate_number,
                v.vehicle_year,
                v.make,
                v.model,
                v.chassis_number,
                v.engine_number,
                v.registration_expiration_date

            FROM policies AS p

            INNER JOIN customers AS c
                ON c.customer_id = p.customer_id

            INNER JOIN vehicles AS v
                ON v.vehicle_id = p.vehicle_id

            WHERE UPPER(p.policy_number) = ?

            LIMIT 1
            """,
            (
                normalized_policy_number,
            ),
        ).fetchone()

    if row is None:
        return None

    vehicle = VehicleRecord(
        vehicle_id=row["vehicle_id"],
        plate_number=row["plate_number"],
        year=row["vehicle_year"],
        make=row["make"],
        model=row["model"],
        chassis_number=row[
            "chassis_number"
        ],
        engine_number=row[
            "engine_number"
        ],
        registration_expiration_date=row[
            "registration_expiration_date"
        ],
    )

    return PolicyRecord(
        policy_number=row["policy_number"],
        policy_status=row["policy_status"],
        coverage_type=row["coverage_type"],
        coverage_start_date=row[
            "coverage_start_date"
        ],
        coverage_end_date=row[
            "coverage_end_date"
        ],
        customer_id=row["customer_id"],
        customer_name=row["customer_name"],
        identity_number=row[
            "identity_number"
        ],
        date_of_birth=row["date_of_birth"],
        address=row["address"],
        sim_number=row["sim_number"],
        sim_class=row["sim_class"],
        sim_expiration_date=row[
            "sim_expiration_date"
        ],
        vehicle=vehicle,
    )
