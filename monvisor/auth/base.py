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
