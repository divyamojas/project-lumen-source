from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import AsyncClient

from app.auth import get_current_user
from app.models.entry import EntryCreate, EntryUpdate, EntryResponse

router = APIRouter(prefix="/entries", tags=["entries"])


def get_supabase(request: Request) -> AsyncClient:
    return request.app.state.supabase


@router.post("", response_model=EntryResponse, status_code=201)
async def create_entry(
    entry: EntryCreate,
    supabase: AsyncClient = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    data = {**entry.model_dump(), "user_id": user_id}
    result = await supabase.table("entries").insert(data).execute()
    return result.data[0]


@router.get("", response_model=list[EntryResponse])
async def list_entries(
    page: int = 1,
    page_size: int = 20,
    supabase: AsyncClient = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    result = (
        await supabase.table("entries")
        .select("*")
        .eq("user_id", user_id)
        .order("createdAt", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return result.data


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
    existing = (
        await supabase.table("entries")
        .select("id")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Entry not found")

    updates = patch.model_dump(exclude_unset=True)
    result = await supabase.table("entries").update(updates).eq("id", entry_id).execute()
    return result.data[0]


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: str,
    supabase: AsyncClient = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    existing = (
        await supabase.table("entries")
        .select("id")
        .eq("id", entry_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Entry not found")

    await supabase.table("entries").delete().eq("id", entry_id).execute()
