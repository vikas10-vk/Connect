import boto3
import os
import uuid
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=False
)

R2_ACCOUNT_ID      = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID   = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME     = os.getenv("R2_BUCKET_NAME")
R2_PUBLIC_URL      = os.getenv("R2_PUBLIC_URL")

def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )

def generate_presigned_upload_url(
    folder: str,
    file_extension: str,
    content_type: str = None,
) -> dict:
    """
    Generate a presigned URL for direct client upload to R2.
    Returns the upload URL and the final public file URL.
    """
    client   = get_r2_client()
    file_key = f"{folder}/{uuid.uuid4()}.{file_extension}"

    # Use caller-supplied MIME type if available, fall back to inference
    mime = content_type or f"image/{file_extension}"

    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket":      R2_BUCKET_NAME,
            "Key":         file_key,
            "ContentType": mime,
        },
        ExpiresIn=300,  # 5 minutes to complete upload
    )

    public_url = f"{R2_PUBLIC_URL}/{file_key}"

    return {
        "upload_url": upload_url,
        "file_url":   public_url,
        "file_key":   file_key,
    }