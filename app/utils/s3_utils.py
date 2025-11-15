import boto3
from botocore.exceptions import ClientError
from app.core.config import settings
import uuid


s3_client = boto3.client(
    's3',
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
    region_name=settings.aws_region
)

BUCKET_NAME = settings.s3_bucket_name


def upload_image_to_s3(image_bytes: bytes, prefix: str = "qrcode") -> str:
    """
    Upload image bytes to S3 and return the S3 key.
    """
    s3_key = f"{prefix}/{uuid.uuid4().hex}.png"
    try:
        s3_client.put_object(Bucket=BUCKET_NAME, Key=s3_key, Body=image_bytes, ContentType="image/png")
        return s3_key
    except ClientError as e:
        raise RuntimeError(f"Failed to upload image to S3: {e}")


def get_image_from_s3(s3_key: str) -> bytes:
    """
    Download image bytes from S3 by key.
    """
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return response['Body'].read()
    except ClientError as e:
        raise RuntimeError(f"Failed to get image from S3: {e}")


def generate_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """Generate a pre-signed URL for an object in S3.

    The bucket is private; this URL allows temporary public access.
    """
    try:
        url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        raise RuntimeError(f"Failed to generate presigned URL: {e}")
