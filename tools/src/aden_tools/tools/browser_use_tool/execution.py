"""
Core browser automation execution engine.

This module orchestrates the full lifecycle of a browser automation task.

Responsibilities:
-----------------
• Security validation (SSRF + allowlist enforcement)
• LLM client creation (provider abstraction)
• Browser lifecycle management
• Agent execution with timeout control
• Structured result normalization
• Async-to-sync compatibility

Architecture Overview:
----------------------
Public Sync API
    ↓
Async Bridge (Thread-Safe)
    ↓
Async Execution Engine
    ├── Security validation
    ├── Browser setup
    ├── LLM client creation
    ├── Agent execution
    └── Structured response formatting

Design Goals:
-------------
- Deterministic execution
- Explicit failure states
- Resource cleanup guarantees
- Safe timeout handling
- Clear separation of concerns
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Any, Final

from browser_use import (
    Agent,
    Browser,
    BrowserProfile,
    ChatAnthropic,
    ChatAzureOpenAI,
    ChatGroq,
    ChatOpenAI,
)

from .security import SecurityError, validate_domains_in_task

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

#: Maximum number of characters included in task preview.
#: Prevents large payload echo in structured response.
TASK_PREVIEW_LIMIT: Final[int] = 200


# ─────────────────────────────────────────────
# ASYNC → SYNC BRIDGE (THREAD SAFE)
# ─────────────────────────────────────────────

def _run_async_in_thread(coro) -> Any:
    """
    Safely execute an async coroutine from synchronous context.

    Why this exists:
    ----------------
    Some environments (FastAPI, notebooks, MCP servers) may already
    have an active event loop. Calling asyncio.run() directly would fail.

    This function:
        - Spawns a new thread
        - Creates a fresh event loop inside that thread
        - Executes the coroutine safely
        - Propagates exceptions back to caller

    Guarantees:
        - Thread-safe
        - Exception propagation preserved
        - No event loop nesting issues

    Args:
        coro: Coroutine to execute

    Returns:
        Result returned by coroutine

    Raises:
        Any exception raised inside coroutine
    """

    result_container: dict[str, Any] = {}
    exception_container: dict[str, Exception] = {}

    def runner():
        try:
            result_container["result"] = asyncio.run(coro)
        except Exception as exc:
            exception_container["error"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()

    if "error" in exception_container:
        raise exception_container["error"]

    return result_container.get("result")


# ─────────────────────────────────────────────
# LLM FACTORY
# ─────────────────────────────────────────────

def get_llm_client(provider: str, model: str, api_key: str):
    """
    Create and return an LLM client instance for the given provider.

    Supported Providers:
        - openai
        - anthropic
        - azure_openai
        - groq

    This function:
        - Does NOT validate API key correctness
        - Does NOT validate model availability
        - Does NOT perform network calls

    Args:
        provider: Provider name (case-insensitive)
        model: Model identifier
        api_key: Provider API key

    Returns:
        Provider-specific LLM client instance

    Raises:
        ValueError:
            - If provider is unknown
            - If Azure endpoint is missing
    """

    provider_normalized = provider.lower().strip()

    if provider_normalized == "openai":
        return ChatOpenAI(model=model, api_key=api_key)

    if provider_normalized == "anthropic":
        return ChatAnthropic(model=model, api_key=api_key)

    if provider_normalized == "azure_openai":
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not azure_endpoint:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT is required for Azure OpenAI."
            )

        return ChatAzureOpenAI(
            azure_deployment=model,
            api_key=api_key,
            azure_endpoint=azure_endpoint,
        )

    if provider_normalized == "groq":
        return ChatGroq(model=model, api_key=api_key)

    raise ValueError(
        f"Unknown provider '{provider}'. "
        "Valid options: openai, anthropic, azure_openai, groq."
    )


# ─────────────────────────────────────────────
# INTERNAL ASYNC EXECUTION
# ─────────────────────────────────────────────

async def _run_browser_task_async(
    *,
    task: str,
    allowed_domains: list[str] | None,
    max_steps: int,
    timeout_ms: int,
    headless: bool,
    use_vision: bool,
    provider: str,
    model: str,
    api_key: str,
) -> dict:
    """
    Internal async execution pipeline for browser automation.

    Execution Flow:
        1. Security validation (SSRF + allowlist)
        2. Browser instantiation
        3. LLM client creation
        4. Agent creation
        5. Agent execution with timeout
        6. Structured result extraction
        7. Cleanup

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

    browser: Browser | None = None
    start_time = time.time()

    def _elapsed_ms() -> int:
        return int((time.time() - start_time) * 1000)

    try:
        # ── Security Validation ─────────────────────

        if allowed_domains:
            validate_domains_in_task(task, allowed_domains)

        # ── Browser Setup ───────────────────────────

        browser_profile = BrowserProfile(headless=headless)
        browser = Browser(browser_profile=browser_profile)

        # ── LLM Setup ───────────────────────────────

        llm = get_llm_client(provider, model, api_key)

        # ── Agent Setup ─────────────────────────────

        agent = Agent(
            browser=browser,
            llm=llm,
            task=task,
            max_steps=max_steps,
            use_vision=use_vision,
        )

        # ── Execute With Timeout ───────────────────

        try:
            result = await asyncio.wait_for(
                agent.run(),
                timeout=timeout_ms / 1000,
            )
        except TimeoutError:
            return {
                "success": False,
                "error": f"Task timed out after {timeout_ms} ms",
                "status": "timeout",
                "execution_time_ms": _elapsed_ms(),
            }

        # ── Result Extraction ──────────────────────

        final_result = (
            result.final_result()
            if hasattr(result, "final_result")
            else str(result)
        )

        steps_taken = (
            len(result.action_history())
            if hasattr(result, "action_history")
            else 0
        )

        return {
            "success": True,
            "task": (
                task[:TASK_PREVIEW_LIMIT] + "..."
                if len(task) > TASK_PREVIEW_LIMIT
                else task
            ),
            "result": final_result,
            "steps_taken": steps_taken,
            "max_steps": max_steps,
            "execution_time_ms": _elapsed_ms(),
            "model_used": model,
            "provider_used": provider,
            "vision_enabled": use_vision,
        }

    except SecurityError as exc:
        return {
            "success": False,
            "error": str(exc),
            "status": "security_blocked",
            "execution_time_ms": _elapsed_ms(),
        }

    except ValueError as exc:
        return {
            "success": False,
            "error": str(exc),
            "status": "configuration_error",
            "execution_time_ms": _elapsed_ms(),
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"Browser task failed: {exc}",
            "status": "execution_error",
            "execution_time_ms": _elapsed_ms(),
        }

    finally:
        # Guarantee browser cleanup
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


# ─────────────────────────────────────────────
# PUBLIC SYNC API
# ─────────────────────────────────────────────

def run_browser_task(
    *,
    task: str,
    allowed_domains: list[str] | None,
    max_steps: int,
    timeout_ms: int,
    headless: bool,
    use_vision: bool,
    provider: str,
    model: str,
    api_key: str,
) -> dict:
    """
    Public synchronous API for browser task execution.

    This function:
        - Wraps async execution
        - Is safe in environments with active event loops
        - Guarantees structured output
        - Never leaks browser resources

    Recommended for:
        - CLI usage
        - MCP tools
        - Background workers
        - REST endpoints

    Returns:
        Structured execution result dictionary.
    """

    return _run_async_in_thread(
        _run_browser_task_async(
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
    )
