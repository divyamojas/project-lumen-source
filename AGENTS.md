# Lumen Backend — Codex Agent Context

## What This Project Is
FastAPI backend for the Lumen journal app.
It now powers the live frontend for backend-managed auth, entry CRUD, RBAC, schema/migration APIs, raw SQL, and broader superuser admin APIs.

## Stack
- Python 3.11, FastAPI 0.115, Pydantic v2, supabase-py 2.28, PyJWT, asyncpg 0.29
- Supabase async client for application/auth-admin work
- asyncpg pool for migrations, schema inspection, table-data admin work, and raw SQL
- No ORM, no TypeScript, no local installs

## File Map
- `app/main.py` — app setup, CORS, lifespan, schema snapshot cache, router registration
- `app/auth.py` — JWT verification
- `app/db.py` — asyncpg pool, snapshot, migrations, raw SQL
- `app/dependencies.py` — shared dependencies and role checks
- `app/routes/auth.py` — login/signup/reset/google start/logout
- `app/routes/entries.py` — user-scoped entry CRUD
- `app/routes/users.py` — `/users/me`
- `app/routes/admin.py` — stats, user management, auth-user admin, generic table data admin
- `app/routes/schema.py` — schema snapshot, migrations, SQL console
- `app/models/auth.py` — auth request/response models
- `app/models/admin.py` — admin and data-management models
- `app/models/entry.py` — entry models
- `app/models/schema.py` — schema/migration/SQL models

## Auth Pattern
- Frontend authenticates through backend routes, not directly against Supabase JS
- Backend returns/accepts bearer tokens
- `/users/me` is the canonical session-resolution endpoint for the frontend

JWT verification order:
1. bearer extraction
2. unverified `alg` peek
3. JWKS for asymmetric tokens
4. local HS256 verify if `SUPABASE_JWT_SECRET` is set
5. remote Supabase `/auth/v1/user` verification otherwise

## RBAC
`require_role(minimum_role)` checks `user_roles`
Hierarchy: `user < admin < superuser`

## API Highlights
Current frontend-facing auth:
- `/auth/login`
- `/auth/sign-up` and aliases
- `/auth/reset-password` and aliases
- `/auth/google/start` and aliases
- `/auth/logout`
- `/users/me`

Current frontend-facing admin:
- `/admin/stats`
- `/admin/users`
- `/admin/entries`
- `/admin/schema`
- `/admin/schema/migrations`
- `/admin/sql`

Additional superuser APIs now available:
- `/admin/auth/users`
- `/admin/auth/users/{target_id}`
- `/admin/auth/users/{target_id}/invite`
- `/admin/auth/users/{target_id}/generate-link`
- `/admin/data/tables`
- `/admin/data/{schema_name}/{table_name}/query`
- `/admin/data/{schema_name}/{table_name}/insert`
- `/admin/data/{schema_name}/{table_name}`

## Environment Variables
Required:
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_PUBLISHABLE_KEY`
- `DATABASE_URL`

Useful optional vars:
- `CORS_ORIGINS`
- `PASSWORD_RESET_REDIRECT_TO`
- `BOOTSTRAP_SUPERUSER_ID`
- `SUPABASE_JWKS_URL`
- `SUPABASE_JWT_SECRET`

## Strict Rules
- No ORM — Supabase client or asyncpg only
- No hardcoded secrets
- `user_id` always comes from JWT, never from request body
- Return 404, not 403, for owned-resource-not-found
- Return 401 for missing or invalid JWT
- Treat superuser admin/data endpoints as dangerous and keep them guarded

## Out of Scope
- Frontend wiring details
- AWS/S3/Lambda/Bedrock/Comprehend work unless explicitly requested
