import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from config import settings
from ldap_auth import ldap_manager

logger = logging.getLogger(__name__)
security = HTTPBearer()

# ──────────────────────────────
# Token creation
# ──────────────────────────────
def generate_access_token(user_data: dict) -> str:
    """Generate JWT access token"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": user_data["username"],
        "username": user_data["username"],
        "email": user_data.get("email"),
        "groups": user_data.get("groups", []),
        "is_admin": user_data.get("is_admin", False),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


# ──────────────────────────────
# Token verification
# ──────────────────────────────
def verify_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        username = payload.get("sub")
        if not username:
            return None

        return payload

    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


# ──────────────────────────────
# Current user dependency
# ──────────────────────────────
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    token_data = verify_access_token(token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 🔐 Re-validate user from LDAP (important!)
    user = ldap_manager.get_user_details(token_data["username"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    return user


# ──────────────────────────────
# Admin-only dependency
# ──────────────────────────────
async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
