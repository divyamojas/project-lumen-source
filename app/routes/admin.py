from datetime import date, timezone, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import AsyncClient

from app.dependencies import get_supabase, require_role, ROLE_HIERARCHY
from app.models.admin import AdminStats, RoleUpdate, UserSummary
from app.models.entry import EntryListResponse, EntryResponse

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStats)
async def get_stats(
    supabase: AsyncClient = Depends(get_supabase),
    _: str = Depends(require_role("admin")),
):
    today = date.today().isoformat()

    total_users_res, total_entries_res, today_entries_res = await _gather(
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
    offset = (page - 1) * page_size

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

    # Delete entries → roles → auth user
    await supabase.table("entries").delete().eq("user_id", target_id).execute()
    await supabase.table("user_roles").delete().eq("user_id", target_id).execute()
    await supabase.auth.admin.delete_user(target_id)


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


# ── Internal helper ───────────────────────────────────────────────────────────

async def _gather(*coroutines):
    import asyncio
    return await asyncio.gather(*coroutines)
