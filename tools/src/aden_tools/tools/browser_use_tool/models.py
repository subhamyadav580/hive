"""
Model configuration and provider defaults for Browser-Use.

Defines:
- Default text + vision models per provider
- Provider auto-detection order
- Environment variable mappings
- Safe fallback logic
"""

from __future__ import annotations

from typing import Final, Literal, TypedDict

# ─────────────────────────────────────────────
# TYPES
# ─────────────────────────────────────────────

ProviderType = Literal["openai", "anthropic", "groq", "azure_openai"]


class ProviderModels(TypedDict):
    text: str
    vision: str


# ─────────────────────────────────────────────
# SAFE FALLBACKS
# ─────────────────────────────────────────────

FALLBACK_TEXT_MODEL: Final[str] = "gpt-4o-mini"
FALLBACK_VISION_MODEL: Final[str] = "gpt-4o"


# ─────────────────────────────────────────────
# DEFAULT MODELS
# ─────────────────────────────────────────────

DEFAULT_MODELS: Final[dict[ProviderType, ProviderModels]] = {
    "anthropic": {
        "text": "claude-3-5-sonnet-20241022",
        "vision": "claude-3-5-sonnet-20241022",  # Sonnet supports vision
    },
    "openai": {
        "text": "gpt-4o-mini",
        "vision": "gpt-4o",
    },
    "groq": {
        "text": "llama-3.1-70b-versatile",
        "vision": "llama-3.2-90b-vision-preview",
    },
    "azure_openai": {
        "text": "gpt-4",
        "vision": "gpt-4o",
    },
}


# ─────────────────────────────────────────────
# PROVIDER DETECTION ORDER
# ─────────────────────────────────────────────

PROVIDER_DETECTION_ORDER: Final[list[ProviderType]] = [
    "anthropic",
    "openai",
    "groq",
    "azure_openai",
]


# ─────────────────────────────────────────────
# ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────

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

    Args:
        provider: LLM provider name (case-insensitive)
        use_vision: Whether vision capabilities are required

    Returns:
        Model name suitable for the provider and capability.

    Notes:
        - Falls back safely if provider is unknown.
        - Does NOT validate API availability.
    """

    if not provider:
        return FALLBACK_VISION_MODEL if use_vision else FALLBACK_TEXT_MODEL

    provider_normalized = provider.lower()

    provider_models = DEFAULT_MODELS.get(provider_normalized)  # type: ignore[arg-type]

    if not provider_models:
        # Unknown provider → safe global fallback
        return FALLBACK_VISION_MODEL if use_vision else FALLBACK_TEXT_MODEL

    return provider_models["vision"] if use_vision else provider_models["text"]
