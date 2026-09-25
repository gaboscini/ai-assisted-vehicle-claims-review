import os

import boto3


PROFILE_NAME = os.getenv("CLAIMS_AWS_PROFILE") or None
REGION_NAME = os.getenv("CLAIMS_AWS_REGION", "us-east-1")
BUCKET_NAME = os.environ["CLAIMS_AWS_BUCKET"]
TABLE_NAME = os.environ["CLAIMS_AWS_CLAIMS_TABLE"]
FUNCTION_NAME = os.environ["CLAIMS_AWS_DOCUMENT_PROCESSING_FUNCTION"]


session = boto3.Session(
    profile_name=PROFILE_NAME,
    region_name=REGION_NAME,
)

identity = session.client("sts").get_caller_identity()
print("AWS account:", identity["Account"])

session.client("s3").head_bucket(Bucket=BUCKET_NAME)
print("S3 bucket access: OK")

table = session.resource("dynamodb").Table(TABLE_NAME)
table.load()
print("DynamoDB table access: OK")

function = session.client("lambda").get_function_configuration(
    FunctionName=FUNCTION_NAME
)
print("Lambda access:", function["FunctionName"], function["State"])
