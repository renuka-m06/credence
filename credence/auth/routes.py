"""Authentication API endpoints for login, user registration, and profile retrieval."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from credence.auth.deps import get_current_user
from credence.auth.models import Token, UserCreate, UserLogin, UserPublic
from credence.auth.security import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, verify_password
from credence.auth.store import user_store

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate) -> Any:
    """Register a new reviewer or user account."""
    existing = user_store.get_by_username(payload.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' is already registered.",
        )

    # Allowed roles on registration are reviewer or viewer
    role = "reviewer" if payload.role != "viewer" else "viewer"
    user_data = user_store.create_user(
        username=payload.username,
        password=payload.password,
        email=payload.email,
        role=role,
    )

    user_public = UserPublic(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data.get("email"),
        role=user_data["role"],
        is_active=user_data["is_active"],
        created_at=user_data["created_at"],
    )

    access_token = create_access_token(
        data={"sub": user_public.username, "role": user_public.role, "uid": user_public.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_public,
    )


@router.post("/login", response_model=Token)
def login(payload: UserLogin) -> Any:
    """Authenticate with username and password to obtain JWT access token."""
    user_data = user_store.get_by_username(payload.username)
    if not user_data or not verify_password(payload.password, user_data["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_data.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    user_public = UserPublic(
        id=user_data["id"],
        username=user_data["username"],
        email=user_data.get("email"),
        role=user_data["role"],
        is_active=user_data["is_active"],
        created_at=str(user_data["created_at"]),
    )

    access_token = create_access_token(
        data={"sub": user_public.username, "role": user_public.role, "uid": user_public.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_public,
    )


@router.get("/me", response_model=UserPublic)
def get_current_user_profile(user: UserPublic = Depends(get_current_user)) -> Any:
    """Retrieve details of currently authenticated reviewer."""
    return user
