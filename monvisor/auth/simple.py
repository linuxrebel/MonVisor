# MonVisor — AI-assisted monitoring configuration for Prometheus/Grafana.
# Copyright (C) 2026 James Sparenberg
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
