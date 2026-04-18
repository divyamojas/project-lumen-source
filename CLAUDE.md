# Lumen Backend — Claude Context

## Current State (as of 2026-04-18)
Phase 1 scaffold complete. Standalone FastAPI service with full entry CRUD and JWT auth.
Not yet wired to the frontend — that comes in Phase 2.

### Built Files
```
app/
  main.py         — FastAPI app, CORS (localhost:3000), router mount, /health
  auth.py         — get_current_user dependency (JWKS primary, HS256 fallback)
  routes/
    entries.py    — POST/GET/GET{id}/PATCH{id}/DELETE{id} /entries
  models/
    entry.py      — EntryCreate, EntryUpdate, EntryResponse (Pydantic)
Dockerfile        — python:3.11-slim, uvicorn --reload
requirements.txt  — fastapi, uvicorn, supabase, PyJWT, python-dotenv, pydantic
.env.example      — template for required env vars
```

## Stack
- Python 3.11
- FastAPI
- Supabase (Postgres + Auth)
- PyJWT — verifies Supabase-issued JWTs using JWKS for modern signing keys, with legacy HS256 compatibility

## Auth Pattern
Every protected route uses `Depends(get_current_user)` from `app/auth.py`.

Resolution order:
1. Read `Authorization: Bearer <token>` header
2. Peek at the token's `alg` header (no signature check yet)
3. If asymmetric (RS256/ES256): verify via Supabase JWKS — `SUPABASE_URL/auth/v1/.well-known/jwks.json` (or `SUPABASE_JWKS_URL` override)
4. If HS256 + `SUPABASE_JWT_SECRET` set: verify locally with shared secret
5. If HS256 + no secret: verify remotely via `GET /auth/v1/user` using `SUPABASE_PUBLISHABLE_KEY`

Returns `user_id` (the JWT `sub` claim) on success, raises `401` on failure.

## Supabase Usage
- Use the Supabase Python client directly — no ORM, no SQLAlchemy.
- All queries are scoped to the authenticated `user_id` extracted from the JWT.
- Never trust a `user_id` from the request body.
- Prefer hosted `sb_secret_...` keys on the backend. Legacy `service_role` keys are supported only as a compatibility fallback.

## Response Rules
- Return 404 (not 403) when a user's own resource is not found — prevents user enumeration.
- Return 401 for missing or invalid JWT.

## Environment Variables (from .env)
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY` — preferred hosted backend key (`sb_secret_...`), bypasses RLS
- `SUPABASE_PUBLISHABLE_KEY` — preferred public key (`sb_publishable_...`) used for HS256 fallback verification
- `SUPABASE_JWKS_URL` — optional override; defaults to `SUPABASE_URL/auth/v1/.well-known/jwks.json`
- `SUPABASE_SERVICE_ROLE_KEY` — optional legacy fallback for older JWT-based server keys
- `SUPABASE_ANON_KEY` — optional legacy fallback for older public JWT-based keys
- `SUPABASE_JWT_SECRET` — optional legacy fallback for projects still using shared-secret HS256 verification

## Supabase Notes
- Supabase now recommends publishable and secret API keys over legacy `anon` and `service_role` JWT-based keys.
- Modern Supabase Auth projects can use asymmetric signing keys, so local verification should prefer JWKS rather than a shared JWT secret.
- The Python client examples in the current docs use `SUPABASE_URL` and `SUPABASE_KEY`; this repo keeps `SUPABASE_SECRET_KEY` for clarity and maps legacy names as fallbacks.

## Backend-Specific Rules
- No ORM — Supabase client only.
- Pydantic models for all request bodies and responses.
- CORS must allow the frontend origin (`http://localhost:3000` in dev).
- All config (URLs, secrets) from environment variables — never hardcoded.
