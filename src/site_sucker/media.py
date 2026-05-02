"""External media scanner for downloaded HTML files."""

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def get_external_media(
    output_dir: Path | str,
    target_domain: str,
    settings: dict[str, Any],
) -> set[str]:
    """Scan downloaded HTML and CSS for external media URLs.

    Parses all HTML and CSS files in the output directory to find external media URLs
    (images, videos, CSS, JS, fonts) that are hosted on different domains.
    Performs deduplication and URL normalization.

    Args:
        output_dir: Path to the directory containing downloaded HTML files.
        target_domain: The primary domain being mirrored (used to exclude internal URLs).
        settings: Configuration dictionary.

    Returns:
        Set of unique external media URLs.
    """
    output_dir = Path(output_dir)
    print(f"\n[2/2] Collecting external media from downloaded HTML and CSS...")

    ext_urls = set()

    # Regex to find href/src attributes
    href_src_pattern = re.compile(r'(?:href|src)=["\'](https?://[^"\'#]+)["\']')

    # Regex to find url() references in CSS (including quotes and without)
    css_url_pattern = re.compile(r'url\(\s*["\']?(https?://[^"\'\\)]+)["\']?\s*\)')

    # Build media extension regex
    extensions = settings.get("MediaExtensions", [])
    escaped_exts = [re.escape(ext) for ext in extensions]
    media_regex = re.compile(rf"(?i)({'|'.join(escaped_exts)})(\?.*)?$")

    url_count = 0
    html_files = list(output_dir.rglob("*.html")) + list(output_dir.rglob("*.htm"))
    css_files = list(output_dir.rglob("*.css"))

    # ── PART 1: Scan HTML files ────────────────────────────────────────────────
    for html_file in html_files:
        try:
            with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        except IOError:
            continue

        if not raw:
            continue

        for match in href_src_pattern.finditer(raw):
            url_count += 1
            url = match.group(1)

            # Skip URLs from the target domain
            # Only skip if hostname exactly matches target domain
            # e.g., example.com matches example.com
            # but cdn.example.com does NOT match example.com (different domain)
            try:
                url_host = urlparse(url).hostname or ""
                if url_host == target_domain:
                    continue
            except Exception:
                # If we can't parse the URL, skip it
                continue

            # Skip non-media URLs
            if not media_regex.search(url):
                continue

            # Normalize URL: strip query string for deduplication
            normalized_url = url.split("?")[0]
            ext_urls.add(normalized_url)

    # ── PART 2: Scan CSS files for url() references ─────────────────────────────
    css_url_count = 0
    for css_file in css_files:
        try:
            with open(css_file, "r", encoding="utf-8", errors="ignore") as f:
                raw_css = f.read()
        except IOError:
            continue

        if not raw_css:
            continue

        for match in css_url_pattern.finditer(raw_css):
            css_url_count += 1
            url = match.group(1)

            # Skip URLs from the target domain
            try:
                url_host = urlparse(url).hostname or ""
                if url_host == target_domain:
                    continue
            except Exception:
                continue

            # Skip non-media URLs
            if not media_regex.search(url):
                continue

            # Normalize URL: strip query string for deduplication
            normalized_url = url.split("?")[0]
            ext_urls.add(normalized_url)

    total_scanned = url_count + css_url_count
    print(f"Scanned {url_count} HTML URLs and {css_url_count} CSS url() references, found {len(ext_urls)} unique external media URLs")
    return ext_urls
