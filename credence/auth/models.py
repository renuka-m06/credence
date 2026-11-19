"""Data models for authentication and access control."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    role: str = Field("reviewer", description="Role: 'admin', 'reviewer', or 'viewer'")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserPublic(UserBase):
    id: str
    is_active: bool = True
    created_at: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


class TokenPayload(BaseModel):
    sub: str  # User ID or username
    role: str = "reviewer"
    exp: Optional[int] = None
