"""Authentication endpoints.

POST /auth/register  — create a new user account
POST /auth/login     — authenticate and receive a JWT
POST /auth/token     — OAuth2 password-form endpoint (for Swagger UI)
GET  /auth/me        — return current user info (includes model + api_key)
PUT  /auth/me        — update model and api_key for current user
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from surogate_agent.auth.database import get_db
from surogate_agent.auth.jwt import create_access_token, get_current_user
from surogate_agent.auth.models import User
from surogate_agent.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserSettingsUpdate,
)
from surogate_agent.auth.service import (
    authenticate_user,
    create_user,
    get_user_by_email,
    get_user_by_username,
    update_user_settings,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """Register a new user and return their profile."""
    if get_user_by_username(db, req.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken.",
        )
    if get_user_by_email(db, req.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )
    return create_user(db, req)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate with JSON body and return a JWT access token."""
    user = authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.username, user.role))


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password-form endpoint used by Swagger UI's Authorize button."""
    user = authenticate_user(db, form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.username, user.role))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user's profile, including LLM settings."""
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(
    body: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Update the current user's model and API key."""
    return update_user_settings(db, current_user, body.model, body.api_key)
