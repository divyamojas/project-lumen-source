import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import AsyncClient

from app.auth import get_current_user
from app.dependencies import get_supabase
from app.models.entry import (
    EntryCreate,
    EntryListResponse,
    EntryResponse,
    EntryUpdate,
    JournalType,
    normalize_type_metadata,
)
from app.services.s3_sync import delete_entry_from_s3, sync_entry_to_s3

router = APIRouter(prefix="/entries", tags=["entries"])
logger = logging.getLogger(__name__)


async def _record_sync_audit(supabase: AsyncClient, user_id: str, result: dict, scope: str = "entry") -> None:
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


async def _sync_and_audit_entry(supabase: AsyncClient, user_id: str, entry: dict) -> None:
    result = await asyncio.to_thread(sync_entry_to_s3, user_id, entry)
    await _record_sync_audit(supabase, user_id, result)


async def _delete_and_audit_entry(supabase: AsyncClient, user_id: str, entry_id: str) -> None:
    result = await asyncio.to_thread(delete_entry_from_s3, user_id, entry_id)
    await _record_sync_audit(supabase, user_id, result)


@router.post("", response_model=EntryResponse, status_code=201)
async def create_entry(
    entry: EntryCreate,
    supabase: AsyncClient = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    data = {**entry.model_dump(), "user_id": user_id}
    result = await supabase.table("entries").insert(data).execute()
    row = result.data[0]
    asyncio.create_task(_sync_and_audit_entry(supabase, user_id, row))
    return row


@router.get("", response_model=EntryListResponse)
async def list_entries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tag: Optional[str] = Query(default=None),
    collection: Optional[str] = Query(default=None),
    favorite: Optional[bool] = Query(default=None),
    pinned: Optional[bool] = Query(default=None),
    from_date: Optional[str] = Query(default=None, description="ISO date — createdAt >="),
    to_date: Optional[str] = Query(default=None, description="ISO date — createdAt <="),
    supabase: AsyncClient = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    offset = (page - 1) * page_size

    query = (
        supabase.table("entries")
        .select("*", count="exact")
        .eq("user_id", user_id)
        .order("createdAt", desc=True)
    )

    if tag is not None:
        query = query.contains("tags", [tag])
    if collection is not None:
        query = query.eq("collection", collection)
    if favorite is not None:
        query = query.eq("favorite", favorite)
    if pinned is not None:
        query = query.eq("pinned", pinned)
    if from_date is not None:
        query = query.gte("createdAt", from_date)
    if to_date is not None:
        query = query.lte("createdAt", to_date)

    result = await query.range(offset, offset + page_size - 1).execute()

    total = result.count or 0
    return EntryListResponse(
        data=result.data,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )


@router.get("/{entry_id}", response_model=EntryResponse)
async def get_entry(
    entry_id: str,
    supabase: AsyncClient = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    result = (
        await supabase.table("entries")
        .select("*")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Entry not found")
    return result.data


@router.patch("/{entry_id}", response_model=EntryResponse)
async def update_entry(
    entry_id: str,
    patch: EntryUpdate,
    supabase: AsyncClient = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    current_entry_result = (
        await supabase.table("entries")
        .select("journal_type")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not current_entry_result.data:
        raise HTTPException(status_code=404, detail="Entry not found")

    updates = patch.model_dump(exclude_unset=True)
    effective_journal_type = JournalType(
        updates.get("journal_type") or current_entry_result.data.get("journal_type") or JournalType.personal.value
    )
    if "type_metadata" in updates:
        updates["type_metadata"] = normalize_type_metadata(effective_journal_type, updates["type_metadata"])
    if "journal_type" in updates and "type_metadata" not in updates:
        updates["type_metadata"] = {}
    result = (
        await supabase.table("entries")
        .update(updates)
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Entry not found")
    row = result.data[0]
    asyncio.create_task(_sync_and_audit_entry(supabase, user_id, row))
    return row


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: str,
    supabase: AsyncClient = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    result = (
        await supabase.table("entries")
        .delete()
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Entry not found")
    asyncio.create_task(_delete_and_audit_entry(supabase, user_id, entry_id))
