"""
Core browser automation execution engine.

Responsibilities:
- Security validation
- LLM client creation
- Browser lifecycle management
- Agent execution
- Structured result handling
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Final

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

TASK_PREVIEW_LIMIT: Final[int] = 200


# ─────────────────────────────────────────────
# LLM FACTORY
# ─────────────────────────────────────────────

def get_llm_client(provider: str, model: str, api_key: str):
    """
    Create LLM client for a provider.

    Raises:
        ValueError if provider is unsupported or misconfigured.
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
# CORE EXECUTION
# ─────────────────────────────────────────────

async def run_browser_task(
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
    Execute a natural-language browser automation task.

    Returns:
        dict containing:
            - success (bool)
            - result (str, optional)
            - error (str, optional)
            - status (str, optional)
            - execution_time_ms (int)
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

        # ── Extract Result Safely ───────────────────

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

    # ─────────────────────────────────────────────
    # ERROR HANDLING
    # ─────────────────────────────────────────────

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
        if browser:
            try:
                await browser.close()
            except Exception:
                # Do not mask primary errors
                pass
