import logging

from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.auth import get_current_user
from app.dependencies import get_supabase
from app.models.auth import UserMeResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


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
        roles_res = (
            await supabase.table("user_roles")
            .select("role")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.warning("user_roles lookup failed for %s: %s", user_id, exc)
        roles_res = None

    role_data = getattr(roles_res, "data", None)
    role = role_data["role"] if isinstance(role_data, dict) and role_data.get("role") else "user"

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
