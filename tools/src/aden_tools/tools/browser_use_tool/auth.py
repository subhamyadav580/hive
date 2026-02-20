"""
Authentication credential resolution for browser automation.

Handles:
- Secure credential reference lookup
- Explicit username/password fallback
- Safe injection into task strings

Security:
- Does not log credentials
- Does not cache credentials
- Returns None if resolution fails
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aden_tools.credentials.auth_store import AuthCredentialStore


class AuthCredentialResolver:
    """
    Resolves authentication credentials for browser tasks.

    Resolution Priority:
        1. credential_ref (secure store)
        2. explicit username/password (fallback)

    Notes:
        - Does NOT persist credentials
        - Does NOT log credentials
        - Returns None if incomplete
    """

    def __init__(self, auth_store: AuthCredentialStore | None = None):
        self._auth_store = auth_store

    # ─────────────────────────────────────────
    # RESOLUTION
    # ─────────────────────────────────────────

    def resolve_credentials(
        self,
        credential_ref: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> tuple[str, str] | None:
        """
        Resolve authentication credentials.

        Returns:
            (username, password) or None

        Security Rules:
            - Empty username/password are treated as invalid
            - Partial credentials are rejected
        """

        # 1️⃣ Secure credential reference
        if credential_ref:
            if not self._auth_store:
                return None

            creds = self._auth_store.get_auth_credential(credential_ref)
            if not creds:
                return None

            resolved_username = creds.get("username")
            resolved_password = creds.get("password")

            if resolved_username and resolved_password:
                return resolved_username, resolved_password

            # Incomplete stored credentials are rejected
            return None

        # 2️⃣ Explicit credentials fallback
        if username and password:
            return username, password

        # Reject partial credentials
        return None

    # ─────────────────────────────────────────
    # INJECTION
    # ─────────────────────────────────────────

    def inject_credentials_into_task(
        self,
        task: str,
        username: str,
        password: str,
    ) -> str:
        """
        Inject credentials into task placeholders.

        Supported placeholders:
            {username}
            {password}

        If placeholders do not exist, task is returned unchanged.

        Important:
            - Does not modify task if no placeholders present
            - Does not partially inject
        """

        if not task:
            return task

        result = task

        if "{username}" in result:
            result = result.replace("{username}", username)

        if "{password}" in result:
            result = result.replace("{password}", password)

        return result
