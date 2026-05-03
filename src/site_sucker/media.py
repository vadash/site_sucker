"""External media scanner for downloaded HTML and CSS files."""

import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from site_sucker.file_iter import iter_css_files, iter_html_files
from site_sucker.progress import ProgressTracker
from site_sucker.settings import Settings

logger = logging.getLogger(__name__)


def _scan_html_media(
    html_items: list[tuple[Path, str]],
    target_domain: str,
    media_regex: re.Pattern[str],
) -> tuple[set[str], int]:
    """Scan HTML files for external media URLs using BeautifulSoup.

    Args:
        html_items: List of (path, content) tuples from iter_html_files.
        target_domain: The primary domain being mirrored (excluded from results).
        media_regex: Compiled regex matching media file extensions.

    Returns:
        Tuple of (unique external URLs, total HTML URLs scanned).
    """
    ext_urls: set[str] = set()
    url_count = 0
    progress = ProgressTracker(len(html_items))

    for _html_file, content in html_items:
        soup = BeautifulSoup(content, "lxml")

        for tag in soup.find_all(["img", "script", "link", "video", "audio", "source"]):
            for attr in ("src", "href", "data-src"):
                url = tag.get(attr)
                if not url:
                    continue

                url_count += 1

                if not url.startswith(("http://", "https://")):
                    continue

                try:
                    url_host = urlparse(url).hostname or ""
                    if url_host == target_domain:
                        continue
                except Exception:
                    continue

                if not media_regex.search(url):
                    continue

                normalized_url = url.split("?")[0]
                ext_urls.add(normalized_url)

        progress.tick()

    progress.finish()
    return ext_urls, url_count


def _scan_css_media(
    output_dir: Path,
    target_domain: str,
    media_regex: re.Pattern[str],
    css_url_pattern: re.Pattern[str],
) -> tuple[set[str], int]:
    """Scan CSS files for external media url() references.

    Args:
        output_dir: Path to the directory containing downloaded CSS files.
        target_domain: The primary domain being mirrored (excluded from results).
        media_regex: Compiled regex matching media file extensions.
        css_url_pattern: Compiled regex matching CSS url() references.

    Returns:
        Tuple of (unique external URLs, total CSS url() references scanned).
    """
    ext_urls: set[str] = set()
    css_url_count = 0

    for _css_file, raw_css in iter_css_files(output_dir):
        for match in css_url_pattern.finditer(raw_css):
            css_url_count += 1
            url = match.group(1)

            try:
                url_host = urlparse(url).hostname or ""
                if url_host == target_domain:
                    continue
            except Exception:
                continue

            if not media_regex.search(url):
                continue

            normalized_url = url.split("?")[0]
            ext_urls.add(normalized_url)

    return ext_urls, css_url_count


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

    css_url_pattern = re.compile(r'url\(\s*["\']?(https?://[^"\'\\)]+)["\']?\s*\)')

    extensions = settings.media_extensions
    escaped_exts = [re.escape(ext) for ext in extensions]
    media_regex = re.compile(rf"(?i)({'|'.join(escaped_exts)})(\?.*)?$")

    html_items = list(iter_html_files(output_dir))

    html_urls, url_count = _scan_html_media(html_items, target_domain, media_regex)
    css_urls, css_url_count = _scan_css_media(
        output_dir, target_domain, media_regex, css_url_pattern
    )

    ext_urls = html_urls | css_urls

    logger.info(
        "Scanned %d HTML URLs and %d CSS url() references, found %d unique external media URLs",
        url_count,
        css_url_count,
        len(ext_urls),
    )
    return ext_urls
