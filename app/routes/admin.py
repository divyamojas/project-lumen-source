import asyncio
import logging
import os
import re
from datetime import date, timezone, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from supabase import AsyncClient

logger = logging.getLogger(__name__)

from app.dependencies import get_supabase, require_role, ROLE_HIERARCHY
from app.models.admin import (
    AdminAuthActionRequest,
    AdminAuthUserCreate,
    AdminAuthUserResponse,
    AdminAuthUserUpdate,
    AdminStats,
    AdminTableDeleteRequest,
    AdminTableListResponse,
    AdminTableMutationRequest,
    AdminTableMutationResponse,
    AdminTableQueryRequest,
    AdminTableQueryResponse,
    AdminTableUpdateRequest,
    RoleUpdate,
    UserSummary,
)
from app.models.entry import EntryListResponse, EntryResponse

router = APIRouter(prefix="/admin", tags=["admin"])
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_GENERIC_DATA_ALLOWED_SCHEMAS = {"public"}
_GENERIC_DATA_DENYLIST = {"schema_migrations", "sql_audit_log", "admin_api_audit_log"}


def _generic_admin_data_enabled() -> bool:
    return os.getenv("ENABLE_GENERIC_DATA_ADMIN", "false").lower() == "true"


def _generic_admin_data_write_enabled() -> bool:
    return os.getenv("ENABLE_GENERIC_DATA_ADMIN_WRITES", "false").lower() == "true"


def _require_generic_admin_data_enabled() -> None:
    if not _generic_admin_data_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Generic admin data APIs are disabled for this deployment",
        )


def _require_generic_admin_data_write_enabled() -> None:
    if not _generic_admin_data_write_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Generic admin data write APIs are disabled for this deployment",
        )


# ── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStats)
async def get_stats(
    supabase: AsyncClient = Depends(get_supabase),
    _: str = Depends(require_role("admin")),
):
    today = date.today().isoformat()

    total_users_res, total_entries_res, today_entries_res = await asyncio.gather(
        supabase.table("user_roles").select("user_id", count="exact").execute(),
        supabase.table("entries").select("id", count="exact").execute(),
        supabase.table("entries").select("id", count="exact").gte("createdAt", today).execute(),
    )

    return AdminStats(
        total_users=total_users_res.count or 0,
        total_entries=total_entries_res.count or 0,
        entries_today=today_entries_res.count or 0,
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserSummary])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    supabase: AsyncClient = Depends(get_supabase),
    _: str = Depends(require_role("admin")),
):
    auth_response = await supabase.auth.admin.list_users(page=page, per_page=page_size)
    users = auth_response.users if hasattr(auth_response, "users") else []

    user_ids = [u.id for u in users]
    if not user_ids:
        return []

    roles_res = (
        await supabase.table("user_roles")
        .select("user_id, role")
        .in_("user_id", user_ids)
        .execute()
    )
    roles_map = {r["user_id"]: r["role"] for r in roles_res.data}

    counts_res = (
        await supabase.table("entries")
        .select("user_id", count="exact")
        .in_("user_id", user_ids)
        .execute()
    )
    from collections import Counter
    entry_counts = Counter(r["user_id"] for r in counts_res.data)

    return [
        UserSummary(
            user_id=u.id,
            email=u.email,
            role=roles_map.get(u.id, "user"),
            entry_count=entry_counts.get(u.id, 0),
            created_at=str(u.created_at) if u.created_at else None,
            last_sign_in_at=str(u.last_sign_in_at) if u.last_sign_in_at else None,
        )
        for u in users
    ]


