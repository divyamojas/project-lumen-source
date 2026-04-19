import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import AsyncClient

from app.auth import get_current_user
from app.dependencies import get_supabase, get_user_role
from app.models.auth import UserMeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

_DELETE_CONFIRMATION = "DELETE MY ACCOUNT"


class DeleteAccountRequest(BaseModel):
    confirm: Optional[str] = None


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    user_id: str = Depends(get_current_user),
    supabase: AsyncClient = Depends(get_supabase),
):
    try:
        auth_user = await supabase.auth.admin.get_user_by_id(user_id)
    except Exception as exc:
        logger.warning("get_user_by_id failed for %s: %s", user_id, exc)
        auth_user = None
    user = auth_user.user if auth_user and getattr(auth_user, "user", None) else None

    try:
        role = await get_user_role(supabase, user_id)
    except Exception as exc:
        logger.warning("role resolution failed for %s: %s", user_id, exc)
        role = "user"

    metadata = {}
    if user and getattr(user, "user_metadata", None):
        metadata = dict(user.user_metadata)

    return UserMeResponse(
        id=user_id,
        email=getattr(user, "email", None),
        role=role,
        created_at=str(getattr(user, "created_at", None)) if user and getattr(user, "created_at", None) else None,
        last_sign_in_at=(
            str(getattr(user, "last_sign_in_at", None))
            if user and getattr(user, "last_sign_in_at", None)
            else None
        ),
        metadata=metadata,
    )


@router.delete("/me/entries")
async def delete_my_entries(
    user_id: str = Depends(get_current_user),
    supabase: AsyncClient = Depends(get_supabase),
):
    result = await supabase.table("entries").delete().eq("user_id", user_id).execute()
    count = len(result.data) if result.data else 0
    return {"deleted": True, "entries_removed": count}


@router.delete("/me")
async def delete_my_account(
    body: DeleteAccountRequest,
    user_id: str = Depends(get_current_user),
    supabase: AsyncClient = Depends(get_supabase),
):
    if body.confirm != _DELETE_CONFIRMATION:
        raise HTTPException(
            status_code=400,
            detail=f'Confirmation string must be exactly "{_DELETE_CONFIRMATION}"',
        )

    entries_result = await supabase.table("entries").delete().eq("user_id", user_id).execute()
    entries_removed = len(entries_result.data) if entries_result.data else 0

    try:
        await supabase.auth.admin.delete_user(user_id)
    except Exception as exc:
        logger.error("Failed to delete auth user %s: %s", user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to delete account")

    return {"deleted": True, "entries_removed": entries_removed}
