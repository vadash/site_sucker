"""Offline HTML cleaner - strips online-only resources using BeautifulSoup."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from site_sucker.file_iter import iter_html_files, write_if_changed
from site_sucker.progress import ProgressTracker

logger = logging.getLogger(__name__)


@dataclass
class RemovalRule:
    """Rule for removing DOM nodes.

    Attributes:
        tag: HTML tag name to match.
        attrs: Dictionary of attributes to match (passed to BeautifulSoup's find_all).
        check_content: Optional regex to match against tag text content.
        check_nested: Optional nested tag spec (tag, attrs) to check before removing.
    """

    tag: str
    attrs: dict[str, Any] | None = None
    check_content: re.Pattern[str] | None = None
    check_nested: tuple[str, dict[str, Any]] | None = None


# Data-driven removal rules for online-only resources
_REMOVAL_RULES = [
    # MediaWiki load.php resources
    RemovalRule(tag="link", attrs={"rel": "stylesheet", "href": re.compile(r"load\.php")}),
    RemovalRule(tag="script", attrs={"src": re.compile(r"load\.php")}),
    # Network hints
    RemovalRule(tag="link", attrs={"rel": "preconnect"}),
    RemovalRule(tag="link", attrs={"rel": "dns-prefetch"}),
    # Metadata links
    RemovalRule(tag="link", attrs={"rel": "EditURI"}),
    RemovalRule(tag="link", attrs={"type": re.compile(r"application/(atom|rss)\+xml")}),
    # Analytics and tracking
    RemovalRule(tag="script", check_content=re.compile(r"_paq")),
    RemovalRule(tag="script", attrs={"src": re.compile(r"google-analytics\.com", re.IGNORECASE)}),
    RemovalRule(tag="script", check_content=re.compile(r"google-analytics\.com", re.IGNORECASE)),
    # Noscript tracking pixels
    RemovalRule(
        tag="noscript",
        check_nested=(
            "img",
            {"src": re.compile(r"(matomo|analytics|doubleclick|google-analytics)", re.IGNORECASE)},
        ),
    ),
    # FontAwesome CDN
    RemovalRule(tag="script", attrs={"src": re.compile(r"9a832b96e0\.js")}),
    RemovalRule(tag="link", attrs={"href": re.compile(r"use\.fontawesome\.com", re.IGNORECASE)}),
    RemovalRule(tag="script", check_content=re.compile(r"FontAwesomeCdnConfig")),
    # Google Analytics inline calls
    RemovalRule(tag="script", check_content=re.compile(r"""ga\(['\"]create['""]""")),
    RemovalRule(tag="script", check_content=re.compile(r"""ga\(['\"]send['""]""")),
    # phpBB navigation links
    RemovalRule(
        tag="a", attrs={"href": re.compile(r"(posting|tradegold|memberlist|search|ucp|mcp)\.php")}
    ),
]


def _remove_dom_nodes(soup: BeautifulSoup) -> int:
    """Remove unwanted DOM nodes using data-driven rules.

    Args:
        soup: BeautifulSoup object representing the HTML document.

    Returns:
        Number of nodes removed.
    """
    removed_count = 0

    for rule in _REMOVAL_RULES:
        # Find all tags matching the rule
        tags = soup.find_all(rule.tag, **(rule.attrs or {}))

        for tag in tags:
            # Check content regex if specified
            if rule.check_content and not rule.check_content.search(tag.string or ""):
                continue

            # Check nested tag condition if specified
            if rule.check_nested:
                nested_tag, nested_attrs = rule.check_nested
                if not tag.find(nested_tag, **nested_attrs):
                    continue

            tag.decompose()
            removed_count += 1

    return removed_count


def _clean_inline_javascript(content: str) -> str:
    """Clean inline JavaScript code using regex (string-level operations).

    These are content-level replacements within script tag contents,
    not DOM operations, so regex is appropriate.

    Args:
        content: Serialized HTML string from BeautifulSoup.

    Returns:
        Cleaned HTML string.
    """
    # Remove Google Analytics inline calls (more flexible pattern)
    content = re.sub(r"""ga\(['\"]create['\"],\s*[^)]+\);?""", "", content)
    content = re.sub(
        r"""ga\(['\"]send['\"],\s*[^)]+\);?""", "", content
    )  # This should match both 'pageview' and "pageview"

    # Remove analytics push calls
    content = re.sub(r"""\.push\(\s*\[?\s*['"]trackPageView['"].*?\);?""", "", content)
    content = re.sub(r"""\.push\(\s*\[?\s*['"]enableLinkTracking['"].*?\);?""", "", content)

    # Remove FontAwesome CDN config (simple and complex patterns)
    content = re.sub(
        r"""window\.FontAwesomeCdnConfig\s*=\s*\{[^}]+\}\s*;""", "", content, flags=re.DOTALL
    )
    content = re.sub(
        r"""window\.FontAwesomeCdnConfig\s*=\s*\{[^}]+\}\s*;.*?function\s*\([^)]*\)[^{]*\{[^}]*\}\s*\([^)]*\)\s*;""",
        "",
        content,
        flags=re.DOTALL,
    )

    return content


def repair_offline_html(output_dir: Path | str) -> int:
    """Strip online-only resources from HTML for offline browsing using BeautifulSoup.

    Removes or neutralizes HTML elements that block offline rendering:
    - Removes remote CSS/JS links (load.php) that weren't downloaded
    - Removes preconnect/dns-prefetch hints (useless offline)
    - Removes tracking/analytics scripts and pixels
    - Removes online-only navigation links (EditURI, Atom feeds, etc.)
    - Injects minimal fallback CSS

    Uses BeautifulSoup DOM operations for tag removal (safe, cannot corrupt HTML)
    and regex only for inline JavaScript content cleanup.

    Args:
        output_dir: Path to the directory containing downloaded HTML files.

    Returns:
        Number of HTML files modified.
    """
    output_dir = Path(output_dir)

    # Collect files upfront to get total count for progress
    html_items = list(iter_html_files(output_dir))
    total = len(html_items)

    if total == 0:
        logger.info("[4/4] Stripping online-only resources for offline browsing...")
        return 0

    logger.info("[4/4] Stripping online-only resources for offline browsing... (%d file(s))", total)

    modified_count = 0
    progress = ProgressTracker(total)

    for processed, (html_file, content) in enumerate(html_items, start=1):
        # Parse with BeautifulSoup using lxml parser
        soup = BeautifulSoup(content, "lxml")

        # 1. Remove unwanted DOM nodes
        removed = _remove_dom_nodes(soup)

        # 2. Inject fallback CSS before </head> (DOM operation, before serializing)
        if soup.head:
            style_tag = soup.new_tag("style")
            style_tag.string = (
                "/* Minimal fallback CSS for offline browsing */\n"
                "body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0; }\n"
                "#content { max-width: 960px; margin: 0 auto; padding: 20px; }\n"
                "h1, h2, h3 { margin-top: 1.5em; }\n"
                "a { color: #0645ad; text-decoration: none; }\n"
                "a:hover { text-decoration: underline; }\n"
                ".mw-body-content { padding: 1em; }"
            )
            soup.head.append(style_tag)

        # 3. Serialize to string once
        cleaned_content = str(soup)

        # 4. Clean inline JavaScript (regex is appropriate for string-level ops)
        cleaned_content = _clean_inline_javascript(cleaned_content)

        # 5. Only write if content changed
        if removed > 0 or cleaned_content != content:
            write_if_changed(html_file, content, cleaned_content)
            modified_count += 1

        progress.update(processed)

    progress.finish()

    if modified_count > 0:
        logger.info("  Cleaned %d HTML file(s) for offline use", modified_count)

    return modified_count
