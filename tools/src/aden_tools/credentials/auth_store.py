"""
Authentication credential storage for browser automation.

Provides:
- Namespaced credential IDs using "auth:" prefix
- Encrypted storage via CredentialStore
- Secure secret handling using Pydantic SecretStr
- Safe metadata index initialization

Security:
- Credentials encrypted at rest
- Secrets never logged
- Passwords only decrypted on explicit retrieval
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import SecretStr

if TYPE_CHECKING:
    from framework.credentials import CredentialStore

logger = logging.getLogger(__name__)

AUTH_NAMESPACE: Final[str] = "auth:"


# ─────────────────────────────────────────────
# AUTH STORE
# ─────────────────────────────────────────────

class AuthCredentialStore:
    """
    Manages website authentication credentials.

    All credentials:
    - Stored encrypted
    - Prefixed with "auth:" namespace
    - Decrypted only when explicitly retrieved

    Thread Safety:
        Not guaranteed. Use external synchronization if shared.
    """

    def __init__(self, credential_store: CredentialStore):
        self._store = credential_store
        self._ensure_index()

    # ─────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────

    def _validate_ref_id(self, ref_id: str) -> None:
        """
        Validate credential reference ID.

        Prevents accidental namespace collisions.
        """
        if not ref_id or ":" in ref_id:
            raise ValueError("Invalid ref_id. Must be non-empty and must not contain ':'.")

    def _ensure_index(self) -> None:
        """
        Ensure metadata index file exists and is well-formed.

        This is required for EncryptedFileStorage-based backends.
        """
        try:
            storage = getattr(self._store, "_storage", None)
            base_path = getattr(storage, "base_path", None)

            if not base_path:
                logger.debug("Skipping index initialization (non-file storage backend).")
                return

            index_path = Path(base_path) / "metadata" / "index.json"

            if not index_path.exists():
                index_path.parent.mkdir(parents=True, exist_ok=True)

                index_data = {
                    "credentials": {},
                    "version": "1.0",
                    "last_modified": datetime.now(UTC).isoformat(),
                }

                index_path.write_text(json.dumps(index_data, indent=2))
                logger.debug("Created credential index at %s", index_path)
                return

            # Validate structure
            try:
                index = json.loads(index_path.read_text())
            except json.JSONDecodeError:
                logger.warning("Corrupted index file detected. Reinitializing.")
                index = {}

            if "credentials" not in index:
                index["credentials"] = {}
                index_path.write_text(json.dumps(index, indent=2))
                logger.debug("Fixed missing 'credentials' key in index.")

        except Exception:
            logger.exception("Failed to ensure credential index structure.")

    def _namespaced_id(self, ref_id: str) -> str:
        return f"{AUTH_NAMESPACE}{ref_id}"

    # ─────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────

    def save_auth_credential(
        self,
        ref_id: str,
        username: str,
        password: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """
        Save authentication credentials securely.

        Args:
            ref_id: Unique identifier (no namespace prefix)
            username: Username or email
            password: Password
            metadata: Optional additional secret fields (e.g., 2FA)

        Raises:
            ValueError if ref_id invalid
        """
        from framework.credentials.models import CredentialKey, CredentialObject

        self._validate_ref_id(ref_id)

        keys = {
            "username": CredentialKey(name="username", value=SecretStr(username)),
            "password": CredentialKey(name="password", value=SecretStr(password)),
        }

        if metadata:
            for key, value in metadata.items():
                if value:  # Ignore empty metadata values
                    keys[key] = CredentialKey(key, SecretStr(value))

        credential = CredentialObject(
            id=self._namespaced_id(ref_id),
            keys=keys,
        )

        self._store.save_credential(credential)

        logger.debug("Saved auth credential '%s'", ref_id)

    def get_auth_credential(self, ref_id: str) -> dict[str, str] | None:
        """
        Retrieve decrypted authentication credentials.

        Returns:
            Dictionary of secret values or None if not found.
        """
        self._validate_ref_id(ref_id)

        credential = self._store.get_credential(self._namespaced_id(ref_id))
        if credential is None:
            return None

        result: dict[str, str] = {}

        for key_name, key_obj in credential.keys.items():
            try:
                result[key_name] = key_obj.value.get_secret_value()
            except Exception:
                logger.exception("Failed to extract secret for key '%s'", key_name)
                return None

        return result

    def list_auth_credentials(self) -> list[str]:
        """
        List all saved auth credential references.
        """
        all_ids = self._store.list_credentials()
        auth_ids = [cid for cid in all_ids if cid.startswith(AUTH_NAMESPACE)]
        return [cid.removeprefix(AUTH_NAMESPACE) for cid in auth_ids]

    def delete_auth_credential(self, ref_id: str) -> bool:
        """
        Delete auth credential.

        Returns:
            True if deleted.
        """
        self._validate_ref_id(ref_id)
        return self._store.delete_credential(self._namespaced_id(ref_id))


# ─────────────────────────────────────────────
# FACTORY
# ─────────────────────────────────────────────

def get_auth_store() -> AuthCredentialStore:
    """
    Initialize AuthCredentialStore with encrypted local storage.

    Storage Path:
        ~/.hive/credentials
    """
    from framework.credentials import CredentialStore

    base_path = Path.home() / ".hive" / "credentials"
    base_path.mkdir(parents=True, exist_ok=True)

    logger.debug("Initializing encrypted credential store at %s", base_path)

    store = CredentialStore.with_encrypted_storage(base_path=str(base_path))
    return AuthCredentialStore(store)
