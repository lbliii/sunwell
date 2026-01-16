"""Sample authentication module for benchmark fixtures.

This module provides example code for documentation and review tasks.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal


@dataclass(frozen=True)
class User:
    """A user in the system."""
    
    id: int
    username: str
    email: str
    role: Literal["user", "admin", "moderator"] = "user"
    created_at: datetime | None = None


@dataclass(frozen=True)
class Token:
    """Authentication token."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    refresh_token: str | None = None


async def authenticate(
    username: str,
    password: str,
    mfa_code: str | None = None,
) -> Token:
    """Authenticate a user and return a session token.
    
    Args:
        username: The user's username or email.
        password: The user's password.
        mfa_code: Optional MFA code if 2FA is enabled.
        
    Returns:
        A Token object containing the access token and metadata.
        
    Raises:
        AuthenticationError: If credentials are invalid.
        MFARequiredError: If MFA code is required but not provided.
        AccountLockedError: If the account has been locked.
    """
    # Placeholder implementation
    raise NotImplementedError("This is a fixture for benchmarking")


async def refresh_token(refresh_token: str) -> Token:
    """Refresh an expired access token.
    
    Args:
        refresh_token: The refresh token from the original authentication.
        
    Returns:
        A new Token object with fresh access token.
        
    Raises:
        InvalidTokenError: If the refresh token is invalid or expired.
    """
    raise NotImplementedError("This is a fixture for benchmarking")


async def revoke_token(access_token: str) -> bool:
    """Revoke an access token.
    
    Args:
        access_token: The token to revoke.
        
    Returns:
        True if the token was successfully revoked.
    """
    raise NotImplementedError("This is a fixture for benchmarking")


class AuthenticationError(Exception):
    """Base exception for authentication failures."""
    pass


class MFARequiredError(AuthenticationError):
    """Raised when MFA is required but not provided."""
    pass


class AccountLockedError(AuthenticationError):
    """Raised when the account is locked."""
    pass


class InvalidTokenError(Exception):
    """Raised when a token is invalid."""
    pass
