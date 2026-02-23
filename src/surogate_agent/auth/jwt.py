"""JWT token creation and validation."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt as _jwt
from jwt.exceptions import InvalidTokenError as JWTError
from sqlalchemy.orm import Session

from surogate_agent.auth.database import get_db
from surogate_agent.auth.models import User
from surogate_agent.auth.service import get_user_by_username

_SECRET_KEY: str = os.getenv("SUROGATE_JWT_SECRET", "change-me-in-production")
_ALGORITHM = "HS256"
_EXPIRE_MINUTES: int = int(os.getenv("SUROGATE_ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_access_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expire}
    return _jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — decode JWT and return the corresponding User."""
    try:
        payload = _jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        username: str | None = payload.get("sub")
        if not username:
            raise _CREDENTIALS_EXC
    except JWTError:
        raise _CREDENTIALS_EXC

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXC
    return user
