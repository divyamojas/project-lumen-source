import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app import db
from app.dependencies import require_role
from app.models.schema import MigrationRecord, SchemaSnapshot, SQLRequest, SQLResponse

router = APIRouter(prefix="/admin", tags=["admin-schema"])


def get_pool(request: Request) -> asyncpg.Pool:
    pool = request.app.state.db_pool
    if pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured or unreachable",
        )
    return pool


# ── Schema snapshot ───────────────────────────────────────────────────────────

@router.get("/schema", response_model=SchemaSnapshot)
async def get_schema(
    _: str = Depends(require_role("admin")),
):
    snapshot = db.load_snapshot()
    if not snapshot:
        raise HTTPException(status_code=503, detail="Schema snapshot not yet available — restart the app or call /refresh")
    return snapshot


@router.post("/schema/refresh", response_model=SchemaSnapshot)
async def refresh_schema(
    pool: asyncpg.Pool = Depends(get_pool),
    _: str = Depends(require_role("admin")),
):
    return await db.take_schema_snapshot(pool)


# ── Migrations ────────────────────────────────────────────────────────────────

@router.get("/schema/migrations", response_model=list[MigrationRecord])
async def list_migrations(
    pool: asyncpg.Pool = Depends(get_pool),
    _: str = Depends(require_role("admin")),
):
    files = db.list_migration_files()
    applied = await db.get_applied_migrations(pool)

    records = []
    for f in files:
        if f["filename"] in applied:
            app_info = applied[f["filename"]]
            if app_info["checksum"] != f["checksum"]:
                migration_status = "checksum_mismatch"
            else:
                migration_status = "applied"
        else:
            migration_status = "pending"

        records.append(MigrationRecord(
            filename=f["filename"],
            status=migration_status,
            checksum=f["checksum"],
            applied_at=applied.get(f["filename"], {}).get("applied_at"),
            applied_by=applied.get(f["filename"], {}).get("applied_by"),
        ))

    return records


@router.post("/schema/migrations/apply", response_model=list[MigrationRecord])
async def apply_pending_migrations(
    pool: asyncpg.Pool = Depends(get_pool),
    caller_id: str = Depends(require_role("superuser")),
):
    files = db.list_migration_files()
    applied = await db.get_applied_migrations(pool)

    pending = [f for f in files if f["filename"] not in applied]
    if not pending:
        return await list_migrations(pool=pool, _=caller_id)

    for f in pending:
        await db.apply_migration(pool, f["filename"], f["sql"], applied_by=caller_id)

    # Refresh snapshot after schema changes
    await db.take_schema_snapshot(pool)

    return await list_migrations(pool=pool, _=caller_id)


# ── Raw SQL ───────────────────────────────────────────────────────────────────

@router.post("/sql", response_model=SQLResponse)
async def run_sql(
    body: SQLRequest,
    request: Request,
    pool: asyncpg.Pool = Depends(get_pool),
    caller_id: str = Depends(require_role("superuser")),
):
    if not body.query.strip():
        raise HTTPException(status_code=422, detail="Query must not be empty")

    try:
        result = await db.execute_sql(pool, body.query)
    except asyncpg.PostgresError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Persist to audit log (best-effort — don't fail the response if log insert fails)
    try:
        supabase = request.app.state.supabase
        await supabase.table("sql_audit_log").insert({
            "executed_by": caller_id,
            "query": body.query,
            "status": result["status"],
            "row_count": result["row_count"],
            "duration_ms": result["duration_ms"],
            "executed_at": result["executed_at"],
        }).execute()
    except Exception:
        pass

    return result
