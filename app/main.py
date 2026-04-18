import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import acreate_client

from app import db
from app.routes import admin, entries, schema, users


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

        await db.take_schema_snapshot(app.state.db_pool)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "DB pool unavailable — schema/migration/SQL endpoints disabled: %s", exc
        )
        app.state.db_pool = None

    yield

    await app.state.db_pool.close()


app = FastAPI(title="Lumen API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(entries.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(schema.router)


@app.get("/health")
async def health(request):
    pool_size = request.app.state.db_pool.get_size()
    return {"status": "ok", "db_pool_size": pool_size}
