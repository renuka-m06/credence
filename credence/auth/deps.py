"""FastAPI dependency injection for user authentication and role-based access control."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from credence.auth.models import UserPublic
from credence.auth.security import decode_access_token
from credence.auth.store import user_store

security_bearer = HTTPBearer(auto_error=False)

# Config flag: allow anonymous/dev mode when CREDENCE_AUTH_REQUIRED is false
AUTH_REQUIRED = os.getenv("CREDENCE_AUTH_REQUIRED", "false").lower() in ("true", "1", "yes")


async def get_current_user_optional(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> Optional[UserPublic]:
    """Retrieve authenticated user if bearer token is present, else None."""
    if not auth or not auth.credentials:
        return None

    payload = decode_access_token(auth.credentials)
    if not payload:
        return None

    username = payload.get("sub") or payload.get("username")
    if not username:
        return None

    user_dict = user_store.get_by_username(username)
    if not user_dict or not user_dict.get("is_active"):
        return None

    return UserPublic(
        id=user_dict["id"],
        username=user_dict["username"],
        email=user_dict.get("email"),
        role=user_dict.get("role", "reviewer"),
        is_active=user_dict.get("is_active", True),
        created_at=str(user_dict.get("created_at")),
    )


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> UserPublic:
    """Require valid authenticated user."""
    user = await get_current_user_optional(auth)
    if user:
        return user

    if not AUTH_REQUIRED:
        # Development fallback: synthesize verified reviewer identity
        return UserPublic(
            id="user-reviewer-1",
            username="reviewer-1",
            email="reviewer1@credence.local",
            role="reviewer",
            is_active=True,
            created_at="2026-01-01T00:00:00Z",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide a valid Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_reviewer(
    user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """Enforce reviewer or admin role."""
    if user.role not in ("reviewer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: user role '{user.role}' lacks reviewer privileges.",
        )
    return user


async def require_admin(
    user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """Enforce admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: administrative privileges required.",
        )
    return user
