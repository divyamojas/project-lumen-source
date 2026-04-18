import json
import os
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

bearer_scheme = HTTPBearer(auto_error=False)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_JWKS_URL = os.getenv("SUPABASE_JWKS_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv(
    "SUPABASE_ANON_KEY"
)
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _get_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorized("Missing Authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Invalid Authorization header")

    return token


@lru_cache(maxsize=1)
def _get_jwks_client() -> PyJWKClient | None:
    jwks_url = SUPABASE_JWKS_URL
    if not jwks_url and SUPABASE_URL:
        jwks_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    if not jwks_url:
        return None
    return PyJWKClient(jwks_url)


def _get_token_algorithm(token: str) -> str:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc

    algorithm = header.get("alg")
    if not algorithm:
        raise _unauthorized("Invalid token")

    return algorithm


def _decode_with_jwks(token: str, algorithm: str) -> str:
    jwks_client = _get_jwks_client()
    if not jwks_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase JWKS verification is not configured",
        )

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise _unauthorized("Invalid token")

    return user_id


def _verify_hs256_token_remotely(token: str) -> str:
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "HS256 token verification requires SUPABASE_PUBLISHABLE_KEY "
                "or SUPABASE_ANON_KEY"
            ),
        )

    request = Request(
        f"{SUPABASE_URL.rstrip('/')}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_PUBLISHABLE_KEY,
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            user = json.load(response)
    except HTTPError as exc:
        if exc.code == status.HTTP_401_UNAUTHORIZED:
            raise _unauthorized("Invalid token") from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase Auth verification failed",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Auth is unavailable",
        ) from exc

    user_id = user.get("id")
    if not user_id:
        raise _unauthorized("Invalid token")

    return user_id


def _decode_hs256_token(token: str) -> str:
    if SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except jwt.PyJWTError as exc:
            raise _unauthorized("Invalid token") from exc

        user_id = payload.get("sub")
        if not user_id:
            raise _unauthorized("Invalid token")
        return user_id

    return _verify_hs256_token_remotely(token)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if not credentials:
        raise _unauthorized("Missing Authorization header")
    token = credentials.credentials
    algorithm = _get_token_algorithm(token)

    if algorithm == "HS256":
        return _decode_hs256_token(token)

    return _decode_with_jwks(token, algorithm)
