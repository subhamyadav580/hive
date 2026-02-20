"""
Security validation for browser automation tasks.

Enforces:
- SSRF protection (private/loopback IP blocking)
- Domain allowlisting
- Scheme validation (http/https only)
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from typing import Final

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

ALLOWED_SCHEMES: Final[set[str]] = {"http", "https"}

PRIVATE_RANGES: Final[list[ipaddress._BaseNetwork]] = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

LOCALHOST_ALIASES: Final[set[str]] = {
    "localhost",
    "localhost.localdomain",
}


# Matches:
# - http(s)://example.com
# - example.com
_DOMAIN_PATTERN = re.compile(
    r"(?:(?P<scheme>https?)://(?P<url_host>[^/\s\?#]+))"
    r"|(?<!\w)(?P<bare_host>(?:[a-z0-9\-]+\.)+[a-z]{2,})(?!\w)",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────
# EXCEPTIONS
# ─────────────────────────────────────────────

class SecurityError(Exception):
    """Raised when a browser security policy is violated."""


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

def _is_private_ip(host: str) -> bool:
    """
    Returns True if host is a private/loopback IP.
    """
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in PRIVATE_RANGES)
    except ValueError:
        return host.lower() in LOCALHOST_ALIASES


def _normalise_host(host: str) -> str:
    """
    Normalize hostname:
    - Remove port
    - Lowercase
    - Strip trailing dot
    """
    host = host.split(":")[0]
    return host.rstrip(".").lower()


def _validate_scheme(scheme: str | None) -> None:
    """
    Ensure scheme is allowed.
    """
    if scheme and scheme.lower() not in ALLOWED_SCHEMES:
        raise SecurityError(
            f"Scheme '{scheme}' is not permitted. Allowed schemes: {ALLOWED_SCHEMES}"
        )


def _is_domain_allowed(host: str, allowed_domains: Iterable[str]) -> bool:
    """
    Check if host matches allowlist (supports subdomains).
    """
    for allowed in allowed_domains:
        normalized = allowed.lower().lstrip("*.")
        if host == normalized or host.endswith("." + normalized):
            return True
    return False


# ─────────────────────────────────────────────
# PUBLIC VALIDATION
# ─────────────────────────────────────────────

def validate_domains_in_task(
    task: str,
    allowed_domains: list[str] | None,
) -> None:
    """
    Validate that all domains referenced in a task comply with security policy.

    Enforces:
    - http/https schemes only
    - No private/loopback IPs
    - Domain allowlist (if provided)

    Args:
        task: Natural language instruction
        allowed_domains: Optional list of allowed domains

    Raises:
        SecurityError: If validation fails
    """

    if not task:
        return

    for match in _DOMAIN_PATTERN.finditer(task):
        scheme = match.group("scheme")
        raw_host = match.group("url_host") or match.group("bare_host")

        if not raw_host:
            continue

        _validate_scheme(scheme)

        host = _normalise_host(raw_host)

        # ── SSRF Protection ─────────────────

        if _is_private_ip(host):
            raise SecurityError(
                f"Access to private/loopback address '{host}' is not permitted."
            )

        # ── Allowlist Enforcement ───────────

        if allowed_domains:
            if not _is_domain_allowed(host, allowed_domains):
                raise SecurityError(
                    f"Domain '{host}' is not in the allowed_domains list."
                )
