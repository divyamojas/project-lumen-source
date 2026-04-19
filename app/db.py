import asyncpg
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SNAPSHOT_PATH = Path("/app/schema_snapshot.json")
MIGRATIONS_DIR = Path("/app/migrations")


# ── Pool ─────────────────────────────────────────────────────────────────────

async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=2,
        max_size=10,
        command_timeout=30,
    )


# ── Schema snapshot ───────────────────────────────────────────────────────────

async def take_schema_snapshot(pool: asyncpg.Pool) -> dict:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                t.table_schema,
                t.table_name,
                c.column_name,
                c.data_type,
                c.udt_name,
                c.is_nullable,
                c.column_default,
                c.ordinal_position
            FROM information_schema.tables t
            JOIN information_schema.columns c
                ON t.table_name = c.table_name
                AND t.table_schema = c.table_schema
            WHERE t.table_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
                AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_schema, t.table_name, c.ordinal_position
        """)

        indexes = await conn.fetch("""
            SELECT
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY schemaname, tablename, indexname
        """)

        constraints = await conn.fetch("""
            SELECT
                ns.nspname AS table_schema,
                cls.relname AS table_name,
                con.conname AS constraint_name,
                CASE con.contype
                    WHEN 'p' THEN 'PRIMARY KEY'
                    WHEN 'f' THEN 'FOREIGN KEY'
                    WHEN 'u' THEN 'UNIQUE'
                    WHEN 'c' THEN 'CHECK'
                    WHEN 'x' THEN 'EXCLUDE'
                    ELSE con.contype::text
                END AS constraint_type,
                pg_get_constraintdef(con.oid) AS definition
            FROM pg_constraint con
            JOIN pg_class cls ON cls.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = cls.relnamespace
            WHERE ns.nspname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY ns.nspname, cls.relname, con.conname
        """)

        triggers = await conn.fetch("""
            SELECT
                event_object_schema AS table_schema,
                event_object_table AS table_name,
                trigger_name,
                action_timing,
                array_agg(DISTINCT event_manipulation ORDER BY event_manipulation) AS events,
                action_statement
            FROM information_schema.triggers
            WHERE event_object_schema NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            GROUP BY event_object_schema, event_object_table, trigger_name, action_timing, action_statement
            ORDER BY event_object_schema, event_object_table, trigger_name
        """)

        policies = await conn.fetch("""
            SELECT
                schemaname,
                tablename,
                policyname,
                permissive,
                roles,
                cmd,
                qual,
                with_check
            FROM pg_policies
            WHERE schemaname NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
            ORDER BY schemaname, tablename, policyname
        """)

    tables: dict = {}
    for row in rows:
        key = f"{row['table_schema']}.{row['table_name']}"
        if key not in tables:
            tables[key] = {
                "schema": row["table_schema"],
                "name": row["table_name"],
                "columns": [],
                "indexes": [],
                "constraints": [],
                "triggers": [],
                "policies": [],
            }
        tables[key]["columns"].append({
            "name": row["column_name"],
            "type": row["data_type"],
            "udt_name": row["udt_name"],
            "nullable": row["is_nullable"] == "YES",
            "default": row["column_default"],
        })

    for idx in indexes:
        key = f"{idx['schemaname']}.{idx['tablename']}"
        if key in tables:
            tables[key]["indexes"].append({
                "name": idx["indexname"],
                "definition": idx["indexdef"],
            })

    for constraint in constraints:
        key = f"{constraint['table_schema']}.{constraint['table_name']}"
        if key in tables:
            tables[key]["constraints"].append({
                "name": constraint["constraint_name"],
                "constraint_type": constraint["constraint_type"],
                "definition": constraint["definition"],
            })

    for trigger in triggers:
        key = f"{trigger['table_schema']}.{trigger['table_name']}"
        if key in tables:
            tables[key]["triggers"].append({
                "name": trigger["trigger_name"],
                "timing": trigger["action_timing"],
                "events": list(trigger["events"] or []),
                "statement": trigger["action_statement"],
            })

    for policy in policies:
        key = f"{policy['schemaname']}.{policy['tablename']}"
        if key in tables:
            tables[key]["policies"].append({
                "name": policy["policyname"],
                "permissive": policy["permissive"],
                "command": policy["cmd"],
                "roles": list(policy["roles"] or []),
                "using_expression": policy["qual"],
                "with_check_expression": policy["with_check"],
            })

    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }

    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2))
    logger.info("Schema snapshot written to %s (%d tables)", SNAPSHOT_PATH, len(tables))
    return snapshot


def load_snapshot() -> dict | None:
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text())
    return None


# ── Migrations ────────────────────────────────────────────────────────────────

async def ensure_migrations_table(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id          SERIAL PRIMARY KEY,
                filename    TEXT UNIQUE NOT NULL,
                checksum    TEXT NOT NULL,
                applied_by  UUID REFERENCES auth.users(id) ON DELETE SET NULL,
                applied_at  TIMESTAMPTZ DEFAULT now()
            )
        """)


