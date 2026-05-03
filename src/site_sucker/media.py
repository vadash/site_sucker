"""External media scanner for downloaded HTML and CSS files."""

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from site_sucker.file_iter import iter_css_files, iter_html_files
from site_sucker.settings import Settings

logger = logging.getLogger(__name__)


def get_external_media(
    output_dir: Path | str,
    target_domain: str,
    settings: Settings,
) -> set[str]:
    """Scan downloaded HTML and CSS for external media URLs.

    Uses BeautifulSoup for HTML files (scans href/src attributes on relevant tags).
    Uses regex for CSS files (scans url() references).

    Performs deduplication and URL normalization.

    Args:
        output_dir: Path to the directory containing downloaded HTML files.
        target_domain: The primary domain being mirrored (used to exclude internal URLs).
        settings: Settings instance.

    Returns:
        Set of unique external media URLs.
    """
    output_dir = Path(output_dir)
    logger.info("[2/2] Collecting external media from downloaded HTML and CSS...")

    ext_urls = set()

    # Regex to find url() references in CSS (including quotes and without)
    css_url_pattern = re.compile(r'url\(\s*["\']?(https?://[^"\'\\)]+)["\']?\s*\)')

    # Build media extension regex
    extensions = settings.media_extensions
    escaped_exts = [re.escape(ext) for ext in extensions]
    media_regex = re.compile(rf"(?i)({'|'.join(escaped_exts)})(\?.*)?$")

    url_count = 0

    # ── PART 1: Scan HTML files with BeautifulSoup ─────────────────────────────
    for _html_file, content in iter_html_files(output_dir):
        soup = BeautifulSoup(content, "lxml")

        # Scan all tags that can have media URLs
        for tag in soup.find_all(["img", "script", "link", "video", "audio", "source"]):
            # Check src and href attributes
            for attr in ("src", "href", "data-src"):
                url = tag.get(attr)
                if not url:
                    continue

                url_count += 1

                # Skip non-HTTP URLs
                if not url.startswith(("http://", "https://")):
                    continue

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
    for _css_file, raw_css in iter_css_files(output_dir):
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

    url_count + css_url_count
    logger.info(
        "Scanned %d HTML URLs and %d CSS url() references, found %d unique external media URLs",
        url_count,
        css_url_count,
        len(ext_urls),
    )
    return ext_urls
