"""
Security validation for browser automation tasks.

This module enforces outbound request safety rules for browser automation
and LLM-driven browsing workflows.

It protects against:

• SSRF (Server-Side Request Forgery)
• Access to private / loopback IP ranges
• Access to localhost aliases
• Unsafe URL schemes
• Unauthorized domains (via optional allowlist)

The validator scans natural language task instructions for any referenced
URLs or domain names and ensures they comply with security policy.

Designed for use inside:
- MCP tools
- Agent-based browser automation
- LLM execution environments
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from typing import Final

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

#: Allowed URL schemes for outbound requests.
#: Any other scheme (ftp, file, gopher, etc.) will be rejected.
ALLOWED_SCHEMES: Final[set[str]] = {"http", "https"}


#: Private and loopback IP ranges that must never be accessible.
#: These ranges protect against SSRF attacks targeting:
#: - Internal infrastructure
#: - Kubernetes pods
#: - Cloud metadata services
#: - Localhost services
PRIVATE_RANGES: Final[list[ipaddress._BaseNetwork]] = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


#: Hostname aliases that resolve to localhost.
LOCALHOST_ALIASES: Final[set[str]] = {
    "localhost",
    "localhost.localdomain",
}


# Matches:
# - http://example.com
# - https://example.com
# - example.com
#
# Groups:
#   scheme     → http / https (optional)
#   url_host   → hostname extracted from full URL
#   bare_host  → domain appearing without scheme
#
# Designed for natural-language task parsing.
_DOMAIN_PATTERN = re.compile(
    r"(?:(?P<scheme>https?)://(?P<url_host>[^/\s\?#]+))"
    r"|(?<!\w)(?P<bare_host>(?:[a-z0-9\-]+\.)+[a-z]{2,})(?!\w)",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────
# EXCEPTIONS
# ─────────────────────────────────────────────

class SecurityError(Exception):
    """
    Raised when a browser security policy is violated.

    This exception should be treated as a hard-block signal.
    The calling system must stop execution immediately.
    """
    pass


# ─────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────

def _is_private_ip(host: str) -> bool:
    """
    Determine whether a host represents a private or loopback address.

    This protects against SSRF attacks by preventing access to:
        - Internal VPC ranges
        - Loopback interfaces
        - Link-local addresses
        - IPv6 private ranges

    Args:
        host: Hostname or IP address

    Returns:
        True if the host is private or localhost, otherwise False.
    """
    try:
        addr = ipaddress.ip_address(host)
        return any(addr in net for net in PRIVATE_RANGES)
    except ValueError:
        # Not an IP — check localhost aliases
        return host.lower() in LOCALHOST_ALIASES


def _normalise_host(host: str) -> str:
    """
    Normalize a hostname for safe comparison.

    Performs:
        - Port removal
        - Lowercasing
        - Trailing dot stripping (FQDN normalization)

    Args:
        host: Raw host string (may include port)

    Returns:
        Normalized hostname
    """
    host = host.split(":")[0]
    return host.rstrip(".").lower()


def _validate_scheme(scheme: str | None) -> None:
    """
    Validate that a URL scheme is allowed.

    Only 'http' and 'https' are permitted.

    Args:
        scheme: Extracted URL scheme (may be None)

    Raises:
        SecurityError: If scheme is not permitted
    """
    if scheme and scheme.lower() not in ALLOWED_SCHEMES:
        raise SecurityError(
            f"Scheme '{scheme}' is not permitted. Allowed schemes: {ALLOWED_SCHEMES}"
        )


def _is_domain_allowed(host: str, allowed_domains: Iterable[str]) -> bool:
    """
    Check whether a host matches an allowlist.

    Supports:
        - Exact matches
        - Subdomain matches
        - Wildcard-style prefixes (e.g. *.example.com)

    Args:
        host: Normalized hostname
        allowed_domains: Iterable of allowed domains

    Returns:
        True if host is allowed, otherwise False.
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
    Validate all domains referenced in a natural-language task.

    This function scans the task text for any domain or URL references
    and enforces:

        1. Allowed schemes (http / https only)
        2. No access to private or loopback IP ranges
        3. Optional domain allowlist enforcement

    Intended for use before executing browser automation tasks.

    Example:
        validate_domains_in_task(
            task="Go to https://example.com and log in",
            allowed_domains=["example.com"]
        )

    Args:
        task:
            Natural language instruction that may contain URLs.

        allowed_domains:
            Optional list of permitted domains.
            If provided, all referenced domains must match this list.

    Raises:
        SecurityError:
            - If a private IP is referenced
            - If localhost is referenced
            - If a scheme is invalid
            - If a domain is not allowlisted
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
