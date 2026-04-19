# Lumen — Backend

> **Your journal. Private backup. Future AI.**
> A private, calm journal suite where your data stays under your Lumen deployment —
> and where AI works *on your data*, not on someone else's servers.

Lumen is a journaling suite for six use cases: personal reflection, science
and research logging, travel, fitness, work, and creative writing. Each type
gets purpose-built fields and prompts. Entries can be backed up to an
AWS S3 bucket configured for the Lumen deployment. An AI layer (in progress)
will let you query your journal in natural language using Bedrock.

**Status:** Phase 1 (core journaling) is usable but still being hardened.
Phase 2 (deployment-managed S3 backup) is partially implemented and still in progress.
Phases 3–5 (Bedrock, NL query, sentiment) remain on the roadmap.

---

## Architecture

- Python 3.11, FastAPI 0.115, Pydantic v2
- Supabase async client for auth and application data
- asyncpg for migrations, schema inspection, and raw SQL
- No ORM anywhere

## Routes

### Auth
- `POST /auth/login`
- `POST /auth/sign-up`
- `POST /auth/reset-password`
- `GET /auth/google/start`
- `POST /auth/logout`

### User
- `GET /users/me`
- `GET /users/me/preferences`
- `PATCH /users/me/preferences`
- `DELETE /users/me/entries`
- `DELETE /users/me`
- `GET /health`

### Entries
- `GET /entries`
- `POST /entries`
- `GET /entries/{id}`
- `PATCH /entries/{id}`
- `DELETE /entries/{id}`

### Backup
- `GET /sync/status`
- `POST /sync/full`

### Admin (admin role required)
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

### Superuser
- `POST /admin/auth/users`
- `PATCH /admin/auth/users/{target_id}`
- `GET /admin/data/tables`
- `POST /admin/data/{schema_name}/{table_name}/query`
- `POST /admin/data/{schema_name}/{table_name}/insert`
- `PATCH /admin/data/{schema_name}/{table_name}`
- `DELETE /admin/data/{schema_name}/{table_name}`

## How To Run

This backend is started by the root orchestrator repo, not by a local compose file in this directory.

1. Install Docker Desktop or another runtime that supports `docker compose`.
2. Open a terminal in the sibling `project-lumen/` repo.
3. Copy `.env.example` to `.env` and fill in the required values.
4. Start the development stack: `./start.sh`
5. API is available at `http://localhost:8000`.
6. Interactive docs at `http://localhost:8000/docs`.

## Environment Variables

Required:
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_PUBLISHABLE_KEY`
- `DATABASE_URL`

Optional:
- `CORS_ORIGINS`
- `SUPABASE_JWT_SECRET`
- `SUPABASE_JWKS_URL`
- `BOOTSTRAP_SUPERUSER_ID`
- `PASSWORD_RESET_REDIRECT_TO`
- `S3_SYNC_ENABLED`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `S3_BUCKET_NAME`
- `ENABLE_ADMIN_SQL`
- `ENABLE_GENERIC_DATA_ADMIN`

## Auth Contract

JWT verification order:
1. RS256/ES256 → verify via Supabase JWKS
2. HS256 + `SUPABASE_JWT_SECRET` → verify locally
3. HS256, no secret → verify remotely via `/auth/v1/user`

`user_id` always comes from JWT — never from request body or query params.

## RBAC

`require_role(minimum_role)` enforces role hierarchy: `user < admin < superuser`.

## File Map

```
app/
  main.py           — app setup, CORS, lifespan, router registration
  auth.py           — JWT verification
  db.py             — asyncpg pool, schema snapshot, migrations, raw SQL
  dependencies.py   — shared dependencies and role checks
  routes/
    auth.py         — auth endpoints
    entries.py      — user-scoped entry CRUD
    users.py        — /users/me
    admin.py        — admin and superuser APIs
    schema.py       — schema snapshot, migrations, SQL console
  models/
    auth.py
    entry.py
    admin.py
    schema.py
migrations/
  0001_create_entries.sql
  0002_create_user_roles.sql
  0003_create_sql_audit_log.sql
```

## Planned Phases

- Phase 2: Deployment-managed S3 backup on save, plus better operator visibility
- Phase 3: S3 event trigger to Lambda and Bedrock Knowledge Base sync
- Phase 4: In-app natural language query over journal entries
- Phase 5: Sentiment detection with AWS Comprehend to auto-set entry theme
