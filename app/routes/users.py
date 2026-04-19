import logging

from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.auth import get_current_user
from app.dependencies import get_supabase, get_user_role
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
