from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.auth import get_current_user
from app.dependencies import get_supabase, get_user_role
from app.services.s3_sync import BUCKET, REGION, S3_SYNC_ENABLED, _get_s3, sync_entry_to_s3

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status")
async def sync_status(_user_id: str = Depends(get_current_user)):
    reachable = False
    if S3_SYNC_ENABLED and BUCKET:
        try:
            _get_s3().head_bucket(Bucket=BUCKET)
            reachable = True
        except Exception:
            reachable = False

    return {
        "enabled": S3_SYNC_ENABLED,
        "bucket": BUCKET or None,
        "region": REGION,
        "reachable": reachable,
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
        if sync_entry_to_s3(entry_user_id, entry):
            synced += 1
        else:
            failed += 1
    return {
        "synced": synced,
        "failed": failed,
        "total": len(entries),
        "scope": "all-users" if is_admin else "current-user",
    }
