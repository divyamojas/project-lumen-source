from typing import Optional
from pydantic import BaseModel


class RoleUpdate(BaseModel):
    role: str  # "user" | "admin" | "superuser"


class UserSummary(BaseModel):
    user_id: str
    email: Optional[str] = None
    role: str
    entry_count: int
    created_at: Optional[str] = None
    last_sign_in_at: Optional[str] = None


class AdminStats(BaseModel):
    total_users: int
    total_entries: int
    entries_today: int
