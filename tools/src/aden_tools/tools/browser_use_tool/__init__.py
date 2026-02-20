"""
Browser automation tool with AI agents.
"""

from .credentials import CredentialResolver
from .execution import get_llm_client, run_browser_task
from .models import (
    DEFAULT_MODELS,
    PROVIDER_DETECTION_ORDER,
    PROVIDER_ENV_VARS,
    get_default_model,
)
from .registration import register_tools
from .security import SecurityError, validate_domains_in_task

__all__ = [
    # Main registration
    "register_tools",

    # Core functionality
    "run_browser_task",
    "get_llm_client",

    # Credentials
    "CredentialResolver",

    # Models
    "DEFAULT_MODELS",
    "PROVIDER_DETECTION_ORDER",
    "PROVIDER_ENV_VARS",
    "get_default_model",

    # Security
    "SecurityError",
    "validate_domains_in_task",
]
