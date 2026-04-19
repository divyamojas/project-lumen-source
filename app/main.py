import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from supabase import acreate_client

from app import db
from app.routes import admin, auth, entries, legal, schema, sync, users


def _require(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise RuntimeError(f"{var} is required but not set")
    return val


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Supabase async client
    app.state.supabase = await acreate_client(
        _require("SUPABASE_URL"),
        os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or _require("SUPABASE_SECRET_KEY"),
    )

    # Direct Postgres pool (migrations, raw SQL) — optional, degrades gracefully
    try:
        app.state.db_pool = await db.create_pool()
        await db.ensure_migrations_table(app.state.db_pool)
        await db.apply_all_pending(app.state.db_pool)

        bootstrap_id = os.getenv("BOOTSTRAP_SUPERUSER_ID")
        if bootstrap_id:
            await db.bootstrap_superuser(app.state.db_pool, bootstrap_id)

        app.state.schema_snapshot = await db.take_schema_snapshot(app.state.db_pool)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "DB pool unavailable — schema/migration/SQL endpoints disabled: %s", exc
        )
        app.state.db_pool = None
        app.state.schema_snapshot = None

    yield

    if app.state.db_pool is not None:
        await app.state.db_pool.close()


_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "https://localhost",
    "https://127.0.0.1",
    "http://127.0.0.1:3000",
]

def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    extra = [o.strip() for o in raw.split(",") if o.strip()]
    return list(dict.fromkeys(_DEFAULT_CORS_ORIGINS + extra))


app = FastAPI(title="Lumen API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(entries.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(schema.router)
app.include_router(sync.router)
app.include_router(legal.router)


@app.get("/health")
async def health(request: Request):
    pool = request.app.state.db_pool
    return {
        "status": "ok" if pool is not None else "degraded",
        "db_pool_size": pool.get_size() if pool is not None else None,
    }
