import json
import os
from datetime import datetime, timezone

try:
    import boto3

    _boto3_available = True
except ImportError:
    boto3 = None
    _boto3_available = False

S3_SYNC_ENABLED = os.getenv("S3_SYNC_ENABLED", "false").lower() == "true"
BUCKET = os.getenv("S3_BUCKET_NAME", "")
REGION = os.getenv("AWS_REGION", "ap-south-1")

_s3_client = None


def _result(*, success: bool, action: str, entry_id: str | None = None, key: str | None = None, error: str | None = None) -> dict:
    return {
        "success": success,
        "action": action,
        "entry_id": entry_id,
        "bucket": BUCKET or None,
        "region": REGION,
        "object_key": key,
        "error": error,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", region_name=REGION)
    return _s3_client


def sync_entry_to_s3(user_id: str, entry: dict) -> dict:
    """
    Push a single entry to S3.
    Key pattern: journals/{user_id}/{entry_id}.json
    Returns a structured result for logging and UI status surfaces.
    """
    entry_id = entry.get("id")
    key = f"journals/{user_id}/{entry_id}.json" if entry_id else None
    if not S3_SYNC_ENABLED or not BUCKET or not _boto3_available:
        return _result(
            success=False,
            action="upsert",
            entry_id=entry_id,
            key=key,
            error="S3 backup is disabled or unavailable in this deployment",
        )
    try:
        client = _get_s3()
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
        return _result(success=True, action="upsert", entry_id=entry_id, key=key)
    except Exception as e:
        print(f"[s3_sync] Failed to sync entry {entry.get('id')}: {e}")
        return _result(success=False, action="upsert", entry_id=entry_id, key=key, error=str(e))


def delete_entry_from_s3(user_id: str, entry_id: str) -> dict:
    """Remove an entry from S3 when deleted from the app."""
    key = f"journals/{user_id}/{entry_id}.json"
    if not S3_SYNC_ENABLED or not BUCKET or not _boto3_available:
        return _result(
            success=False,
            action="delete",
            entry_id=entry_id,
            key=key,
            error="S3 backup is disabled or unavailable in this deployment",
        )
    try:
        client = _get_s3()
        client.delete_object(Bucket=BUCKET, Key=key)
        return _result(success=True, action="delete", entry_id=entry_id, key=key)
    except Exception as e:
        print(f"[s3_sync] Failed to delete entry {entry_id} from S3: {e}")
        return _result(success=False, action="delete", entry_id=entry_id, key=key, error=str(e))
