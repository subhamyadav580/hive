#!/usr/bin/env python3
"""
One-time setup script for Browser Automation Tool.

This script:
1. Saves LLM provider API keys
2. Saves multi-key website credentials (generic)
"""

import sys
from getpass import getpass
from pathlib import Path

from pydantic import SecretStr

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from framework.credentials import CredentialStore
from framework.credentials.models import CredentialKey, CredentialObject

# ─────────────────────────────────────────────
# GLOBAL STORE (encrypted)
# ─────────────────────────────────────────────

store = CredentialStore.with_encrypted_storage()


# ─────────────────────────────────────────────
# LLM CREDENTIAL SETUP
# ─────────────────────────────────────────────

def setup_llm_credentials():
    print("\nLLM API Key Setup\n")

    def save(provider_id: str, api_key: str):
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
        print(f"✓ Saved {provider_id} credentials")

    anthropic = input("Anthropic API Key (press Enter to skip): ").strip()
    if anthropic:
        save("anthropic", anthropic)

    openai = input("OpenAI API Key (press Enter to skip): ").strip()
    if openai:
        save("openai", openai)

    print("LLM setup complete.\n")


# ─────────────────────────────────────────────
# GENERIC WEBSITE CREDENTIAL SETUP
# ─────────────────────────────────────────────

def setup_website_credentials():
    print("\nWebsite / Service Credential Setup\n")
    print("You can store ANY multi-key credential (login, API, OAuth, etc.)")
    print("Example keys: username, password, api_key, access_token\n")

    while True:
        ref_id = input("Credential ID (or 'quit' to finish): ").strip()

        if ref_id.lower() in ("quit", "q", "exit"):
            break

        if not ref_id:
            print("Credential ID cannot be empty.\n")
            continue

        keys = {}

        print("\nEnter credential fields (leave field name empty to finish):")

        while True:
            key_name = input("Field name (e.g. username, password, api_key): ").strip()

            if not key_name:
                break

            # Use getpass for sensitive fields
            if "password" in key_name.lower() or "secret" in key_name.lower():
                value = getpass(f"{key_name}: ").strip()
            else:
                value = input(f"{key_name}: ").strip()

            if value:
                keys[key_name] = CredentialKey(
                    name=key_name,
                    value=SecretStr(value),
                )

        if not keys:
            print("No fields provided. Skipping.\n")
            continue

        store.save_credential(
            CredentialObject(
                id=ref_id,
                keys=keys,
            )
        )

        print(f"✓ Saved credential: {ref_id}\n")

    print("Website credential setup complete.\n")

def list_credentials():
    creds = store.list_credentials()
    print("\nListing stored credentials...", creds)
    if not creds:
        print("No credentials stored.")
        return

    print("\nStored Credentials:")
    for cred in creds:
        print(f"- {cred.id} (fields: {', '.join(cred.keys.keys())})")
    print()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\nBrowser Automation Tool Setup\n")

    # setup_llm_credentials()
    # setup_website_credentials()

    list_credentials()

    print("Setup complete! You can now use stored credentials via credential_ref.\n")