def _checksum(sql: str) -> str:
    return hashlib.md5(sql.encode()).hexdigest()


def list_migration_files() -> list[dict]:
    if not MIGRATIONS_DIR.exists():
        return []
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return [
        {"filename": f.name, "checksum": _checksum(f.read_text()), "sql": f.read_text()}
        for f in files
    ]


async def get_applied_migrations(pool: asyncpg.Pool) -> dict[str, dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT filename, checksum, applied_by, applied_at FROM schema_migrations ORDER BY id"
        )
    return {
        r["filename"]: {
            "checksum": r["checksum"],
            "applied_by": str(r["applied_by"]) if r["applied_by"] else None,
            "applied_at": r["applied_at"].isoformat() if r["applied_at"] else None,
        }
        for r in rows
    }


async def apply_migration(
    pool: asyncpg.Pool, filename: str, sql: str, applied_by: str | None = None
) -> None:
    checksum = _checksum(sql)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(sql)
            await conn.execute(
                """
                INSERT INTO schema_migrations (filename, checksum, applied_by)
                VALUES ($1, $2, $3)
                """,
                filename, checksum, applied_by,
            )
    logger.info("Applied migration: %s", filename)


# ── Bootstrap ─────────────────────────────────────────────────────────────────

async def bootstrap_superuser(pool: asyncpg.Pool, user_id: str) -> bool:
    """Insert the first superuser if user_roles is empty. Returns True if seeded."""
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM user_roles")
        if count == 0:
            await conn.execute(
                "INSERT INTO user_roles (user_id, role) VALUES ($1, 'superuser') "
                "ON CONFLICT DO NOTHING",
                user_id,
            )
            logger.info("Bootstrapped superuser: %s", user_id)
            return True
    return False


async def apply_all_pending(pool: asyncpg.Pool) -> list[str]:
    """Apply all pending migrations. Returns list of applied filenames."""
    files = list_migration_files()
    applied = await get_applied_migrations(pool)
    pending = [f for f in files if f["filename"] not in applied]
    for f in pending:
        await apply_migration(pool, f["filename"], f["sql"])
    if pending:
        logger.info("Applied %d migration(s): %s", len(pending), [f["filename"] for f in pending])
    return [f["filename"] for f in pending]


# ── Raw SQL execution ─────────────────────────────────────────────────────────

_SELECT_LIKE = re.compile(r"^\s*(SELECT|WITH|EXPLAIN|SHOW|TABLE)\b", re.IGNORECASE)


async def execute_sql(pool: asyncpg.Pool, query: str) -> dict:
    start = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        if _SELECT_LIKE.match(query):
            records = await conn.fetch(query)
            rows = [dict(r) for r in records]
            row_count = len(rows)
            status = f"SELECT {row_count}"
        else:
            status = await conn.execute(query)
            rows = []
            parts = status.split()
            row_count = int(parts[-1]) if parts and parts[-1].isdigit() else 0

    duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    logger.info(
        "SQL executed | status=%s rows=%d duration_ms=%d query=%.120s",
        status, row_count, duration_ms, query.replace("\n", " "),
    )

    return {
        "query": query,
        "status": status,
        "row_count": row_count,
        "rows": rows,
        "duration_ms": duration_ms,
        "executed_at": start.isoformat(),
    }
