"""
monvisor/auth/base.py
Abstract auth provider interface.
All auth backends implement this class.
"""

from abc import ABC, abstractmethod
from typing import Optional


class AuthProvider(ABC):

    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Verify credentials. Returns a session token string on success, None on failure.
        """

    @abstractmethod
    def validate_token(self, token: str) -> bool:
        """Returns True if the session token is valid and not expired."""

    @abstractmethod
    def logout(self, token: str) -> None:
        """Invalidate a session token."""
