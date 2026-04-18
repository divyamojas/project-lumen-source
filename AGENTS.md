# Lumen Backend — Codex Agent Context

## What This Project Is
FastAPI backend for the Lumen journaling PWA. Runs in Docker (lumen-api, port 8000).
Connects to Supabase (Postgres + Auth). Verifies Supabase JWTs locally via PyJWT.
Phase 1 scaffold is complete. Not yet wired to the frontend.

## Stack
- Python 3.11, FastAPI, Supabase Python client, PyJWT, Pydantic v2
- No ORM — Supabase client only
- No TypeScript — Python only

## File Responsibilities
- `app/main.py` → app init, CORS, router registration, /health
- `app/auth.py` → `get_current_user` dependency: extracts + verifies JWT, returns user_id
- `app/routes/entries.py` → full CRUD for /entries
- `app/models/entry.py` → EntryCreate, EntryUpdate, EntryResponse Pydantic models

## Auth Pattern
Every protected route uses `get_current_user = Depends(get_current_user)`.
`user_id` is always taken from the verified JWT payload (`sub` claim) — never from the request body.

## Strict Rules
- No ORM — use Supabase Python client directly
- No hardcoded secrets — all config from environment variables
- `user_id` always from JWT, never from request body
- Return 404 (not 403) when a user's own resource is not found — prevents user enumeration
- Return 401 for missing or invalid JWT
- CORS: allow `http://localhost:3000` in dev

## Entry Schema
Matches the shared contract in the root CLAUDE.md. Key fields:
`id, title, body, createdAt, updatedAt, accentColor, theme, tags, favorite, pinned,
collection, checklist, templateId, promptId, relatedEntryIds`
`user_id` is stored in the DB row but comes from the JWT, not the request.

## API Endpoints
| Method | Path            | Auth required |
|--------|-----------------|---------------|
| POST   | /entries        | yes           |
| GET    | /entries        | yes           |
| GET    | /entries/{id}   | yes           |
| PATCH  | /entries/{id}   | yes           |
| DELETE | /entries/{id}   | yes           |
| GET    | /health         | no            |

## Environment Variables (from .env)
- SUPABASE_URL
- SUPABASE_SECRET_KEY  — secret/service-role key, not publishable; bypasses RLS
- SUPABASE_JWT_SECRET

## Permanently Out of Scope (Phase 1)
- Frontend wiring (Phase 2)
- S3 uploads (Phase 3)
- Lambda / Bedrock (Phase 4)
- AWS Comprehend sentiment (Phase 5)
Do not implement future phases unless explicitly asked.
