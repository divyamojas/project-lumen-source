# Lumen Backend — Claude Context

## Current State (as of 2026-04-18)
Phase 1 complete. Standalone FastAPI service with full entry CRUD, JWT auth, RBAC,
admin dashboard API, schema introspection, file-based migrations, and raw SQL execution.
Not yet wired to the frontend — that comes in Phase 2.

## File Map
```
app/
  main.py           — FastAPI app, CORS, lifespan (Supabase client + asyncpg pool + schema snapshot)
  auth.py           — get_current_user (HTTPBearer, JWKS primary, HS256 fallback)
  db.py             — asyncpg pool, schema snapshot, migration helpers, raw SQL execution
  dependencies.py   — get_supabase, get_db_pool, require_role(minimum_role)
  routes/
    entries.py      — POST/GET/GET{id}/PATCH{id}/DELETE{id} /entries (user-scoped)
    users.py        — GET /users/me
    admin.py        — /admin/stats, /admin/users, /admin/users/{id}, role management, user deletion, all-entries
    schema.py       — /admin/schema, /admin/schema/refresh, /admin/schema/migrations, /admin/sql
  models/
    entry.py        — EntryCreate, EntryUpdate, EntryResponse, EntryListResponse
    admin.py        — RoleUpdate, UserSummary, AdminStats
    schema.py       — SchemaSnapshot, MigrationRecord, SQLRequest, SQLResponse
migrations/
  0001_create_entries.sql
  0002_create_user_roles.sql
  0003_create_sql_audit_log.sql
```

## Stack
- Python 3.11, FastAPI 0.115, Pydantic v2, PyJWT, supabase-py 2.28, asyncpg 0.29
- Supabase async client for all application queries
- asyncpg pool for migrations, schema introspection, and raw SQL
- No ORM anywhere

## Startup Sequence (lifespan)
1. Supabase `AsyncClient` created → `app.state.supabase`
2. asyncpg pool created → `app.state.db_pool` (graceful — app starts even if DATABASE_URL is missing)
3. `schema_migrations` table auto-created if absent
4. Schema snapshot written to `schema_snapshot.json`

## Auth
`get_current_user` in `app/auth.py` uses FastAPI `HTTPBearer` (shows Authorize button in Swagger).

Resolution order:
1. Extract Bearer token from `Authorization` header
2. Peek at token `alg` (no sig check)
3. Asymmetric (RS256/ES256): verify via JWKS at `SUPABASE_URL/auth/v1/.well-known/jwks.json`
4. HS256 + `SUPABASE_JWT_SECRET` set: verify locally
5. HS256 + no secret: verify remotely via `GET /auth/v1/user` with `SUPABASE_PUBLISHABLE_KEY`

Returns `user_id` (JWT `sub`) on success. Raises 401 on failure.

## RBAC
`require_role(minimum_role)` in `app/dependencies.py`. Hierarchy: `user < admin < superuser`.
Looks up caller's role in `user_roles` table. Returns `user_id` on success, raises 403 on failure.

Permission matrix:
| Endpoint group              | admin | superuser |
|-----------------------------|:-----:|:---------:|
| GET /admin/stats            |   ✓   |     ✓     |
| GET /admin/users            |   ✓   |     ✓     |
| GET /admin/users/{id}       |   ✓   |     ✓     |
| PATCH /admin/users/{id}/role|       |     ✓     |
| DELETE /admin/users/{id}    |       |     ✓     |
| GET /admin/entries          |       |     ✓     |
| DELETE /admin/entries/{id}  |       |     ✓     |
| GET /admin/schema           |   ✓   |     ✓     |
| POST /admin/schema/refresh  |   ✓   |     ✓     |
| GET /admin/schema/migrations|   ✓   |     ✓     |
| POST /admin/schema/migrations/apply |  |  ✓   |
| POST /admin/sql             |       |     ✓     |

Safety guards: superuser cannot delete themselves or modify another superuser's role.

## Schema & Migrations
- Migration files live in `migrations/` named `NNNN_description.sql`
- `schema_migrations` table tracks applied files (filename + MD5 checksum)
- `POST /admin/schema/migrations/apply` applies all pending files in order, then refreshes snapshot
- `GET /admin/schema/migrations` shows status: `applied | pending | checksum_mismatch`
- Bootstrap: first-time setup must be done via Supabase SQL Editor (chicken-and-egg with user_roles)

## Raw SQL
`POST /admin/sql` (superuser only). Executes arbitrary SQL via asyncpg.
- SELECT/WITH/EXPLAIN/SHOW: returns rows as list of dicts
- DDL/DML: returns status string + affected row count
- Every execution is logged to `sql_audit_log` table (best-effort)
- All executions logged to stdout via Python `logging`

## Environment Variables
Required:
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY` — `sb_secret_...` key, bypasses RLS
- `SUPABASE_PUBLISHABLE_KEY` — `sb_publishable_...` key, used for HS256 fallback auth
- `DATABASE_URL` — direct Postgres connection string for asyncpg
  Format: `postgresql://postgres.[ref]:[password]@[host]:5432/postgres`
  Note: URL-encode special chars in password (e.g. `@` → `%40`)

Optional / legacy:
- `SUPABASE_JWKS_URL` — override JWKS endpoint
- `SUPABASE_JWT_SECRET` — legacy HS256 shared secret
- `SUPABASE_SERVICE_ROLE_KEY` — legacy service role key
- `SUPABASE_ANON_KEY` — legacy anon key

## Rules (non-negotiable)
- No ORM — Supabase client or asyncpg only
- No hardcoded secrets — all config from `.env`
- `user_id` always from JWT, never from request body
- Return 404 (not 403) for owned-resource-not-found
- Return 401 for missing/invalid JWT
- CORS: allow `http://localhost:3000`
- No TypeScript — Python only
- No local installs — Docker only
