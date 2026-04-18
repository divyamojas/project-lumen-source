import asyncpg
from fastapi import Depends, HTTPException, Request, status
from supabase import AsyncClient

from app.auth import get_current_user

ROLE_HIERARCHY = {"user": 1, "admin": 2, "superuser": 3}


def get_supabase(request: Request) -> AsyncClient:
    return request.app.state.supabase


def get_db_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.db_pool


def require_role(minimum_role: str):
    """Returns caller's user_id after verifying their role meets the minimum."""
    required_level = ROLE_HIERARCHY[minimum_role]

    async def dependency(
        request: Request,
        user_id: str = Depends(get_current_user),
    ) -> str:
        supabase = get_supabase(request)
        result = (
            await supabase.table("user_roles")
            .select("role")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        role = result.data["role"] if result.data else "user"
        if ROLE_HIERARCHY.get(role, 1) < required_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user_id

    return dependency
