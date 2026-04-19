import boto3
import json
import os
from datetime import datetime, timezone

S3_SYNC_ENABLED = os.getenv("S3_SYNC_ENABLED", "false").lower() == "true"
BUCKET = os.getenv("S3_BUCKET_NAME", "")
REGION = os.getenv("AWS_REGION", "ap-south-1")


def get_s3_client():
    return boto3.client("s3", region_name=REGION)


def sync_entry_to_s3(user_id: str, entry: dict) -> bool:
    """
    Push a single entry to S3.
    Key pattern: journals/{user_id}/{entry_id}.json
    Returns True on success, False if sync is disabled or fails.
    """
    if not S3_SYNC_ENABLED or not BUCKET:
        return False
    try:
        client = get_s3_client()
        key = f"journals/{user_id}/{entry['id']}.json"
        payload = {
            **entry,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        client.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        return True
    except Exception as e:
        print(f"[s3_sync] Failed to sync entry {entry.get('id')}: {e}")
        return False


def delete_entry_from_s3(user_id: str, entry_id: str) -> bool:
    """Remove an entry from S3 when deleted from the app."""
    if not S3_SYNC_ENABLED or not BUCKET:
        return False
    try:
        client = get_s3_client()
        key = f"journals/{user_id}/{entry_id}.json"
        client.delete_object(Bucket=BUCKET, Key=key)
        return True
    except Exception as e:
        print(f"[s3_sync] Failed to delete entry {entry_id} from S3: {e}")
        return False
