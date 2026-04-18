# Lumen Backend — Codex Agent Context

## What This Project Is
FastAPI backend for the Lumen journaling PWA. Runs in Docker (lumen-api, port 8000).
Phase 1 complete: entry CRUD, JWT auth, RBAC, admin API, schema introspection, migrations, raw SQL.
Not yet wired to the frontend (Phase 2).

## Stack
- Python 3.11, FastAPI 0.115, Pydantic v2, supabase-py 2.28, PyJWT, asyncpg 0.29
- Supabase async client — all application queries
- asyncpg pool — migrations, schema introspection, raw SQL execution
- No ORM anywhere. No TypeScript. No local installs — Docker only.

## File Map
- `app/main.py` — lifespan (Supabase client + asyncpg pool + schema snapshot), CORS, router registration
- `app/auth.py` — `get_current_user` via HTTPBearer; JWKS primary, HS256 fallbacks
- `app/db.py` — asyncpg pool factory, schema snapshot, migration helpers, SQL execution
- `app/dependencies.py` — `get_supabase`, `get_db_pool`, `require_role(minimum_role)`
- `app/routes/entries.py` — user-scoped entry CRUD (`/entries`)
- `app/routes/users.py` — `GET /users/me`
- `app/routes/admin.py` — admin stats, user management, cross-user entry access
- `app/routes/schema.py` — schema snapshot, migrations, raw SQL (`/admin/schema/*`, `/admin/sql`)
- `app/models/entry.py` — EntryCreate, EntryUpdate, EntryResponse, EntryListResponse
- `app/models/admin.py` — RoleUpdate, UserSummary, AdminStats
- `app/models/schema.py` — SchemaSnapshot, MigrationRecord, SQLRequest, SQLResponse
- `migrations/` — numbered `.sql` files applied in order via the migrations endpoint

## Auth Pattern
`get_current_user` uses `HTTPBearer` (shows lock icon in Swagger UI).

Resolution order:
1. Extract Bearer token
2. Peek at `alg` header (unsigned)
3. Asymmetric → verify via JWKS (`SUPABASE_URL/auth/v1/.well-known/jwks.json`)
4. HS256 + `SUPABASE_JWT_SECRET` → verify locally
5. HS256, no secret → verify remotely via `/auth/v1/user` with `SUPABASE_PUBLISHABLE_KEY`

Returns `user_id` (JWT `sub`). Never trusts user_id from request body.

## RBAC
`require_role(minimum_role)` checks `user_roles` table. Hierarchy: `user(1) < admin(2) < superuser(3)`.
Returns caller `user_id` on pass. Raises 403 on fail.

## API Endpoints
| Method | Path                              | Min role   |
|--------|-----------------------------------|------------|
| POST   | /entries                          | user       |
| GET    | /entries                          | user       |
| GET    | /entries/{id}                     | user       |
| PATCH  | /entries/{id}                     | user       |
| DELETE | /entries/{id}                     | user       |
| GET    | /users/me                         | user       |
| GET    | /admin/stats                      | admin      |
| GET    | /admin/users                      | admin      |
| GET    | /admin/users/{id}                 | admin      |
| PATCH  | /admin/users/{id}/role            | superuser  |
| DELETE | /admin/users/{id}                 | superuser  |
| GET    | /admin/entries                    | superuser  |
| DELETE | /admin/entries/{id}               | superuser  |
| GET    | /admin/schema                     | admin      |
| POST   | /admin/schema/refresh             | admin      |
| GET    | /admin/schema/migrations          | admin      |
| POST   | /admin/schema/migrations/apply    | superuser  |
| POST   | /admin/sql                        | superuser  |
| GET    | /health                           | none       |

## Environment Variables
Required:
- `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_PUBLISHABLE_KEY`
- `DATABASE_URL` — asyncpg Postgres connection string; URL-encode special chars in password

Optional/legacy: `SUPABASE_JWKS_URL`, `SUPABASE_JWT_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY`

## Bootstrap (first-time setup)
Run migration SQL files directly in Supabase SQL Editor, then insert superuser row:
```sql
INSERT INTO user_roles (user_id, role) VALUES ('<your-user-id>', 'superuser');
```
After bootstrap, use `POST /admin/schema/migrations/apply` to track them going forward.

## Strict Rules
- No ORM — Supabase client or asyncpg only
- No hardcoded secrets
- `user_id` always from JWT, never from request body
- Return 404 (not 403) for owned-resource-not-found
- Return 401 for missing/invalid JWT
- CORS: allow `http://localhost:3000`

## Out of Scope (do not implement unless asked)
- Phase 2: frontend wiring
- Phase 3: S3 uploads
- Phase 4: Lambda / Bedrock
- Phase 5: AWS Comprehend sentiment
