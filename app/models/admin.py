from typing import Any, Optional
from pydantic import BaseModel, Field


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


class AdminAuthUserCreate(BaseModel):
    email: str
    password: Optional[str] = None
    email_confirm: bool = True
    phone_confirm: bool = False
    user_metadata: dict[str, Any] = Field(default_factory=dict)
    app_metadata: dict[str, Any] = Field(default_factory=dict)
    role: str = "user"


class AdminAuthUserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    email_confirm: Optional[bool] = None
    phone_confirm: Optional[bool] = None
    ban_duration: Optional[str] = None
    user_metadata: Optional[dict[str, Any]] = None
    app_metadata: Optional[dict[str, Any]] = None
    role: Optional[str] = None


class AdminAuthActionRequest(BaseModel):
    redirect_to: Optional[str] = None


class AdminAuthUserResponse(BaseModel):
    user_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    disabled: bool = False
    email_confirmed_at: Optional[str] = None
    phone_confirmed_at: Optional[str] = None
    created_at: Optional[str] = None
    last_sign_in_at: Optional[str] = None
    user_metadata: dict[str, Any] = Field(default_factory=dict)
    app_metadata: dict[str, Any] = Field(default_factory=dict)


class AdminTableListResponse(BaseModel):
    tables: list[str]


class AdminTableQueryRequest(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 50
    offset: int = 0
    order_by: Optional[str] = None
    order_direction: str = "asc"


class AdminTableMutationRequest(BaseModel):
    values: dict[str, Any]


class AdminTableDeleteRequest(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)


class AdminTableUpdateRequest(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Any] = Field(default_factory=dict)


class AdminTableQueryResponse(BaseModel):
    schema: str
    table: str
    rows: list[dict[str, Any]]
    row_count: int


class AdminTableMutationResponse(BaseModel):
    schema: str
    table: str
    rows: list[dict[str, Any]]
    row_count: int
