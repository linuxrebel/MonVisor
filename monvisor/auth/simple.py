"""
monvisor/auth/simple.py
bcrypt-based auth provider — the default for free tier.
Stores hashed password and sessions in SQLite.
"""

import uuid
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from monvisor.auth.base import AuthProvider
from monvisor.db import queries


SESSION_TTL_HOURS = 12


class SimpleAuthProvider(AuthProvider):

    def authenticate(self, username: str, password: str) -> Optional[str]:
        if username != "admin":
            return None

        stored_hash = queries.get_setting("auth_password_hash")
        if not stored_hash:
            return None

        if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            return None

        # Create session
        token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
        queries.create_session(token, expires_at)
        return token

    def validate_token(self, token: str) -> bool:
        return queries.validate_session(token)

    def logout(self, token: str) -> None:
        queries.delete_session(token)

    @staticmethod
    def set_password(password: str):
        """Hash and store the admin password. Called during monvisor init."""
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        queries.set_setting("auth_password_hash", hashed)

    @staticmethod
    def is_configured() -> bool:
        """Returns True if a password has been set."""
        return queries.get_setting("auth_password_hash") is not None
