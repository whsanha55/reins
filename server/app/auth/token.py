# auth/token.py — API token 인증(Bearer). REINS_API_TOKEN 미설정 시 스킵(로컬 개발 편의).
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer = HTTPBearer(auto_error=False)


async def require_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    # 미설정 → 인증 무력화(로컬). 운영에선 강한 난수 필수.
    if not settings.REINS_API_TOKEN:
        return "dev"
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    if creds.credentials != settings.REINS_API_TOKEN:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    return creds.credentials
