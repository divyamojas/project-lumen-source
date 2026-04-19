import os

from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.auth import get_current_user
from app.dependencies import get_supabase, require_role
from app.services.s3_sync import BUCKET, REGION, S3_SYNC_ENABLED, get_s3_client, sync_entry_to_s3

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status")
async def sync_status(_user_id: str = Depends(get_current_user)):
    reachable = False
    if S3_SYNC_ENABLED and BUCKET:
        try:
            get_s3_client().head_bucket(Bucket=BUCKET)
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
    user_id: str = Depends(require_role("admin")),
    supabase: AsyncClient = Depends(get_supabase),
):
    result = await supabase.table("entries").select("*").eq("user_id", user_id).execute()
    entries = result.data or []
    synced = 0
    failed = 0
    for entry in entries:
        if sync_entry_to_s3(user_id, entry):
            synced += 1
        else:
            failed += 1
    return {"synced": synced, "failed": failed, "total": len(entries)}
