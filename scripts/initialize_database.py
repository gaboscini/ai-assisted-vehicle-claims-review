import sqlite3
from contextlib import closing
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "claims_demo.db"
)


CLAIM_COLUMNS = {
    "customer_id": "TEXT",
    "claimant_name": "TEXT",
    "phone_number": "TEXT",
    "email_address": "TEXT",
    "claim_category": "TEXT",
    "agent_decision": "TEXT",
    "agent_reason": "TEXT",
    "customer_message": "TEXT",
    "requested_evidence": "TEXT",
    "processing_stage": "TEXT",
    "updated_at": "TEXT",
}


def add_missing_claim_columns(
    connection: sqlite3.Connection,
) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(claims)"
        ).fetchall()
    }

    for column_name, column_type in CLAIM_COLUMNS.items():
        if column_name not in existing_columns:
            connection.execute(
                f"ALTER TABLE claims "
                f"ADD COLUMN {column_name} {column_type}"
            )


def create_tables(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            identity_number TEXT NOT NULL UNIQUE,
            date_of_birth TEXT NOT NULL,
            address TEXT NOT NULL,
            sim_number TEXT NOT NULL UNIQUE,
            sim_class TEXT NOT NULL,
            sim_expiration_date TEXT NOT NULL,
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicles (
            vehicle_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            plate_number TEXT NOT NULL UNIQUE,
            vehicle_year INTEGER NOT NULL,
            make TEXT NOT NULL,
            model TEXT NOT NULL,
            chassis_number TEXT NOT NULL UNIQUE,
            engine_number TEXT NOT NULL UNIQUE,
            registration_expiration_date TEXT NOT NULL,
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS policies (
            policy_number TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            vehicle_id TEXT NOT NULL,
            coverage_type TEXT NOT NULL,
            policy_status TEXT NOT NULL,
            coverage_start_date TEXT NOT NULL,
            coverage_end_date TEXT NOT NULL,
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id),

            FOREIGN KEY (vehicle_id)
                REFERENCES vehicles(vehicle_id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            policy_number TEXT NOT NULL,
            customer_id TEXT,
            claimant_name TEXT,
            phone_number TEXT,
            email_address TEXT,
            claim_category TEXT,
            incident_date TEXT NOT NULL,
            incident_location TEXT NOT NULL,
            damage_description TEXT NOT NULL,
            claim_status TEXT NOT NULL,
            agent_decision TEXT,
            agent_reason TEXT,
            customer_message TEXT,
            requested_evidence TEXT,
            processing_stage TEXT NOT NULL
                DEFAULT 'DOCUMENT_QUEUED',
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (policy_number)
                REFERENCES policies(policy_number),

            FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id)
        )
        """
    )

    add_missing_claim_columns(
        connection=connection,
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS claim_files (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            image_slot TEXT,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            file_extension TEXT NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,

            FOREIGN KEY (claim_id)
                REFERENCES claims(claim_id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS assessments (
            assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT NOT NULL,
            assessment_type TEXT NOT NULL,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (claim_id)
                REFERENCES claims(claim_id)
        )
        """
    )

    connection.execute(
        """
        UPDATE claims
        SET processing_stage = 'COMPLETED'
        WHERE claim_status IN ('APPROVED', 'REJECTED')
        """
    )

    connection.execute(
        """
        UPDATE claims
        SET processing_stage = 'LEGACY_FINAL_REVIEW'
        WHERE claim_status = 'READY_FOR_REVIEW'
          AND EXISTS (
              SELECT 1 FROM assessments
              WHERE assessments.claim_id = claims.claim_id
                AND assessments.assessment_type = 'claim_pre_assessment'
          )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_claim_files_claim_id
        ON claim_files(claim_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_assessments_claim_id
        ON assessments(claim_id)
        """
    )


def seed_customer(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        INSERT INTO customers (
            customer_id,
            full_name,
            identity_number,
            date_of_birth,
            address,
            sim_number,
            sim_class,
            sim_expiration_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(customer_id) DO UPDATE SET
            full_name = excluded.full_name,
            identity_number = excluded.identity_number,
            date_of_birth = excluded.date_of_birth,
            address = excluded.address,
            sim_number = excluded.sim_number,
            sim_class = excluded.sim_class,
            sim_expiration_date =
                excluded.sim_expiration_date
        """,
        (
            "CUS-DEMO-000001",
            "Alex Rivera",
            "KTP-TEST-000001",
            "1990-04-15",
            "100 Example Avenue, Example City",
            "SIM-TEST-000001",
            "A",
            "2028-04-15",
        ),
    )


def seed_vehicle(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        INSERT INTO vehicles (
            vehicle_id,
            customer_id,
            plate_number,
            vehicle_year,
            make,
            model,
            chassis_number,
            engine_number,
            registration_expiration_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(vehicle_id) DO UPDATE SET
            customer_id = excluded.customer_id,
            plate_number = excluded.plate_number,
            vehicle_year = excluded.vehicle_year,
            make = excluded.make,
            model = excluded.model,
            chassis_number = excluded.chassis_number,
            engine_number = excluded.engine_number,
            registration_expiration_date =
                excluded.registration_expiration_date
        """,
        (
            "VEH-DEMO-000001",
            "CUS-DEMO-000001",
            "EXAMPLE-1234",
            2022,
            "Toyota",
            "Avanza",
            "CHASSIS-DEMO-000001",
            "ENGINE-DEMO-000001",
            "2027-12-31",
        ),
    )


def seed_policy(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        INSERT INTO policies (
            policy_number,
            customer_id,
            vehicle_id,
            coverage_type,
            policy_status,
            coverage_start_date,
            coverage_end_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(policy_number) DO UPDATE SET
            customer_id = excluded.customer_id,
            vehicle_id = excluded.vehicle_id,
            coverage_type = excluded.coverage_type,
            policy_status = excluded.policy_status,
            coverage_start_date =
                excluded.coverage_start_date,
            coverage_end_date =
                excluded.coverage_end_date
        """,
        (
            "POL-DEMO-000001",
            "CUS-DEMO-000001",
            "VEH-DEMO-000001",
            "Comprehensive",
            "ACTIVE",
            "2026-01-01",
            "2026-12-31",
        ),
    )


def print_database_summary(
    connection: sqlite3.Connection,
) -> None:
    table_names = [
        "customers",
        "vehicles",
        "policies",
        "claims",
        "claim_files",
        "assessments",
    ]

    print("\n--- DATABASE SUMMARY ---\n")

    for table_name in table_names:
        row = connection.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()

        record_count = (
            row[0]
            if row
            else 0
        )

        print(
            f"{table_name}: "
            f"{record_count} record(s)"
        )


def initialize_database(
    database_path: Path = DATABASE_PATH,
    *,
    seed_reference_data: bool = True,
    verbose: bool = True,
) -> None:
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with closing(
        sqlite3.connect(database_path)
    ) as connection:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        create_tables(
            connection=connection,
        )

        if seed_reference_data:
            seed_customer(
                connection=connection,
            )

            seed_vehicle(
                connection=connection,
            )

            seed_policy(
                connection=connection,
            )

        connection.commit()

        if verbose:
            print_database_summary(
                connection=connection,
            )

    if verbose:
        print(
            "\nSQLite database initialized successfully."
        )

        print(
            f"Database: {database_path}"
        )

        print(
            "\nAll seeded records are synthetic "
            "and are intended only for demonstration testing."
        )


if __name__ == "__main__":
    initialize_database()
