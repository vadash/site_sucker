"""URL filtering utilities.

Shared by resume crawler, media scanner, and wget argument builder.
"""

from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


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
    if reject_patterns and any(pattern in url for pattern in reject_patterns):
        return True

    # Check reject domains (exact hostname match)
    return bool(
        reject_domains
        and parsed.hostname
        and any(parsed.hostname == domain for domain in reject_domains)
    )


# Tags and attributes to scan for navigation links (e.g., <a href>)
_NAV_TAGS = [("a", ["href"])]

# Tags and attributes to scan for embedded resources (images, scripts, etc.)
_RESOURCE_TAGS = [
    ("img", ["src", "data-src"]),
    ("script", ["src"]),
    ("link", ["href"]),
    ("video", ["src"]),
    ("audio", ["src"]),
    ("source", ["src", "data-src"]),
]


def extract_internal_urls(
    soup: BeautifulSoup,
    base_url: str,
    target_domain: str,
    reject_patterns: Iterable[str] | None = None,
    reject_domains: Iterable[str] | None = None,
) -> set[str]:
    """Extract all internal URLs from a parsed HTML document.

    Scans both navigation links (<a> tags) and embedded resources
    (img, script, link, video, audio, source tags). Returns a set of
    absolute URLs that belong to the target domain, after reject filtering.

    This is a shared utility used by:
    - resume.py::discover_links() (BFS crawler link discovery)
    - repair_links.py::repair_internal_links() (local link rewriting)

    Args:
        soup: BeautifulSoup object representing the parsed HTML.
        base_url: Base URL of this HTML file (used to resolve relative links).
        target_domain: Primary domain to filter links (only keep links to this domain).
        reject_patterns: List of substring patterns to reject (e.g., ["action=", "Special:"]).
        reject_domains: List of domains to reject (e.g., ["analytics.example.com"]).

    Returns:
        Set of absolute URLs belonging to target_domain, after reject filtering.
        Fragments are stripped from URLs (e.g., "page.html#section" → "page.html").
    """
    urls = set()

    def _add_url(url_attr: str) -> None:
        """Add a URL to the links set after validation and filtering."""
        # Skip anchors, javascript, mailto, and data URLs
        if url_attr.startswith(("#", "javascript:", "mailto:", "data:")):
            return

        # Resolve relative URLs to absolute
        absolute_url = urljoin(base_url, url_attr)

        # Use shared URL filter
        if should_reject_url(
            absolute_url,
            target_domain,
            reject_patterns,
            reject_domains,
        ):
            return

        # Strip fragments for normalization
        normalized = absolute_url.split("#")[0]
        urls.add(normalized)

    # Scan navigation links
    for tag_name, attrs in _NAV_TAGS:
        for tag in soup.find_all(tag_name):
            for attr in attrs:
                url = tag.get(attr)
                if url:
                    _add_url(url)

    # Scan embedded resources
    for tag_name, attrs in _RESOURCE_TAGS:
        for tag in soup.find_all(tag_name):
            for attr in attrs:
                url = tag.get(attr)
                if url:
                    _add_url(url)

    return urls
