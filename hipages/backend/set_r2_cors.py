"""
Set CORS rules on the R2 bucket to allow browser direct uploads from localhost and production.
Run once: venv/Scripts/python.exe set_r2_cors.py
"""
import boto3, os, json
from dotenv import load_dotenv

load_dotenv(r"C:\Users\Capstone\Intership_main\hipages\.env")

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

cors_config = {
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
            "AllowedOrigins": [
                "http://localhost:3000",
                "http://localhost:3001",
                "https://*.vercel.app",
                "*",          # broad for dev — tighten in production
            ],
            "ExposeHeaders":  ["ETag"],
            "MaxAgeSeconds":  3600,
        }
    ]
}

try:
    client.put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration=cors_config,
    )
    print(f"[OK] CORS rules applied to bucket '{bucket}'")
    print(json.dumps(cors_config, indent=2))
except Exception as e:
    print(f"[FAILED] Could not set CORS: {e}")
    print("You may need to set CORS manually in the Cloudflare R2 dashboard.")
    print("Go to: R2 > your bucket > Settings > CORS > add the rule with AllowedOrigins=[*]")
