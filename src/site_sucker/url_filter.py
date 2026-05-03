"""URL filtering utilities.

Shared by resume crawler, media scanner, and wget argument builder.
"""

from urllib.parse import urlparse
from typing import Iterable


def should_reject_url(
    url: str,
    target_domain: str,
    reject_patterns: Iterable[str] | None = None,
    reject_domains: Iterable[str] | None = None,
) -> bool:
    """Check if a URL should be rejected based on filtering rules.

    Args:
        url: The URL to check.
        target_domain: Primary domain being mirrored (urls from other domains are rejected).
        reject_patterns: List of substring patterns to reject (e.g., ["action=", "Special:"]).
        reject_domains: List of domains to reject (e.g., ["analytics.example.com"]).

    Returns:
        True if the URL should be rejected, False otherwise.
    """
    # Skip anchors, javascript, and mailto links
    if url.startswith(("#", "javascript:", "mailto:", "data:")):
        return True

    try:
        parsed = urlparse(url)
    except Exception:
        return True

    # Only accept HTTP/HTTPS URLs
    if parsed.scheme not in ("http", "https"):
        return True

    # Reject URLs from other domains
    if parsed.hostname != target_domain:
        return True

    # Check reject patterns (substring match)
    if reject_patterns:
        if any(pattern in url for pattern in reject_patterns):
            return True

    # Check reject domains (exact hostname match)
    if reject_domains and parsed.hostname:
        if any(parsed.hostname == domain for domain in reject_domains):
            return True

    return False
