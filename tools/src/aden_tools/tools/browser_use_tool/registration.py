"""
Browser-Use MCP tool registration.

Provides:
- Natural language browser automation
- Authenticated browsing
- Vision-enabled browsing
- Secure credential management

Security:
- Enforces input validation limits
- Prevents ambiguous credential injection
- Never logs credentials
"""

from typing import TYPE_CHECKING, Final

from fastmcp import FastMCP

from .auth import AuthCredentialResolver
from .credentials import CredentialResolver
from .execution import run_browser_task

if TYPE_CHECKING:
    from aden_tools.credentials import CredentialStoreAdapter
    from aden_tools.credentials.auth_store import AuthCredentialStore


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

MAX_STEPS_MIN: Final[int] = 1
MAX_STEPS_MAX: Final[int] = 50

TIMEOUT_MIN_MS: Final[int] = 5_000
TIMEOUT_MAX_MS: Final[int] = 300_000

DEFAULT_MAX_STEPS: Final[int] = 15
DEFAULT_TIMEOUT_MS: Final[int] = 300_000
DEFAULT_AUTH_MAX_STEPS: Final[int] = 20
DEFAULT_AUTH_TIMEOUT_MS: Final[int] = 90_000
DEFAULT_VISION_TIMEOUT_MS: Final[int] = 120_000


# ─────────────────────────────────────────────
# TOOL REGISTRATION
# ─────────────────────────────────────────────

