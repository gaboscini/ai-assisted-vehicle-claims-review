from pydantic import BaseModel


class VehicleRecord(BaseModel):
    vehicle_id: str
    plate_number: str
    year: int
    make: str
    model: str
    chassis_number: str
    engine_number: str
    registration_expiration_date: str


class PolicyRecord(BaseModel):
    policy_number: str
    policy_status: str
    coverage_type: str
    coverage_start_date: str
    coverage_end_date: str

    customer_id: str
    customer_name: str
    identity_number: str
    date_of_birth: str
    address: str
    sim_number: str
    sim_class: str
    sim_expiration_date: str

    vehicle: VehicleRecord