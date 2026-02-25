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

from typing import TYPE_CHECKING, Any, Final

from fastmcp import FastMCP

from .auth import AuthCredentialResolver
from .credentials import CredentialResolver
from .execution import run_browser_task

if TYPE_CHECKING:
    from aden_tools.credentials import CredentialStoreAdapter

import logging

logger = logging.getLogger(__name__)

MAX_STEPS_MIN: Final[int] = 1
MAX_STEPS_MAX: Final[int] = 50

TIMEOUT_MIN_MS: Final[int] = 5_000
TIMEOUT_MAX_MS: Final[int] = 300_000

DEFAULT_MAX_STEPS: Final[int] = 15
DEFAULT_TIMEOUT_MS: Final[int] = 300_000
DEFAULT_AUTH_MAX_STEPS: Final[int] = 20
DEFAULT_AUTH_TIMEOUT_MS: Final[int] = 90_000
DEFAULT_VISION_TIMEOUT_MS: Final[int] = 120_000


# TOOL REGISTRATION
def register_tools(
    mcp: FastMCP,
    credentials: "CredentialStoreAdapter | None" = None,
) -> None:
    """
    Register browser automation tools with the MCP server.

    Args:
        mcp: FastMCP instance
        credentials: CredentialStoreAdapter instance, or None

    Notes:
        - Register tools with FastMCP server
        - Supports both browser automation and vision tasks
        - Validates input and resolves credentials
    """
    credential_resolver = CredentialResolver(credentials)
    auth_resolver = AuthCredentialResolver(credentials)

    # ─────────────────────────────────────────
    # INTERNAL EXECUTION
    # ─────────────────────────────────────────

    def _execute_browser_task(
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
        Internal execution pipeline for browser automation tasks.

        Validates input and resolves credentials before executing the task.

        Returns a structured result dictionary with keys:

            - success (bool)
            - status (str)
            - error (str | None)

        Status types:
            - configuration_error
            - timeout
            - security_blocked
            - execution_error

        Args:
            task (str): Natural language instruction
            allowed_domains (list[str] | None): Optional allowlist
            max_steps (int): Maximum number of steps to execute
            timeout_ms (int): Timeout in milliseconds
            headless (bool): Disable GUI
            provider (str | None): LLM provider override
            model (str | None): Model override
            use_vision (bool): Enable vision mode
            api_key (str | None): Explicit API key override

        Returns:
            dict: Structured result dictionary
        """
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

        try:
            provider, model = credential_resolver.resolve_provider_and_model(
                provider=provider,
                model=model,
                use_vision=use_vision,
            )

            api_key = credential_resolver.resolve_api_key(
                provider=provider,
                explicit_key=api_key,
            )

        except ValueError as e:
            logger.info("Browser task configuration error")

            return {
                "success": False,
                "status": "configuration_error",
                "error": str(e),
                "help": (
                    "Provide provider and model explicitly, or configure "
                    "an API key via environment variable or credential store."
                ),
            }

        # ── Execute browser task ────────────

        return run_browser_task(
            task=task,
            allowed_domains=allowed_domains,
            max_steps=max_steps,
            timeout_ms=timeout_ms,
            headless=headless,
            use_vision=use_vision,
            provider=provider,
            model=model,
            api_key=api_key,
        )

    @mcp.tool()
    def browser_use_task(
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
        General natural-language browsing.

        Args:
            task: Natural language instruction.
            allowed_domains: Optional allowlist of domains.
            max_steps: Maximum steps to execute (1-50).
            timeout_ms: Maximum timeout in milliseconds (5000-300000).
            headless: Whether to run the browser headlessly.
            provider: Optional LLM provider.
            model: Optional model name to use.
            use_vision: Whether to use vision capabilities.
            api_key: Optional API key to use.

        Returns:
            Structured result dictionary with keys:

            On Success:
                {
                    "success": True,
                    "task": str,
                    "result": str,
                    "steps_taken": int,
                    "max_steps": int,
                    "execution_time_ms": int,
                    "model_used": str,
                    "provider_used": str,
                    "vision_enabled": bool,
                }

            On Failure:
                {
                    "success": False,
                    "error": str,
                    "status": str,
                    "execution_time_ms": int,
                }

        Status Types:
            - timeout
            - security_blocked
            - configuration_error
            - execution_error
        """
        return _execute_browser_task(
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

    @mcp.tool()
    def browser_use_auth_task(
        task: str,
        credential_ref: str | None = None,
        explicit_credentials: dict[str, Any] | None = None,
        allowed_domains: list[str] | None = None,
        max_steps: int = DEFAULT_AUTH_MAX_STEPS,
        timeout_ms: int = DEFAULT_AUTH_TIMEOUT_MS,
        headless: bool = True,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> dict:

        """
        Execute a browser automation task with authentication.

        This function:

            - Resolves credentials using the provided credential_ref or explicit_credentials
            - Injects resolved credentials into the task
            - Executes the task with the injected credentials

        Args:
            task:
                Natural language instruction
            credential_ref:
                Optional credential reference for the task
            explicit_credentials:
                Optional explicit credentials to be injected into the task
            allowed_domains:
                Optional allowlist of domains
            max_steps:
                Maximum number of steps to execute
            timeout_ms:
                Timeout in milliseconds
            headless:
                Disable GUI
            provider:
                Optional provider override
            model:
                Optional model override
            api_key:
                Optional API key override

        Returns:

            Structured result dictionary with keys:
                - success (bool)
                - status (str)
                - error (str | None)
                - execution_time_ms (int)
        """
        if credential_ref and explicit_credentials:
            return {
                "success": False,
                "error": "Provide either credential_ref OR explicit_credentials, not both.",
            }

        creds = auth_resolver.resolve_credentials(
            credential_ref=credential_ref,
            explicit_credentials=explicit_credentials,
        )

        if creds is None:
            logger.info("browser_use_auth_task: no credentials provided")
            return {
                "success": False,
                "status": "configuration_error",
                "error": "No credentials provided.",
                "help": (
                    "Provide either a valid credential_ref pointing to a stored "
                    "credential or explicit_credentials dictionary."
                ),
            }


        final_task = auth_resolver.inject_credentials_into_task(
            task=task,
            credential_data=creds,
        )

        # Clear memory reference
        creds = None

        return _execute_browser_task(
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
    def browser_use_vision_task(
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
        Execute a browser automation task with vision capabilities.

        This function:
            - Enables vision mode, selecting a model that supports vision capabilities
            - Executes the task with the selected model

        Args:
            task:
                Natural language instruction
            allowed_domains:
                Optional allowlist of domains
            max_steps:
                Maximum number of steps to execute
            timeout_ms:
                Timeout in milliseconds
            headless:
                Disable GUI
            provider:
                Optional provider override
            model:
                Optional model override
            api_key:
                Optional API key override

        Returns:
            Structured result dictionary with keys:

                - success (bool)
                - status (str)
                - error (str | None)
                - execution_time_ms (int)
        """
        return _execute_browser_task(
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

