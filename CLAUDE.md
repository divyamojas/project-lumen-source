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
- PyJWT — verifies Supabase-issued JWTs locally (no round-trip to Supabase on every request)

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
2. Verifies the JWT using `SUPABASE_JWT_SECRET` via PyJWT
3. Returns the decoded payload — `user_id` is read from there

```python
from fastapi import Depends, HTTPException, Header
import jwt

def get_current_user(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]  # this is user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Supabase Usage
- Use the Supabase Python client directly — no ORM, no SQLAlchemy.
- All queries are scoped to the authenticated `user_id` extracted from the JWT.
- Never trust a `user_id` from the request body.

## Response Rules
- Return 404 (not 403) when a user's own resource is not found — prevents user enumeration.
- Return 401 for missing or invalid JWT.

## Backend-Specific Rules
- No ORM — Supabase client only.
- Pydantic models for all request bodies and responses.
- CORS must allow the frontend origin (`http://localhost:3000` in dev).
- All config (URLs, secrets) from environment variables — never hardcoded.
