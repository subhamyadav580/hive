"""
Model configuration and provider defaults for Browser-Use.

This module defines:

• Default text and vision models per LLM provider
• Provider auto-detection order
• Environment variable mappings
• Safe global fallback logic
• Default model resolution behavior

Design Goals:
-------------
- Deterministic model selection
- Safe fallback behavior
- Zero runtime network validation
- Predictable provider detection
- Clear separation of text vs vision models

This module does NOT:
- Validate API keys
- Validate model availability
- Perform provider connectivity checks

It strictly handles configuration resolution.
"""

from __future__ import annotations

from typing import Final, Literal, TypedDict

# ─────────────────────────────────────────────
# TYPES
# ─────────────────────────────────────────────

#: Supported LLM providers.
#: Keep this union aligned with DEFAULT_MODELS and PROVIDER_ENV_VARS.
ProviderType = Literal["openai", "anthropic", "groq", "azure_openai"]


class ProviderModels(TypedDict):
    """
    Defines the default models for a provider.

    Attributes:
        text:
            Default model used for standard text generation.

        vision:
            Default model used when multimodal (vision) support is required.
    """

    text: str
    vision: str


# ─────────────────────────────────────────────
# SAFE FALLBACKS
# ─────────────────────────────────────────────

#: Global fallback text model used when:
#: - Provider is unknown
#: - Provider config is missing
#: - Provider string is empty
FALLBACK_TEXT_MODEL: Final[str] = "gpt-4o-mini"


#: Global fallback vision model used when:
#: - Provider is unknown
#: - Vision is requested but provider config is missing
FALLBACK_VISION_MODEL: Final[str] = "gpt-4o"


# ─────────────────────────────────────────────
# DEFAULT MODELS
# ─────────────────────────────────────────────

"""
Default model configuration per provider.

Guidelines:
-----------
- Choose stable, production-ready models.
- Prefer general-purpose models over niche variants.
- Vision model must support image input.
- Text model should optimize cost/performance balance.
"""

DEFAULT_MODELS: Final[dict[ProviderType, ProviderModels]] = {
    "anthropic": {
        # Claude Sonnet supports both text and vision
        "text": "claude-3-5-sonnet-20241022",
        "vision": "claude-3-5-sonnet-20241022",
    },
    "openai": {
        # Cost-efficient default text model
        "text": "gpt-4o-mini",
        # Full multimodal model
        "vision": "gpt-4o",
    },
    "groq": {
        "text": "llama-3.1-70b-versatile",
        "vision": "llama-3.2-90b-vision-preview",
    },
    "azure_openai": {
        # Azure deployments may differ per tenant
        # These represent common baseline deployments
        "text": "gpt-4",
        "vision": "gpt-4o",
    },
}


# ─────────────────────────────────────────────
# PROVIDER DETECTION ORDER
# ─────────────────────────────────────────────

"""
Order in which providers are auto-detected.

Detection typically checks:
    - Environment variables
    - Config files
    - Explicit overrides

Priority matters:
    Earlier providers take precedence if multiple API keys exist.
"""

PROVIDER_DETECTION_ORDER: Final[list[ProviderType]] = [
    "anthropic",
    "openai",
    "groq",
    "azure_openai",
]


# ─────────────────────────────────────────────
# ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────

"""
Mapping of providers to expected API key environment variables.

These are used for:
    - Auto-detection
    - Configuration validation
    - CLI bootstrapping

Note:
    This module does NOT read environment variables directly.
    It only defines canonical names.
"""

PROVIDER_ENV_VARS: Final[dict[ProviderType, str]] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "groq": "GROQ_API_KEY",
}


# ─────────────────────────────────────────────
# MODEL RESOLUTION
# ─────────────────────────────────────────────

def get_default_model(provider: str, use_vision: bool) -> str:
    """
    Resolve the appropriate default model for a provider.

    Resolution Logic:
    -----------------
    1. If provider is empty → return global fallback.
    2. Normalize provider to lowercase.
    3. If provider exists in DEFAULT_MODELS:
         - Return vision model if `use_vision=True`
         - Otherwise return text model
    4. If provider is unknown → return global fallback.

    This function:
        - Is deterministic
        - Does not validate API keys
        - Does not verify model availability
        - Does not perform network calls

    Args:
        provider:
            LLM provider name (case-insensitive).

        use_vision:
            Whether vision capabilities are required.

    Returns:
        Model name suitable for the provider and requested capability.

    Examples:
        >>> get_default_model("openai", False)
        'gpt-4o-mini'

        >>> get_default_model("anthropic", True)
        'claude-3-5-sonnet-20241022'

        >>> get_default_model("unknown", False)
        'gpt-4o-mini'
    """

    if not provider:
        return FALLBACK_VISION_MODEL if use_vision else FALLBACK_TEXT_MODEL

    provider_normalized = provider.lower()

    provider_models = DEFAULT_MODELS.get(provider_normalized)  # type: ignore[arg-type]

    if not provider_models:
        # Unknown provider → safe global fallback
        return FALLBACK_VISION_MODEL if use_vision else FALLBACK_TEXT_MODEL

    return provider_models["vision"] if use_vision else provider_models["text"]
