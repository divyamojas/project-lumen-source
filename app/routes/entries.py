import os
from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client, Client

from app.auth import get_current_user
from app.models.entry import EntryCreate, EntryUpdate, EntryResponse

router = APIRouter(prefix="/entries", tags=["entries"])


def get_supabase() -> Client:
    return create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))


@router.post("", response_model=EntryResponse, status_code=201)
def create_entry(entry: EntryCreate, user_id: str = Depends(get_current_user)):
    supabase = get_supabase()
    data = {**entry.model_dump(), "user_id": user_id}
    result = supabase.table("entries").insert(data).execute()
    return result.data[0]


@router.get("", response_model=list[EntryResponse])
def list_entries(
    page: int = 1,
    page_size: int = 20,
    user_id: str = Depends(get_current_user),
):
    supabase = get_supabase()
    offset = (page - 1) * page_size
    result = (
        supabase.table("entries")
        .select("*")
        .eq("user_id", user_id)
        .order("createdAt", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return result.data


@router.get("/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: str, user_id: str = Depends(get_current_user)):
    supabase = get_supabase()
    result = (
        supabase.table("entries")
        .select("*")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Entry not found")
    return result.data


@router.patch("/{entry_id}", response_model=EntryResponse)
def update_entry(
    entry_id: str,
    patch: EntryUpdate,
    user_id: str = Depends(get_current_user),
):
    supabase = get_supabase()
    existing = (
        supabase.table("entries")
        .select("id")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Entry not found")

    updates = {k: v for k, v in patch.model_dump().items() if v is not None}
    result = supabase.table("entries").update(updates).eq("id", entry_id).execute()
    return result.data[0]


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: str, user_id: str = Depends(get_current_user)):
    supabase = get_supabase()
    existing = (
        supabase.table("entries")
        .select("id")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Entry not found")

    supabase.table("entries").delete().eq("id", entry_id).execute()
