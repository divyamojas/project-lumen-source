import logging

from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.auth import get_current_user
from app.dependencies import get_supabase, get_user_role
from app.services.s3_sync import BUCKET, REGION, S3_SYNC_ENABLED, _get_s3, sync_entry_to_s3

router = APIRouter(prefix="/sync", tags=["sync"])
logger = logging.getLogger(__name__)


async def _record_sync_audit(
    supabase: AsyncClient,
    user_id: str,
    result: dict,
    *,
    scope: str = "entry",
) -> None:
    try:
        await supabase.table("sync_audit_log").insert({
            "user_id": user_id,
            "entry_id": result.get("entry_id"),
            "action": result.get("action") or "upsert",
            "status": "success" if result.get("success") else "failed",
            "scope": scope,
            "bucket": result.get("bucket"),
            "object_key": result.get("object_key"),
            "region": result.get("region"),
            "error_message": result.get("error"),
            "created_at": result.get("created_at"),
        }).execute()
    except Exception as exc:
        logger.warning("sync audit write failed for user=%s entry=%s: %s", user_id, result.get("entry_id"), exc)


@router.get("/status")
async def sync_status(
    user_id: str = Depends(get_current_user),
    supabase: AsyncClient = Depends(get_supabase),
):
    reachable = False
    if S3_SYNC_ENABLED and BUCKET:
        try:
            _get_s3().head_bucket(Bucket=BUCKET)
            reachable = True
        except Exception:
            reachable = False

    latest_attempt = None
    try:
        latest_attempt_result = (
            await supabase.table("sync_audit_log")
            .select("status,action,scope,entry_id,bucket,object_key,region,error_message,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        latest_row = (latest_attempt_result.data or [None])[0]
        if latest_row:
            latest_attempt = {
                "status": latest_row.get("status"),
                "action": latest_row.get("action"),
                "scope": latest_row.get("scope"),
                "entry_id": latest_row.get("entry_id"),
                "bucket": latest_row.get("bucket"),
                "object_key": latest_row.get("object_key"),
                "region": latest_row.get("region"),
                "error": latest_row.get("error_message"),
                "created_at": latest_row.get("created_at"),
            }
    except Exception as exc:
        logger.warning("sync status audit lookup failed for user=%s: %s", user_id, exc)

    return {
        "enabled": S3_SYNC_ENABLED,
        "bucket": BUCKET or None,
        "region": REGION,
        "reachable": reachable,
        "last_attempt": latest_attempt,
    }


@router.post("/full")
async def full_sync(
    user_id: str = Depends(get_current_user),
    supabase: AsyncClient = Depends(get_supabase),
):
    role = await get_user_role(supabase, user_id)
    is_admin = role in {"admin", "superuser"}
    query = supabase.table("entries").select("*")
    if not is_admin:
        query = query.eq("user_id", user_id)

    result = await query.execute()
    entries = result.data or []
    synced = 0
    failed = 0
    for entry in entries:
        entry_user_id = entry.get("user_id", user_id)
        result = sync_entry_to_s3(entry_user_id, entry)
        await _record_sync_audit(
            supabase,
            entry_user_id,
            result,
            scope="full_sync",
        )
        if result.get("success"):
            synced += 1
        else:
            failed += 1
    return {
        "synced": synced,
        "failed": failed,
        "total": len(entries),
        "scope": "all-users" if is_admin else "current-user",
    }
