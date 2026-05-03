"""External and internal URL rewriter for downloaded HTML and CSS files.

This module orchestrates HTML and CSS link rewriting by delegating to specialized modules:
- repair_html: BeautifulSoup-based HTML rewriting (external and internal links)
- repair_css: Regex-pipeline CSS processing (@import inlining, path conversion, URL stripping)
"""

import logging
from pathlib import Path

from site_sucker.file_iter import iter_html_files
from site_sucker.progress import ProgressTracker
from site_sucker.repair_css import process_css_files
from site_sucker.repair_html import rewrite_external_html_links, rewrite_internal_html_links

logger = logging.getLogger(__name__)


def _build_url_map(
    media_dir: Path,
    external_urls: set[str],
) -> dict[str, str]:
    """Build URL -> local filename mapping for downloaded media files.

    Args:
        media_dir: Directory containing downloaded external media.
        external_urls: Set of external URLs that were downloaded.

    Returns:
        Dictionary mapping URLs to local filenames.
    """
    from urllib.parse import urlparse

    url_map = {}
    for url in external_urls:
        try:
            parsed = urlparse(url)
            filename = Path(parsed.path).name
            if filename:
                local_path = media_dir / filename
                if local_path.is_file():
                    url_map[url] = filename
        except Exception:
            pass
    return url_map


def repair_external_links(
    output_dir: Path | str,
    media_dir: Path | str,
    external_urls: set[str],
    log_dir: Path | None = None,
) -> int:
    """Rewrite external CDN URLs in downloaded HTML to point to local copies.

    Orchestrates HTML and CSS link rewriting by delegating to specialized modules:
    - repair_html.rewrite_external_html_links: BeautifulSoup-based HTML rewriting
    - repair_css.process_css_files: Regex-pipeline CSS processing

    Args:
        output_dir: Path to the directory containing downloaded files.
        media_dir: Path to the external media download directory.
        external_urls: Set of external URLs that were downloaded.
        log_dir: Optional directory to log failed replacements. If None, failures are reverted but not logged.

    Returns:
        Number of HTML files modified.
    """
    output_dir = Path(output_dir)
    media_dir = Path(media_dir)
    log_dir = Path(log_dir) if log_dir else None

    if not external_urls:
        logger.info("No external URLs to rewrite.")
        # Don't return early - we still need to process CSS for absolute paths

    logger.info("[3/4] Rewriting external URLs to local paths...")

    # Build URL -> local filename mapping
    url_map = _build_url_map(media_dir, external_urls)

    if not url_map:
        logger.info("No downloaded external files found on disk.")
        # Continue to process CSS for absolute paths even if no external URLs
    else:
        logger.info("  Mapping %d external URLs to local files", len(url_map))

    # ── PART 1: Process HTML Files (BeautifulSoup) ────────────────────────────
    modified_count = 0
    html_items = list(iter_html_files(output_dir))
    progress = ProgressTracker(len(html_items))

    for html_file, content in html_items:
        if rewrite_external_html_links(html_file, output_dir, content, url_map):
            modified_count += 1
        progress.tick()

    progress.finish()
    logger.info("  Rewrote external links in %d HTML file(s)", modified_count)

    # ── PART 2: Process CSS Files (Regex Pipeline) ─────────────────────────────
    process_css_files(output_dir, url_map, log_dir)

    return modified_count


def repair_internal_links(
    output_dir: Path | str,
    target_domain: str,
) -> int:
    """Rewrite internal HTML-to-HTML links to point to local files (for resume mode).

    Orchestrates internal link rewriting by delegating to repair_html module.

    When using resume mode, wget doesn't run with --convert-links, so internal
    links still point to https:// URLs. This function rewrites them to relative
    local paths using BeautifulSoup.

    Args:
        output_dir: Path to the directory containing downloaded files.
        target_domain: The primary domain being mirrored (used to identify internal links).

    Returns:
        Number of HTML files modified.
    """
    output_dir = Path(output_dir)
    return rewrite_internal_html_links(output_dir, target_domain)
