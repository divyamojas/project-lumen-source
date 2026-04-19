import asyncio
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request as FastAPIRequest, Response, status
from supabase import AsyncClient

from app.dependencies import get_supabase
from app.models.auth import (
    AuthLoginRequest,
    AuthSignupRequest,
    AuthUrlResponse,
    PasswordResetRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv(
    "SUPABASE_ANON_KEY"
)
DEFAULT_RESET_REDIRECT_TO = os.getenv("PASSWORD_RESET_REDIRECT_TO")


def _require_auth_env() -> tuple[str, str]:
    if not SUPABASE_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_URL is not configured",
        )
    if not SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_PUBLISHABLE_KEY is not configured",
        )
    return SUPABASE_URL.rstrip("/"), SUPABASE_PUBLISHABLE_KEY


def _normalize_supabase_auth_error(status_code: int, details: dict | None) -> HTTPException:
    details = details or {}

    raw_detail = details.get("detail")
    if isinstance(raw_detail, dict):
        code = raw_detail.get("error_code") or raw_detail.get("code")
        message = raw_detail.get("msg") or raw_detail.get("message") or "Supabase Auth request failed"
    else:
        code = details.get("error_code") or details.get("code")
        message = raw_detail or details.get("msg") or details.get("message") or "Supabase Auth request failed"

    if code == "over_email_send_rate_limit":
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "over_email_send_rate_limit",
                "message": "Supabase email rate limit reached. Wait a bit before trying again.",
                "retryable": True,
                "provider": "supabase-auth",
            },
        )

    return HTTPException(
        status_code=status_code,
        detail={
            "code": code or "supabase_auth_error",
            "message": message,
            "provider": "supabase-auth",
            "retryable": status_code >= 500 or status_code == status.HTTP_429_TOO_MANY_REQUESTS,
        },
    )


def _send_supabase_request(url: str, method: str, payload: dict | None, bearer_token: str | None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "apikey": _require_auth_env()[1],
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    request = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(request, timeout=15) as response:
            response_body = response.read().decode("utf-8")
            if not response_body:
                return {}
            return json.loads(response_body)
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        details = None
        if response_body:
            try:
                details = json.loads(response_body)
            except json.JSONDecodeError:
                details = {"detail": response_body}
        raise _normalize_supabase_auth_error(exc.code, details) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Auth is unavailable",
        ) from exc


async def _supabase_auth_request(
    path: str,
    method: str = "POST",
    payload: dict | None = None,
    bearer_token: str | None = None,
):
    supabase_url, _ = _require_auth_env()
    url = f"{supabase_url}{path}"
    return await asyncio.to_thread(_send_supabase_request, url, method, payload, bearer_token)


@router.get("/google/start", response_model=AuthUrlResponse)
async def start_google_auth(
    redirect_to: str = Query(..., description="Frontend callback URL"),
):
    supabase_url, _ = _require_auth_env()
    query = urlencode({"provider": "google", "redirect_to": redirect_to})
    return AuthUrlResponse(url=f"{supabase_url}/auth/v1/authorize?{query}")


@router.get("/google", response_model=AuthUrlResponse)
async def start_google_auth_alias(
    redirect_to: str = Query(..., description="Frontend callback URL"),
):
    return await start_google_auth(redirect_to)


@router.get("/login/google", response_model=AuthUrlResponse)
async def start_google_login_alias(
    redirect_to: str = Query(..., description="Frontend callback URL"),
):
    return await start_google_auth(redirect_to)


@router.post("/login")
async def login_with_password(body: AuthLoginRequest):
    payload = await _supabase_auth_request(
        "/auth/v1/token?grant_type=password",
        payload=body.model_dump(),
    )
    return payload


@router.post("/sign-up")
async def sign_up(body: AuthSignupRequest, supabase: AsyncClient = Depends(get_supabase)):
    full_name = body.full_name.strip() or body.name.strip()
    signup_payload = {
        "email": body.email,
        "password": body.password,
        "data": {"full_name": full_name} if full_name else {},
    }
    payload = await _supabase_auth_request("/auth/v1/signup", payload=signup_payload)

    user = payload.get("user") or {}
    user_id = user.get("id")
    if user_id:
        await supabase.table("user_roles").upsert({"user_id": user_id, "role": "user"}).execute()

    return payload


@router.post("/signup")
async def sign_up_alias(body: AuthSignupRequest, supabase: AsyncClient = Depends(get_supabase)):
    return await sign_up(body, supabase)


@router.post("/register")
async def register_alias(body: AuthSignupRequest, supabase: AsyncClient = Depends(get_supabase)):
    return await sign_up(body, supabase)


@router.post("/reset-password", status_code=200)
async def reset_password(body: PasswordResetRequest, request: FastAPIRequest):
    redirect_to = DEFAULT_RESET_REDIRECT_TO
    if not redirect_to:
        origin = request.headers.get("origin")
        if origin:
            redirect_to = f"{origin.rstrip('/')}/auth"

    payload = {"email": body.email}
    if redirect_to:
        payload["redirect_to"] = redirect_to

    await _supabase_auth_request("/auth/v1/recover", payload=payload)
    return {"message": "Password reset email sent"}


@router.post("/password/reset", status_code=200)
async def reset_password_alias(body: PasswordResetRequest, request: FastAPIRequest):
    return await reset_password(body, request)


@router.post("/forgot-password", status_code=200)
async def forgot_password_alias(body: PasswordResetRequest, request: FastAPIRequest):
    return await reset_password(body, request)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    authorization: str | None = Header(default=None),
):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()

    if token:
        try:
            await _supabase_auth_request(
                "/auth/v1/logout",
                bearer_token=token,
                payload=None,
            )
        except HTTPException:
            # Logout is best-effort; frontend clears local auth state regardless.
            pass

    response.status_code = status.HTTP_204_NO_CONTENT
