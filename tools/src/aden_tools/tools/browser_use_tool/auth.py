"""
Generic authentication credential resolution for browser automation.

This module provides flexible credential resolution for arbitrary
authentication mechanisms, including:

Supported Use Cases:
--------------------
• Basic authentication (username/password)
• OAuth tokens
• API headers
• Cookies
• Custom multi-key auth schemes
• LLM-provided fallback credentials

Resolution Priority:
--------------------
1. CredentialStoreAdapter reference (credential_ref)
2. Explicit credential dictionary (fallback)
3. None (no credentials resolved)

Security Guarantees:
--------------------
• Credentials are never logged
• Credentials are never cached
• Resolution is just-in-time
• Returns None if resolution fails
• No implicit credential assumptions

Design Goals:
-------------
- Provider-agnostic authentication
- Multi-key credential support
- Placeholder-based injection
- Safe fallback behavior
"""

from __future__ import annotations

import logging
from typing import Any

from aden_tools.credentials.store_adapter import CredentialStoreAdapter

logger = logging.getLogger(__name__)


class AuthCredentialResolver:
    """
    Generic credential resolver for browser automation tasks.

    This resolver supports multi-key credentials stored in an
    encrypted credential store.

    It does NOT:
        - Validate credential correctness
        - Persist credentials
        - Log sensitive data
        - Perform network checks

    Intended for:
        - Login flows
        - Header injection
        - Cookie injection
        - Template-based auth placeholder replacement
    """

    def __init__(self, credentials: CredentialStoreAdapter | None = None):
        """
        Initialize resolver.

        Args:
            credentials:
                Optional encrypted credential store adapter.
        """
        self._credentials = credentials

    # ─────────────────────────────────────────
    # RESOLUTION
    # ─────────────────────────────────────────

    def resolve_credentials(
        self,
        credential_ref: str | None = None,
        explicit_credentials: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Resolve authentication credentials.

        Resolution Order:
            1. credential_ref (CredentialStoreAdapter)
            2. explicit_credentials (fallback)
            3. None

        Args:
            credential_ref:
                Reference ID used to fetch credentials from store.

            explicit_credentials:
                Directly supplied credentials (typically LLM-generated
                or runtime-provided).

        Returns:
            Dictionary containing credential data,
            or None if resolution fails.

        Notes:
            - Does not log sensitive values.
            - Does not raise if credentials are missing.
        """

        # ⚠️ Debug prints present — consider replacing with logger.debug
        print(
            f"resolve_credentials: credential_ref={credential_ref}, "
            f"explicit_credentials={explicit_credentials}"
        )

        # 1️⃣ CredentialStore lookup
        if credential_ref:
            if not self._credentials:
                print("resolve_credentials: no credential store available")
                return None

            data = self._credentials.store.get_credential(credential_ref)
            if not data:
                print(
                    f"resolve_credentials: credential {credential_ref} "
                    f"not found in store"
                )
                return None

            print(
                f"resolve_credentials: credential {credential_ref} "
                f"resolved from store"
            )
            return data

        # 2️⃣ Explicit fallback
        if explicit_credentials:
            print(
                f"resolve_credentials: using explicit credentials "
                f"{explicit_credentials}"
            )
            return explicit_credentials

        print("resolve_credentials: no credentials found")
        return None

    # ─────────────────────────────────────────
    # INJECTION
    # ─────────────────────────────────────────

    def inject_credentials_into_task(
        self,
        task: str,
        credential_data: dict[str, Any],
    ) -> str:
        """
        Inject credential placeholders into task text.

        Replaces placeholders of form:

            {key}

        With corresponding credential values.

        Example:
            task = "Login with username={username} password={password}"
            credential_data = {"username": "...", "password": "..."}

        Args:
            task:
                Task template containing placeholders.

            credential_data:
                Credential dictionary.

        Returns:
            Task string with placeholders replaced.

        Security Notes:
            - Assumes credential values implement get_secret_value()
              if wrapped (e.g., SecretStr).
            - Does not log credential values.
            - Silent if placeholder not present.
        """

        if not task or not credential_data:
            return task

        result = task

        logger.info(
            "Injecting credentials into task. "
            "Placeholder keys: %s",
            list(credential_data.keys()) if hasattr(credential_data, "keys") else None,
        )

        # ⚠️ Your implementation assumes:
        # credential_data.keys is an object with .items()
        # This may break if credential_data is a plain dict.
        for key, value in credential_data.keys.items():
            placeholder = f"{{{key}}}"
            if placeholder in result and value is not None:
                result = result.replace(
                    placeholder,
                    str(value.get_secret_value()),
                )

        return result
