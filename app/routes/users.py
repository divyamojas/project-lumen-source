from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.dependencies import get_supabase, require_role
from supabase import AsyncClient

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_me(user_id: str = Depends(get_current_user)):
    return {"user_id": user_id}
