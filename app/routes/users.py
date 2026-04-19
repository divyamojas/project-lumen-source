import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from supabase import AsyncClient

from app.auth import get_current_user
from app.dependencies import get_supabase, get_user_role
from app.models.auth import UserMeResponse
from app.models.entry import JournalType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

_DELETE_CONFIRMATION = "DELETE MY ACCOUNT"


class DeleteAccountRequest(BaseModel):
    confirm: Optional[str] = None


class UserPreferences(BaseModel):
    enabled_journal_types: list[JournalType] = Field(default_factory=lambda: [JournalType.personal])
    default_journal_type: JournalType = JournalType.personal

    @field_validator("enabled_journal_types")
    @classmethod
    def enabled_types_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("enabled_journal_types must contain at least one journal type")
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def default_type_must_be_enabled(self):
        if self.default_journal_type not in self.enabled_journal_types:
            raise ValueError("default_journal_type must be included in enabled_journal_types")
        return self


class UserPreferencesUpdate(BaseModel):
    enabled_journal_types: Optional[list[JournalType]] = None
    default_journal_type: Optional[JournalType] = None

    @field_validator("enabled_journal_types")
    @classmethod
    def enabled_types_must_not_be_empty(cls, v):
        if v is None:
            return v
        if not v:
            raise ValueError("enabled_journal_types must contain at least one journal type")
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def default_type_must_be_enabled(self):
        if (
            self.default_journal_type is not None
            and self.enabled_journal_types is not None
            and self.default_journal_type not in self.enabled_journal_types
        ):
            raise ValueError("default_journal_type must be included in enabled_journal_types")
        return self


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


@router.get("/me/preferences", response_model=UserPreferences)
async def get_my_preferences(
    user_id: str = Depends(get_current_user),
    supabase: AsyncClient = Depends(get_supabase),
):
    result = (
        await supabase.table("users")
        .select("enabled_journal_types,default_journal_type")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        return UserPreferences()
    return UserPreferences(**result.data)


@router.patch("/me/preferences", response_model=UserPreferences)
async def update_my_preferences(
    body: UserPreferencesUpdate,
    user_id: str = Depends(get_current_user),
    supabase: AsyncClient = Depends(get_supabase),
):
    existing = (
        await supabase.table("users")
        .select("enabled_journal_types,default_journal_type")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    current_preferences = UserPreferences(**existing.data) if existing.data else UserPreferences()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        return current_preferences

    merged_preferences = UserPreferences(
        enabled_journal_types=updates.get(
            "enabled_journal_types",
            current_preferences.enabled_journal_types,
        ),
        default_journal_type=updates.get(
            "default_journal_type",
            current_preferences.default_journal_type,
        ),
    )

    await supabase.table("users").upsert({
        "id": user_id,
        "enabled_journal_types": [item.value for item in merged_preferences.enabled_journal_types],
        "default_journal_type": merged_preferences.default_journal_type.value,
    }).execute()
    return merged_preferences


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
