from services.policy_record_service import (
    get_policy_record,
)


default_policy_number = "POL-DEMO-000001"

entered_policy_number = input(
    f"Enter policy number "
    f"[{default_policy_number}]: "
).strip()

policy_number = (
    entered_policy_number
    if entered_policy_number
    else default_policy_number
)

print("\nLooking up policy record...\n")

policy_record = get_policy_record(
    policy_number=policy_number,
)

if policy_record is None:
    print(
        "No matching policy record was found."
    )
else:
    print("--- POLICY RECORD ---\n")
    print(
        policy_record.model_dump_json(
            indent=2
        )
    )
