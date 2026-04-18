# Lumen Backend — Claude Context

## Current State (as of 2026-04-18)
Phase 1 scaffold complete. Standalone FastAPI service with full entry CRUD and JWT auth.
Not yet wired to the frontend — that comes in Phase 2.

### Built Files
```
app/
  main.py         — FastAPI app, CORS (localhost:3000), router mount, /health
  auth.py         — get_current_user dependency (PyJWT, HS256)
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

## Planned File Structure
```
project-lumen-source/
  app/
    main.py           # FastAPI app init, CORS, router registration
  auth.py           # JWT verification dependency
    routes/
      entries.py      # CRUD for journal entries
    models/
      entry.py        # Pydantic request/response models
  Dockerfile
  requirements.txt
  .env
```

## Auth Pattern
Every protected route uses a FastAPI dependency that:
1. Extracts the `Authorization: Bearer <token>` header
2. Verifies the JWT with PyJWT
3. Uses Supabase JWKS (`/auth/v1/.well-known/jwks.json`) for modern asymmetric signing keys
4. Falls back to `SUPABASE_JWT_SECRET` only for legacy HS256 setups
5. For HS256 projects without the shared secret, verifies the token with `GET /auth/v1/user` using the public API key

```python
from fastapi import Depends, HTTPException, Header
import jwt

def get_current_user(authorization: str = Header(...)):
    ...
```

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