@router.get("/users/{target_id}", response_model=UserSummary)
async def get_user(
    target_id: str,
    supabase: AsyncClient = Depends(get_supabase),
    _: str = Depends(require_role("admin")),
):
    auth_user = await supabase.auth.admin.get_user_by_id(target_id)
    if not auth_user or not auth_user.user:
        raise HTTPException(status_code=404, detail="User not found")

    u = auth_user.user

    roles_res = (
        await supabase.table("user_roles")
        .select("role")
        .eq("user_id", target_id)
        .maybe_single()
        .execute()
    )
    role = roles_res.data["role"] if roles_res.data else "user"

    count_res = (
        await supabase.table("entries")
        .select("id", count="exact")
        .eq("user_id", target_id)
        .execute()
    )

    return UserSummary(
        user_id=u.id,
        email=u.email,
        role=role,
        entry_count=count_res.count or 0,
        created_at=str(u.created_at) if u.created_at else None,
        last_sign_in_at=str(u.last_sign_in_at) if u.last_sign_in_at else None,
    )


@router.patch("/users/{target_id}/role", response_model=UserSummary)
async def update_user_role(
    target_id: str,
    body: RoleUpdate,
    supabase: AsyncClient = Depends(get_supabase),
    caller_id: str = Depends(require_role("superuser")),
):
    if body.role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=422, detail=f"Invalid role. Choose from: {list(ROLE_HIERARCHY)}")

    # Prevent demoting another superuser
    existing = (
        await supabase.table("user_roles")
        .select("role")
        .eq("user_id", target_id)
        .maybe_single()
        .execute()
    )
    if existing.data and existing.data["role"] == "superuser" and target_id != caller_id:
        raise HTTPException(status_code=403, detail="Cannot change another superuser's role")

    await supabase.table("user_roles").upsert({
        "user_id": target_id,
        "role": body.role,
        "assigned_by": caller_id,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    return await get_user(target_id, supabase=supabase, _=caller_id)


@router.delete("/users/{target_id}", status_code=204)
async def delete_user(
    target_id: str,
    supabase: AsyncClient = Depends(get_supabase),
    caller_id: str = Depends(require_role("superuser")),
):
    if target_id == caller_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    existing = (
        await supabase.table("user_roles")
        .select("role")
        .eq("user_id", target_id)
        .maybe_single()
        .execute()
    )
    if existing.data and existing.data["role"] == "superuser":
        raise HTTPException(status_code=403, detail="Cannot delete a superuser")

    # Snapshot role before deletion for compensating write on failure
    role_snapshot = existing.data["role"] if existing.data else "user"

    # Delete entries → roles → auth user (no distributed transaction — compensate on failure)
    entries_deleted = False
    roles_deleted = False

    try:
        await supabase.table("entries").delete().eq("user_id", target_id).execute()
        entries_deleted = True

        await supabase.table("user_roles").delete().eq("user_id", target_id).execute()
        roles_deleted = True

        await supabase.auth.admin.delete_user(target_id)
    except Exception as exc:
        logger.error(
            "delete_user partial failure target=%s entries_deleted=%s roles_deleted=%s: %s",
            target_id,
            entries_deleted,
            roles_deleted,
            exc,
        )
        if roles_deleted:
            try:
                await supabase.table("user_roles").upsert({
                    "user_id": target_id,
                    "role": role_snapshot,
                    "assigned_by": caller_id,
                    "assigned_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
            except Exception as restore_exc:
                logger.error("delete_user role restore failed for %s: %s", target_id, restore_exc)
        raise HTTPException(status_code=502, detail="User deletion failed — state may be inconsistent") from exc


# ── Entries (all users) ───────────────────────────────────────────────────────

@router.get("/entries", response_model=EntryListResponse)
async def list_all_entries(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: Optional[str] = Query(default=None, description="Filter by a specific user"),
    supabase: AsyncClient = Depends(get_supabase),
    _: str = Depends(require_role("superuser")),
):
    offset = (page - 1) * page_size
    query = (
        supabase.table("entries")
        .select("*", count="exact")
        .order("createdAt", desc=True)
    )
    if user_id:
        query = query.eq("user_id", user_id)

    result = await query.range(offset, offset + page_size - 1).execute()
    total = result.count or 0
    return EntryListResponse(
        data=result.data,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(offset + page_size) < total,
    )


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_any_entry(
    entry_id: str,
    supabase: AsyncClient = Depends(get_supabase),
    _: str = Depends(require_role("superuser")),
):
    result = await supabase.table("entries").delete().eq("id", entry_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Entry not found")


# ── Auth user management ─────────────────────────────────────────────────────

def _normalize_auth_user_response(user: Any, role: str = "user") -> AdminAuthUserResponse:
    return AdminAuthUserResponse(
        user_id=user.id,
        email=getattr(user, "email", None),
        phone=getattr(user, "phone", None),
        role=role,
        disabled=bool(getattr(user, "banned_until", None)),
        email_confirmed_at=(
            str(getattr(user, "email_confirmed_at", None))
            if getattr(user, "email_confirmed_at", None)
            else None
        ),
        phone_confirmed_at=(
            str(getattr(user, "phone_confirmed_at", None))
            if getattr(user, "phone_confirmed_at", None)
            else None
        ),
        created_at=str(getattr(user, "created_at", None)) if getattr(user, "created_at", None) else None,
        last_sign_in_at=(
            str(getattr(user, "last_sign_in_at", None))
            if getattr(user, "last_sign_in_at", None)
            else None
        ),
        user_metadata=dict(getattr(user, "user_metadata", None) or {}),
        app_metadata=dict(getattr(user, "app_metadata", None) or {}),
    )


async def _get_role_for_user(supabase: AsyncClient, user_id: str) -> str:
    result = (
        await supabase.table("user_roles")
        .select("role")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    role_data = getattr(result, "data", None)
    return role_data["role"] if isinstance(role_data, dict) and role_data.get("role") else "user"


async def _set_role_for_user(supabase: AsyncClient, user_id: str, role: str, caller_id: str) -> None:
    await supabase.table("user_roles").upsert({
        "user_id": user_id,
        "role": role,
        "assigned_by": caller_id,
        "assigned_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


async def _audit_admin_action(
    request: Request,
    caller_id: str,
    action: str,
    target: str,
    request_data: dict[str, Any] | None = None,
    row_count: int | None = None,
    status_text: str = "success",
) -> None:
    try:
        await request.app.state.supabase.table("admin_api_audit_log").insert({
            "executed_by": caller_id,
            "action": action,
            "target": target,
            "request_data": request_data or {},
            "row_count": row_count,
            "status": status_text,
        }).execute()
    except Exception as exc:
        logger.warning("admin audit write failed action=%s target=%s: %s", action, target, exc)


@router.post("/auth/users", response_model=AdminAuthUserResponse, status_code=201)
async def create_auth_user(
    body: AdminAuthUserCreate,
    request: Request,
    supabase: AsyncClient = Depends(get_supabase),
    caller_id: str = Depends(require_role("superuser")),
):
    if body.role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=422, detail=f"Invalid role. Choose from: {list(ROLE_HIERARCHY)}")

    created = await supabase.auth.admin.create_user({
        "email": body.email,
        **({"password": body.password} if body.password else {}),
        "email_confirm": body.email_confirm,
        "phone_confirm": body.phone_confirm,
        "user_metadata": body.user_metadata,
        "app_metadata": body.app_metadata,
    })
    user = created.user if hasattr(created, "user") else None
    if not user:
        raise HTTPException(status_code=502, detail="Supabase Auth user creation failed")

    await _set_role_for_user(supabase, user.id, body.role, caller_id)
    await _audit_admin_action(
        request,
        caller_id,
        "auth_user_create",
        user.id,
        request_data={"email": body.email, "role": body.role},
        status_text="created",
    )
    return _normalize_auth_user_response(user, role=body.role)


@router.patch("/auth/users/{target_id}", response_model=AdminAuthUserResponse)
async def update_auth_user(
    target_id: str,
    body: AdminAuthUserUpdate,
    request: Request,
    supabase: AsyncClient = Depends(get_supabase),
    caller_id: str = Depends(require_role("superuser")),
):
    current_role = await _get_role_for_user(supabase, target_id)
    next_role = body.role or current_role

    if next_role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=422, detail=f"Invalid role. Choose from: {list(ROLE_HIERARCHY)}")
    if current_role == "superuser" and target_id != caller_id and next_role != "superuser":
        raise HTTPException(status_code=403, detail="Cannot change another superuser's role")

    payload = {
        key: value
        for key, value in {
            "email": body.email,
            "password": body.password,
            "email_confirm": body.email_confirm,
            "phone_confirm": body.phone_confirm,
            "ban_duration": body.ban_duration,
            "user_metadata": body.user_metadata,
            "app_metadata": body.app_metadata,
        }.items()
        if value is not None
    }

    response = await supabase.auth.admin.update_user_by_id(target_id, payload)
    user = response.user if hasattr(response, "user") else None
    if not user:
        raise HTTPException(status_code=502, detail="Supabase Auth user update failed")

    if body.role is not None:
        await _set_role_for_user(supabase, target_id, body.role, caller_id)
        current_role = body.role

    await _audit_admin_action(
        request,
        caller_id,
        "auth_user_update",
        target_id,
        request_data=body.model_dump(exclude_none=True),
        status_text="updated",
    )

    return _normalize_auth_user_response(user, role=current_role)


@router.post("/auth/users/{target_id}/invite")
async def invite_auth_user(
    target_id: str,
    body: AdminAuthActionRequest,
    request: Request,
    supabase: AsyncClient = Depends(get_supabase),
    caller_id: str = Depends(require_role("superuser")),
):
    auth_user = await supabase.auth.admin.get_user_by_id(target_id)
    user = auth_user.user if auth_user and getattr(auth_user, "user", None) else None
    if not user or not getattr(user, "email", None):
        raise HTTPException(status_code=404, detail="User email not found")

    await supabase.auth.admin.invite_user_by_email(user.email, {"redirect_to": body.redirect_to} if body.redirect_to else {})
    await _audit_admin_action(
        request,
        caller_id,
        "auth_user_invite",
        target_id,
        request_data=body.model_dump(exclude_none=True),
        status_text="invited",
    )
    return {"message": "Invite email requested"}


@router.post("/auth/users/{target_id}/generate-link")
async def generate_auth_link(
    target_id: str,
    body: AdminAuthActionRequest,
    request: Request,
    supabase: AsyncClient = Depends(get_supabase),
    caller_id: str = Depends(require_role("superuser")),
):
    auth_user = await supabase.auth.admin.get_user_by_id(target_id)
    user = auth_user.user if auth_user and getattr(auth_user, "user", None) else None
    if not user or not getattr(user, "email", None):
        raise HTTPException(status_code=404, detail="User email not found")

    payload = {
        "type": "magiclink",
        "email": user.email,
        **({"options": {"redirect_to": body.redirect_to}} if body.redirect_to else {}),
    }
    result = await supabase.auth.admin.generate_link(payload)
    await _audit_admin_action(
        request,
        caller_id,
        "auth_user_generate_link",
        target_id,
        request_data=body.model_dump(exclude_none=True),
        status_text="generated",
    )
    return result if isinstance(result, dict) else getattr(result, "model_dump", lambda: {"data": str(result)})()


# ── Generic table data access ────────────────────────────────────────────────

def _validate_identifier(value: str, label: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise HTTPException(status_code=422, detail=f"Invalid {label}")
    return value


def _qualified_table_name(schema_name: str, table_name: str) -> str:
    return f'"{schema_name}"."{table_name}"'


def _build_filter_clause(filters: dict[str, Any], start_index: int = 1) -> tuple[str, list[Any]]:
    if not filters:
        return "", []

    clauses: list[str] = []
    values: list[Any] = []
    position = start_index

    for key, value in filters.items():
        column = _validate_identifier(key, "column name")
        if value is None:
            clauses.append(f'"{column}" IS NULL')
            continue
        clauses.append(f'"{column}" = ${position}')
        values.append(value)
        position += 1

    return " WHERE " + " AND ".join(clauses), values


async def _table_exists(request: Request, schema_name: str, table_name: str) -> bool:
    snapshot = request.app.state.schema_snapshot if hasattr(request.app.state, "schema_snapshot") else None
    key = f"{schema_name}.{table_name}"
    if snapshot and key in snapshot.get("tables", {}):
        return True
    return False


def _assert_manageable_table(schema_name: str, table_name: str) -> None:
    if schema_name not in _GENERIC_DATA_ALLOWED_SCHEMAS:
        raise HTTPException(
            status_code=403,
            detail="Generic table APIs are limited to allowed application schemas",
        )
    if table_name in _GENERIC_DATA_DENYLIST:
        raise HTTPException(
            status_code=403,
            detail="This table is protected; use dedicated admin endpoints or SQL instead",
        )


@router.get("/data/tables", response_model=AdminTableListResponse)
async def list_data_tables(
    request: Request,
    include_system: bool = Query(default=False),
    _: str = Depends(require_role("superuser")),
):
    _require_generic_admin_data_enabled()
    snapshot = getattr(request.app.state, "schema_snapshot", None)
    if snapshot is None:
        snapshot = {}
    tables = sorted(snapshot.get("tables", {}).keys())
    if not include_system:
        tables = [table for table in tables if table.startswith("public.")]
    return AdminTableListResponse(tables=tables)


@router.post("/data/{schema_name}/{table_name}/query", response_model=AdminTableQueryResponse)
async def query_table_rows(
    schema_name: str,
    table_name: str,
    body: AdminTableQueryRequest,
    request: Request,
    caller_id: str = Depends(require_role("superuser")),
):
    import asyncpg

    _require_generic_admin_data_enabled()
    schema_name = _validate_identifier(schema_name, "schema name")
    table_name = _validate_identifier(table_name, "table name")
    _assert_manageable_table(schema_name, table_name)
    if not await _table_exists(request, schema_name, table_name):
        raise HTTPException(status_code=404, detail="Table not found in schema snapshot")

    pool: asyncpg.Pool = request.app.state.db_pool
    if pool is None:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured or unreachable")

    if body.limit < 1 or body.limit > 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    if body.offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")

    where_clause, values = _build_filter_clause(body.filters)
    order_clause = ""
    if body.order_by:
        direction = body.order_direction.lower()
        if direction not in {"asc", "desc"}:
            raise HTTPException(status_code=422, detail="order_direction must be asc or desc")
        order_column = _validate_identifier(body.order_by, "order column")
        order_clause = f' ORDER BY "{order_column}" {direction.upper()}'

    qualified_name = _qualified_table_name(schema_name, table_name)
    limit_placeholder = len(values) + 1
    offset_placeholder = len(values) + 2
    query = (
        f"SELECT * FROM {qualified_name}"
        f"{where_clause}{order_clause}"
        f" LIMIT ${limit_placeholder} OFFSET ${offset_placeholder}"
    )
    values.extend([body.limit, body.offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *values)

    await _audit_admin_action(
        request,
        caller_id,
        "table_query",
        f"{schema_name}.{table_name}",
        request_data=body.model_dump(),
        row_count=len(rows),
    )

    return AdminTableQueryResponse(
        schema_name=schema_name,
        table=table_name,
        rows=[dict(row) for row in rows],
        row_count=len(rows),
    )


@router.post("/data/{schema_name}/{table_name}/insert", response_model=AdminTableMutationResponse, status_code=201)
async def insert_table_row(
    schema_name: str,
    table_name: str,
    body: AdminTableMutationRequest,
    request: Request,
    caller_id: str = Depends(require_role("superuser")),
):
    import asyncpg

    _require_generic_admin_data_enabled()
    _require_generic_admin_data_write_enabled()
    schema_name = _validate_identifier(schema_name, "schema name")
    table_name = _validate_identifier(table_name, "table name")
    _assert_manageable_table(schema_name, table_name)
    if not body.values:
        raise HTTPException(status_code=422, detail="values must not be empty")
    if not await _table_exists(request, schema_name, table_name):
        raise HTTPException(status_code=404, detail="Table not found in schema snapshot")

    pool: asyncpg.Pool = request.app.state.db_pool
    if pool is None:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured or unreachable")

    columns = [_validate_identifier(column, "column name") for column in body.values.keys()]
    placeholders = [f"${index}" for index in range(1, len(columns) + 1)]
    values = [body.values[column] for column in body.values.keys()]
    qualified_name = _qualified_table_name(schema_name, table_name)
    column_list = ", ".join(f'"{column}"' for column in columns)
    query = (
        f"INSERT INTO {qualified_name} ({column_list}) "
        f'VALUES ({", ".join(placeholders)}) RETURNING *'
    )

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *values)

    await _audit_admin_action(
        request,
        caller_id,
        "table_insert",
        f"{schema_name}.{table_name}",
        request_data={"values": body.values},
        row_count=len(rows),
        status_text="created",
    )

    return AdminTableMutationResponse(
        schema_name=schema_name,
        table=table_name,
        rows=[dict(row) for row in rows],
        row_count=len(rows),
    )


@router.patch("/data/{schema_name}/{table_name}", response_model=AdminTableMutationResponse)
async def patch_table_rows(
    schema_name: str,
    table_name: str,
    body: AdminTableUpdateRequest,
    request: Request,
    caller_id: str = Depends(require_role("superuser")),
):
    import asyncpg

    _require_generic_admin_data_enabled()
    _require_generic_admin_data_write_enabled()
    schema_name = _validate_identifier(schema_name, "schema name")
    table_name = _validate_identifier(table_name, "table name")
    _assert_manageable_table(schema_name, table_name)
    if not body.values:
        raise HTTPException(status_code=422, detail="values must not be empty")
    if not body.filters:
        raise HTTPException(status_code=422, detail="filters must not be empty")
    if not await _table_exists(request, schema_name, table_name):
        raise HTTPException(status_code=404, detail="Table not found in schema snapshot")

    pool: asyncpg.Pool = request.app.state.db_pool
    if pool is None:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured or unreachable")

    columns = [_validate_identifier(column, "column name") for column in body.values.keys()]
    values = list(body.values.values())
    set_clause = ", ".join(
        f'"{column}" = ${index}' for index, column in enumerate(columns, start=1)
    )
    where_clause, filter_values = _build_filter_clause(body.filters, start_index=len(values) + 1)
    qualified_name = _qualified_table_name(schema_name, table_name)
    query = f"UPDATE {qualified_name} SET {set_clause}{where_clause} RETURNING *"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *(values + filter_values))

    await _audit_admin_action(
        request,
        caller_id,
        "table_update",
        f"{schema_name}.{table_name}",
        request_data=body.model_dump(),
        row_count=len(rows),
        status_text="updated",
    )

    return AdminTableMutationResponse(
        schema_name=schema_name,
        table=table_name,
        rows=[dict(row) for row in rows],
        row_count=len(rows),
    )


@router.delete("/data/{schema_name}/{table_name}", response_model=AdminTableMutationResponse)
async def delete_table_rows(
    schema_name: str,
    table_name: str,
    body: AdminTableDeleteRequest,
    request: Request,
    caller_id: str = Depends(require_role("superuser")),
):
    import asyncpg

    _require_generic_admin_data_enabled()
    _require_generic_admin_data_write_enabled()
    schema_name = _validate_identifier(schema_name, "schema name")
    table_name = _validate_identifier(table_name, "table name")
    _assert_manageable_table(schema_name, table_name)
    if not body.filters:
        raise HTTPException(status_code=422, detail="filters must not be empty")
    if not await _table_exists(request, schema_name, table_name):
        raise HTTPException(status_code=404, detail="Table not found in schema snapshot")

    pool: asyncpg.Pool = request.app.state.db_pool
    if pool is None:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured or unreachable")

    where_clause, values = _build_filter_clause(body.filters)
    qualified_name = _qualified_table_name(schema_name, table_name)
    query = f"DELETE FROM {qualified_name}{where_clause} RETURNING *"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *values)

    await _audit_admin_action(
        request,
        caller_id,
        "table_delete",
        f"{schema_name}.{table_name}",
        request_data=body.model_dump(),
        row_count=len(rows),
        status_text="deleted",
    )

    return AdminTableMutationResponse(
        schema_name=schema_name,
        table=table_name,
        rows=[dict(row) for row in rows],
        row_count=len(rows),
    )
