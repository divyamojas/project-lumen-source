import asyncpg
import logging
from fastapi import Depends, HTTPException, Request, status
from supabase import AsyncClient

from app.auth import get_current_user

ROLE_HIERARCHY = {"user": 1, "admin": 2, "superuser": 3}
logger = logging.getLogger(__name__)


def get_supabase(request: Request) -> AsyncClient:
    return request.app.state.supabase


def get_db_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


async def get_user_role(supabase: AsyncClient, user_id: str) -> str:
    try:
        result = (
            await supabase.table("user_roles")
            .select("role")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
    except Exception as exc:
        logger.warning("role lookup failed for %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify user role",
        ) from exc

    role_data = getattr(result, "data", None)
    if isinstance(role_data, dict) and role_data.get("role"):
        return role_data["role"]
    return "user"


def require_role(minimum_role: str):
    """Returns caller's user_id after verifying their role meets the minimum."""
    required_level = ROLE_HIERARCHY[minimum_role]

    async def dependency(
        request: Request,
        user_id: str = Depends(get_current_user),
    ) -> str:
        supabase = get_supabase(request)
        role = await get_user_role(supabase, user_id)
        if ROLE_HIERARCHY.get(role, 1) < required_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user_id

    return dependency
