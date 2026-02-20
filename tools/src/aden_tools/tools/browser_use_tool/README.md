# Browser-Use MCP Tool – Natural Language Web Automation

AI-powered browser automation for Hive using natural language instructions, secure credential storage, and adaptive web interaction.

---

# Overview

The Browser-Use MCP Tool enables Hive agents to control a real browser using plain English instructions.

Instead of writing deterministic automation scripts or relying on predefined selectors, agents can:

- Navigate multi-step workflows
- Adapt to layout changes
- Extract structured content
- Perform research across dynamic websites
- Execute authenticated browsing tasks

Example tasks:

- "Search Google for Python tutorials and summarize the top 3 results"
- "Log into Gmail and count unread emails"
- "Compare pricing tiers on three competitor websites"
- "Fill out this form with my saved details"

This integration expands Hive's capabilities beyond static scraping and deterministic automation.

---

# Why This Integration Exists

Hive currently supports:

| Tool | Purpose |
|------|---------|
| `web_search_tool` | URL discovery |
| `web_scrape_tool` | Static HTML extraction |
| Playwright Tool (#4701) | Deterministic browser automation |

However, none provide **adaptive, natural language-driven web interaction**.

Browser-Use introduces a higher abstraction layer.

---

## Comparison with Existing Tools

| Tool | Best For | Requires Selectors | Adaptive |
|------|----------|-------------------|----------|
| web_scrape_tool | Static scraping | No | No |
| Playwright Tool | Structured automation | Yes | No |
| Browser-Use | Research & exploratory tasks | No | Yes |

### Positioning

- Playwright → low-level deterministic control
- Browser-Use → high-level autonomous reasoning
- They are complementary, not competing tools

---

# Architecture Notes

- Browser-Use does NOT manage LLM providers directly.
- It relies on Hive’s global credential resolution system.
- No API keys are required specifically for Browser-Use.
- LLM resolution follows Hive priority rules.

---

# MVP Constraints

This integration intentionally avoids:

- Stealth plugins
- Fingerprint spoofing
- Bot-evasion mechanisms
- User-agent masking

The browser operates transparently and is designed for legitimate automation and research use cases.

---

# One-Time Setup

This setup configures:

1. LLM provider API keys
2. Website login credentials

---

## Create Setup Script

Create `setup_browser_tool.py`:

```python
#!/usr/bin/env python3
import sys
from pathlib import Path
from pydantic import SecretStr

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from framework.credentials import CredentialStore
from framework.credentials.models import CredentialKey, CredentialObject
from aden_tools.credentials.auth_store import get_auth_store

def setup_llm_credentials():
    store = CredentialStore.with_encrypted_storage()

    def save(provider_id, api_key):
        store.save_credential(
            CredentialObject(
                id=provider_id,
                keys={
                    "api_key": CredentialKey(
                        name="api_key",
                        value=SecretStr(api_key),
                    )
                },
            )
        )
        print(f"Saved {provider_id}")

    anthropic = input("Anthropic API Key (Enter to skip): ").strip()
    if anthropic:
        save("anthropic", anthropic)

    openai = input("OpenAI API Key (Enter to skip): ").strip()
    if openai:
        save("openai", openai)

def setup_website_credentials():
    auth_store = get_auth_store()

    while True:
        ref_id = input("Reference ID (or 'quit'): ").strip()
        if ref_id.lower() in ("quit", "q", "exit"):
            break

        username = input("Username: ").strip()
        password = input("Password: ").strip()
        two_factor = input("2FA Secret (optional): ").strip()

        metadata = {"two_factor_secret": two_factor} if two_factor else None

        auth_store.save_auth_credential(
            ref_id=ref_id,
            username=username,
            password=password,
            metadata=metadata
        )
        print(f"Saved {ref_id}")

if __name__ == "__main__":
    setup_llm_credentials()
    setup_website_credentials()
```

Run:

```bash
python3 setup_browser_tool.py
```

---

# Available Tools

## Core Tools

### `browser_use_task`

General natural-language browsing.

| Parameter | Default | Notes |
|------------|----------|--------|
| task | Required | Natural language instruction |
| max_steps | 15 | 1–50 |
| timeout_ms | 300000 | 5000–300000 |
| allowed_domains | None | Optional allowlist |
| headless | True | GUI off |
| provider | Auto | LLM provider |
| model | Auto | Optional override |
| use_vision | False | Vision mode |
| api_key | None | Explicit override |

---

### `browser_use_auth_task`

Authenticated browsing.

Use `credential_ref` (recommended) or explicit credentials.

---

### `browser_use_vision_task`

Vision-enabled browsing (auto-selects vision-capable model).

---

## Credential Tools

- `save_auth_credential`
- `list_auth_credentials`
- `delete_auth_credential`
- `get_auth_credential_info`

Passwords are never returned via API.

---

# Limits & Safeguards

## Input Validation

| Parameter | Min | Max |
|------------|------|------|
| max_steps | 1 | 50 |
| timeout_ms | 5000 | 300000 |

---

## SSRF Protection

Blocked:

- Private IP ranges
- Loopback addresses
- `localhost`
- Non-http/https schemes

Cannot be disabled.

---

## Domain Allowlisting

When set, only allowed domains are accessible.

---

## Credential Encryption

- Encrypted at rest
- Never logged
- Never returned
- Stored in `~/.hive/credentials/`

---

# Execution Safeguards

- One browser instance per task
- Automatic cleanup after execution
- Step limit enforcement
- Timeout enforcement
- Memory cleanup for credentials

---

# Error Format

```json
{
  "success": false,
  "error": "Explanation",
  "status": "timeout | security_blocked | configuration_error | execution_error"
}
```

---

# Credential Resolution Priority

## LLM API Keys

1. Explicit `api_key`
2. Credential store
3. Environment variable

## Website Credentials

1. `credential_ref`
2. Explicit `username/password`

---

# Resource Considerations

This tool uses:

- A headless browser instance
- LLM reasoning for navigation

It is heavier than static scraping and should be used appropriately for adaptive tasks.

---

# Testing Strategy

- Unit tests with mocked browser context
- SSRF validation tests
- Domain allowlist enforcement tests
- Timeout & step limit tests
- Integration test against JS-rendered page
- Browser cleanup verification

---

# Recommended Usage Flow

1. Configure API keys
2. Save website credentials
3. Use `browser_use_task` for research
4. Use `browser_use_auth_task` for login workflows
5. Use `browser_use_vision_task` when visual context is needed

---

# Summary

Browser-Use adds high-level, adaptive web interaction to Hive.

It complements deterministic automation tools and expands Hive’s ability to perform:

- Intelligent research
- Multi-step navigation
- Authenticated workflows
- Dynamic content extraction

Secure, controlled, and architecturally aligned with Hive’s design.