def register_tools(
    mcp: FastMCP,
    credentials: "CredentialStoreAdapter | None" = None,
    auth_store: "AuthCredentialStore | None" = None,
) -> None:
    """
    Register Browser-Use tools with an MCP server.

    Parameters
    ----------
    mcp : FastMCP
        The MCP server instance.
    credentials : CredentialStoreAdapter | None
        Global credential resolver for LLM providers.
    auth_store : AuthCredentialStore | None
        Secure store for website login credentials.

    Notes
    -----
    - LLM provider resolution follows Hive priority rules.
    - Browser-Use does NOT manage provider state directly.
    """

    resolver = CredentialResolver(credentials)
    auth_resolver = AuthCredentialResolver(auth_store)

    # ─────────────────────────────────────────
    # INTERNAL EXECUTION
    # ─────────────────────────────────────────

    async def _execute_browser_task(
        *,
        task: str,
        allowed_domains: list[str] | None,
        max_steps: int,
        timeout_ms: int,
        headless: bool,
        provider: str | None,
        model: str | None,
        use_vision: bool,
        api_key: str | None,
    ) -> dict:
        """
        Internal execution wrapper.

        Performs:
        - Input validation
        - Provider resolution
        - API key resolution
        - Delegation to browser execution engine
        """

        # ── Validation ──────────────────────

        if not task or not task.strip():
            return {
                "success": False,
                "status": "configuration_error",
                "error": "task cannot be empty",
            }

        if not (MAX_STEPS_MIN <= max_steps <= MAX_STEPS_MAX):
            return {
                "success": False,
                "status": "configuration_error",
                "error": f"max_steps must be between {MAX_STEPS_MIN} and {MAX_STEPS_MAX}",
            }

        if not (TIMEOUT_MIN_MS <= timeout_ms <= TIMEOUT_MAX_MS):
            return {
                "success": False,
                "status": "configuration_error",
                "error": f"timeout_ms must be between {TIMEOUT_MIN_MS} and {TIMEOUT_MAX_MS}",
            }

        # ── Resolve provider + model ────────

        provider_resolved, model_resolved = resolver.resolve_provider_and_model(
            provider,
            model,
            use_vision,
        )

        # ── Resolve API key ─────────────────

        try:
            resolved_key = resolver.resolve_api_key(provider_resolved, api_key)
        except ValueError as exc:
            return {
                "success": False,
                "status": "configuration_error",
                "error": str(exc),
            }

        # ── Execute browser task ────────────

        return await run_browser_task(
            task=task,
            allowed_domains=allowed_domains,
            max_steps=max_steps,
            timeout_ms=timeout_ms,
            headless=headless,
            use_vision=use_vision,
            provider=provider_resolved,
            model=model_resolved,
            api_key=resolved_key,
        )

    # ─────────────────────────────────────────
    # PRIMARY TOOL
    # ─────────────────────────────────────────

    @mcp.tool()
    async def browser_use_task(
        task: str,
        allowed_domains: list[str] | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        headless: bool = True,
        provider: str | None = None,
        model: str | None = None,
        use_vision: bool = False,
        api_key: str | None = None,
    ) -> dict:
        """
        Execute a natural-language browser automation task.

        Security Guarantees:
        - Enforces step limits
        - Enforces timeout limits
        - Supports domain allowlisting
        - Never logs credentials

        Returns
        -------
        dict
            {
                success: bool,
                result?: str,
                error?: str,
                status?: str
            }
        """

        return await _execute_browser_task(
            task=task,
            allowed_domains=allowed_domains,
            max_steps=max_steps,
            timeout_ms=timeout_ms,
            headless=headless,
            provider=provider,
            model=model,
            use_vision=use_vision,
            api_key=api_key,
        )

    # ─────────────────────────────────────────
    # AUTH TOOL
    # ─────────────────────────────────────────

    @mcp.tool()
    async def browser_use_auth_task(
        task: str,
        credential_ref: str | None = None,
        username: str | None = None,
        password: str | None = None,
        allowed_domains: list[str] | None = None,
        max_steps: int = DEFAULT_AUTH_MAX_STEPS,
        timeout_ms: int = DEFAULT_AUTH_TIMEOUT_MS,
        headless: bool = True,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> dict:
        """
        Execute authenticated browser task.

        Preferred:
            Use credential_ref (secure reference)

        Fallback:
            Provide username/password explicitly (less secure)
        """

        if credential_ref and (username or password):
            return {
                "success": False,
                "status": "configuration_error",
                "error": "Provide either credential_ref OR username/password, not both.",
            }

        creds = auth_resolver.resolve_credentials(
            credential_ref=credential_ref,
            username=username,
            password=password,
        )

        if creds is None:
            return {
                "success": False,
                "status": "configuration_error",
                "error": "No credentials provided.",
            }

        resolved_username, resolved_password = creds

        final_task = auth_resolver.inject_credentials_into_task(
            task=task,
            username=resolved_username,
            password=resolved_password,
        )

        # Clear memory references
        resolved_username = None
        resolved_password = None

        return await _execute_browser_task(
            task=final_task,
            allowed_domains=allowed_domains,
            max_steps=max_steps,
            timeout_ms=timeout_ms,
            headless=headless,
            provider=provider,
            model=model,
            use_vision=False,
            api_key=api_key,
        )

    # ─────────────────────────────────────────
    # VISION TOOL
    # ─────────────────────────────────────────

    @mcp.tool()
    async def browser_use_vision_task(
        task: str,
        allowed_domains: list[str] | None = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        timeout_ms: int = DEFAULT_VISION_TIMEOUT_MS,
        headless: bool = True,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> dict:
        """
        Execute browser task with vision enabled.
        """

        return await _execute_browser_task(
            task=task,
            allowed_domains=allowed_domains,
            max_steps=max_steps,
            timeout_ms=timeout_ms,
            headless=headless,
            provider=provider,
            model=model,
            use_vision=True,
            api_key=api_key,
        )

    # ─────────────────────────────────────────
    # AUTH CREDENTIAL MANAGEMENT
    # ─────────────────────────────────────────

    @mcp.tool()
    def save_auth_credential(
        ref_id: str,
        username: str,
        password: str,
        two_factor_secret: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Save website login credentials securely."""

        if not auth_store:
            return {"success": False, "error": "Auth credential store not configured."}

        metadata = {}
        if two_factor_secret:
            metadata["two_factor_secret"] = two_factor_secret
        if notes:
            metadata["notes"] = notes

        try:
            auth_store.save_auth_credential(
                ref_id=ref_id,
                username=username,
                password=password,
                metadata=metadata or None,
            )
            return {"success": True, "ref_id": ref_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def list_auth_credentials() -> dict:
        """List saved auth credential references."""
        if not auth_store:
            return {"success": False, "error": "Auth credential store not configured"}

        try:
            refs = auth_store.list_auth_credentials()
            return {
                "success": True,
                "credentials": refs,
                "count": len(refs),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def delete_auth_credential(ref_id: str) -> dict:
        """Delete auth credential by reference ID."""
        if not auth_store:
            return {"success": False, "error": "Auth credential store not configured"}

        try:
            deleted = auth_store.delete_auth_credential(ref_id)
            if deleted:
                return {"success": True, "message": f"{ref_id} deleted"}
            return {"success": False, "error": f"{ref_id} not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def get_auth_credential_info(ref_id: str) -> dict:
        """Get non-sensitive info about an auth credential (e.g. for debugging)."""
        if not auth_store:
            return {"success": False, "error": "Auth credential store not configured"}

        try:
            creds = auth_store.get_auth_credential(ref_id)
            if not creds:
                return {"success": False, "error": f"{ref_id} not found"}

            info = {k: v for k, v in creds.items() if k != "password"}

            return {
                "success": True,
                "ref_id": ref_id,
                "info": info,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

