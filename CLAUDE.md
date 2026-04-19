# Lumen Backend — Claude Context

## Current State (as of 2026-04-19)
FastAPI backend for the Lumen journal app.
It now serves the live auth and admin surface used by the frontend: backend-managed auth, entry CRUD, RBAC,
schema introspection, file-based migrations, raw SQL, and broader superuser admin APIs for auth users and table data.

## Agent Files
`AGENTS.md` is the lean Codex-facing companion to this file.
It should stay short and practical, not a full mirror of this document.

## Repo Boundaries
- This repo owns backend routes, auth verification, Supabase access, asyncpg access, models, and admin APIs
- The root repo owns Docker orchestration and local HTTPS/proxy behavior
- The frontend repo owns UI, client persistence, session UI, and admin screens

## File Map
```
app/
  main.py           — FastAPI app, CORS, lifespan, router registration
  auth.py           — JWT verification via HTTPBearer; JWKS primary, HS256 fallback
  db.py             — asyncpg pool, schema snapshot, migration helpers, raw SQL execution
  dependencies.py   — get_supabase, get_db_pool, require_role(minimum_role)
  routes/
    auth.py         — backend auth endpoints for login/signup/reset/google start/logout
    entries.py      — user-scoped entry CRUD
    users.py        — current-user resolution (`/users/me`)
    admin.py        — admin stats, user management, cross-user entry access, auth-user admin, generic table data admin
    schema.py       — schema snapshot, migrations, raw SQL
  models/
    auth.py         — auth request/response models
    entry.py        — entry models
    admin.py        — admin and table-management models
    schema.py       — schema snapshot, migration, SQL models
migrations/
  0001_create_entries.sql
  0002_create_user_roles.sql
  0003_create_sql_audit_log.sql
```

## Stack
- Python 3.11
- FastAPI 0.115
- Pydantic v2
- supabase-py 2.28
- PyJWT
- asyncpg 0.29
- No ORM anywhere

## Startup Sequence
1. Supabase `AsyncClient` created → `app.state.supabase`
2. asyncpg pool created → `app.state.db_pool` when `DATABASE_URL` is available
3. `schema_migrations` table ensured
4. Pending migrations auto-applied
5. Optional superuser bootstrap runs if `BOOTSTRAP_SUPERUSER_ID` is set
6. Schema snapshot written to `schema_snapshot.json` and cached in `app.state.schema_snapshot`

If the DB pool cannot start, the app still boots in degraded mode and schema/migration/SQL features are unavailable.

## Auth
`get_current_user` in `app/auth.py` uses FastAPI `HTTPBearer`.

JWT verification order:
1. Extract bearer token
2. Peek at token `alg`
3. RS256/ES256 → verify via Supabase JWKS
4. HS256 + `SUPABASE_JWT_SECRET` → verify locally
5. HS256 without local secret → verify remotely via `SUPABASE_URL/auth/v1/user` with `SUPABASE_PUBLISHABLE_KEY`

Current backend auth routes:
- `POST /auth/login`
- `POST /auth/sign-up`
- `POST /auth/signup`
- `POST /auth/register`
- `POST /auth/reset-password`
- `POST /auth/password/reset`
- `POST /auth/forgot-password`
- `GET /auth/google/start`
- `GET /auth/google`
- `GET /auth/login/google`
- `POST /auth/logout`

`/users/me` returns the authenticated user’s id, email, role, timestamps, and metadata.

## RBAC
`require_role(minimum_role)` in `app/dependencies.py`
Hierarchy: `user < admin < superuser`

Role source:
- `user_roles.role`
- missing row defaults to `user`

Safety guards already enforced:
- cannot delete yourself
- cannot demote or delete another superuser through the normal admin user-role flows

## Current API Surface
User routes:
- `/entries`
- `/users/me`
- `/health`

Admin routes currently used by the frontend:
- `GET /admin/stats`
- `GET /admin/users`
- `GET /admin/users/{id}`
- `PATCH /admin/users/{id}/role`
- `DELETE /admin/users/{id}`
- `GET /admin/entries`
- `DELETE /admin/entries/{id}`
- `GET /admin/schema`
- `POST /admin/schema/refresh`
- `GET /admin/schema/migrations`
- `POST /admin/schema/migrations/apply`
- `POST /admin/sql`

Broader superuser routes exposed for direct admin-panel expansion:
- `POST /admin/auth/users`
- `PATCH /admin/auth/users/{target_id}`
- `POST /admin/auth/users/{target_id}/invite`
- `POST /admin/auth/users/{target_id}/generate-link`
- `GET /admin/data/tables`
- `POST /admin/data/{schema_name}/{table_name}/query`
- `POST /admin/data/{schema_name}/{table_name}/insert`
- `PATCH /admin/data/{schema_name}/{table_name}`
- `DELETE /admin/data/{schema_name}/{table_name}`

These are intentionally powerful and should remain `superuser` only.

## Schema & Migrations
- Migration files live in `migrations/` as `NNNN_description.sql`
- `schema_migrations` tracks applied files and checksums
- `POST /admin/schema/migrations/apply` applies all pending files in order
- schema refresh and SQL execution also refresh the cached schema snapshot when possible
- raw SQL can change anything the connected Postgres role is allowed to change

## Raw SQL
`POST /admin/sql` is superuser-only and executes arbitrary SQL through asyncpg.

Behavior:
- `SELECT`/`WITH`/`EXPLAIN`/`SHOW`/`TABLE` → returns rows
- DDL/DML → returns status plus affected row count
- best-effort audit log is written to `sql_audit_log`

## Environment Variables
Required:
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_PUBLISHABLE_KEY`
- `DATABASE_URL`

Optional or legacy:
- `SUPABASE_JWKS_URL`
- `SUPABASE_JWT_SECRET`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY`
- `BOOTSTRAP_SUPERUSER_ID`
- `PASSWORD_RESET_REDIRECT_TO`
- `CORS_ORIGINS`

## Rules
- No ORM — Supabase client or asyncpg only
- No hardcoded secrets — all config from `.env`
- `user_id` always comes from JWT, never from request body
- Return 404 for owned-resource-not-found
- Return 401 for missing/invalid JWT
- Prefer explicit, guarded superuser APIs over hidden backend shortcuts
- No TypeScript — Python only
- No local installs — Docker only

## Out of Scope
- Frontend implementation details
- AWS/S3/Lambda/Bedrock/Comprehend work unless explicitly requested
- Replacing Supabase/Auth/Postgres with another stack
