import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv(r"C:\Users\Capstone\Intership_main\ProConnect\.env")

account_id = os.getenv("R2_ACCOUNT_ID")
access_key = os.getenv("R2_ACCESS_KEY_ID")
secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
bucket     = os.getenv("R2_BUCKET_NAME")

client = boto3.client(
    "s3",
    endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
    region_name="auto",
)

try:
    cors = client.get_bucket_cors(Bucket=bucket)
    print("CORS rules:", json.dumps(cors.get("CORSRules", []), indent=2))
except Exception as e:
    print("No CORS config or error:", e)

# Also test presign
try:
    key = "test/test-presign.jpg"
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": "image/jpeg"},
        ExpiresIn=60,
    )
    print("\nPresign OK:", url[:80], "...")
except Exception as e:
    print("Presign FAILED:", e)
