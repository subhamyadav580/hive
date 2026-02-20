"""
Credential resolution for browser automation.

Implements priority-based resolution with NO implicit fallback.
Explicit configuration is required if no provider is detected.

Resolution Strategy:

API Key Priority:
    1. Explicit api_key parameter
    2. Credential store (encrypted)
    3. Environment variable

Provider/Model Priority:
    1. Explicit provider/model
    2. Credential store auto-detection
    3. Environment variable auto-detection
    4. ERROR (no silent fallback)

Security:
    - Keys resolved just-in-time
    - Never logged
    - Never cached
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from .models import (
    PROVIDER_DETECTION_ORDER,
    PROVIDER_ENV_VARS,
    get_default_model,
)

if TYPE_CHECKING:
    from aden_tools.credentials import CredentialStoreAdapter

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# RESOLVER
# ─────────────────────────────────────────────


class CredentialResolver:
    """
    Resolves LLM provider, model, and API key.

    This class enforces explicit configuration and never silently
    falls back to a default provider.
    """

    def __init__(self, credentials: CredentialStoreAdapter | None = None):
        self.credentials = credentials

        logger.debug(
            "CredentialResolver initialized (credential_store=%s)",
            "enabled" if credentials else "disabled",
        )

    # ─────────────────────────────────────────
    # API KEY RESOLUTION
    # ─────────────────────────────────────────

    def resolve_api_key(
        self,
        provider: str,
        explicit_key: str | None = None,
    ) -> str:
        """
        Resolve API key for provider.

        Raises:
            ValueError if no key found.
        """

        if not provider:
            raise ValueError("Provider must be specified for API key resolution.")

        provider_normalized = provider.lower().strip()

        # 1. Explicit key
        if explicit_key:
            logger.debug("Using explicit API key for provider '%s'", provider_normalized)
            return explicit_key

        # 2. Credential store
        if self.credentials is not None:
            try:
                key = self.credentials.get(provider_normalized)
                if key:
                    logger.debug(
                        f"API key resolved from credential store "
                        f"for {provider_normalized}"
                    )
                    return key
            except Exception:
                logger.exception("Credential store lookup failed")

        # 3. Environment variable
        env_var = PROVIDER_ENV_VARS.get(provider_normalized)
        if env_var:
            key = os.getenv(env_var)
            if key:
                logger.debug("API key resolved from environment variable '%s'", env_var)
                return key

        # No key found
        available = ", ".join(PROVIDER_ENV_VARS.keys())
        suggested_env = PROVIDER_ENV_VARS.get(
            provider_normalized,
            f"{provider_normalized.upper()}_API_KEY",
        )

        error_msg = (
            f"No API key found for provider '{provider_normalized}'.\n\n"
            f"Available providers: {available}\n\n"
            f"To configure:\n"
            f"1. export {suggested_env}=your-key\n"
            f"2. Save to credential store\n"
            f"3. Pass api_key parameter explicitly\n"
        )

        logger.error("API key resolution failed for provider '%s'", provider_normalized)
        raise ValueError(error_msg)

    # ─────────────────────────────────────────
    # PROVIDER + MODEL RESOLUTION
    # ─────────────────────────────────────────

    def resolve_provider_and_model(
        self,
        provider: str | None = None,
        model: str | None = None,
        use_vision: bool = False,
    ) -> tuple[str, str]:
        """
        Resolve provider and model.

        Raises:
            ValueError if provider cannot be determined.
        """

        # Normalize explicit provider early
        provider_normalized = provider.lower().strip() if provider else None

        # 1️⃣ Explicit provider + model
        if provider_normalized and model:
            logger.debug(
                "Using explicit provider/model (%s, %s)",
                provider_normalized,
                model,
            )
            return provider_normalized, model

        # 2️⃣ Credential store auto-detection
        if not provider_normalized and self.credentials:
            for candidate in PROVIDER_DETECTION_ORDER:
                try:
                    if self.credentials.is_available(candidate):
                        provider_normalized = candidate
                        logger.debug(
                            "Auto-detected provider '%s' from credential store",
                            candidate,
                        )
                        break
                except Exception:
                    logger.exception("Credential store availability check failed")

        # 3️⃣ Environment variable auto-detection
        if not provider_normalized:
            for candidate in PROVIDER_DETECTION_ORDER:
                env_var = PROVIDER_ENV_VARS.get(candidate)
                if env_var and os.getenv(env_var):
                    provider_normalized = candidate
                    logger.debug(
                        "Auto-detected provider '%s' from environment variable",
                        candidate,
                    )
                    break

        # 4️⃣ ERROR if still not resolved
        if not provider_normalized:
            available = ", ".join(PROVIDER_ENV_VARS.keys())
            error_msg = (
                "No LLM provider configured.\n\n"
                f"Available providers: {available}\n\n"
                "To configure:\n"
                "1. Pass provider and model explicitly\n"
                "2. Set provider API key in environment variable\n"
                "3. Save credentials to encrypted store\n"
            )
            logger.error("Provider resolution failed")
            raise ValueError(error_msg)

        # Resolve model if missing
        if not model:
            model = get_default_model(provider_normalized, use_vision)
            logger.debug(
                "Selected default model '%s' for provider '%s'",
                model,
                provider_normalized,
            )

        return provider_normalized, model
