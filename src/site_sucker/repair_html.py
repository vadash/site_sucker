"""HTML link rewriting module for external and internal URLs."""

import logging
import os
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from site_sucker.file_iter import iter_html_files, write_if_changed
from site_sucker.paths import get_actual_save_path, relative_depth, url_to_filepath
from site_sucker.progress import ProgressTracker
from site_sucker.url_filter import extract_internal_urls

logger = logging.getLogger(__name__)


def _rewrite_tag_urls(
    soup: BeautifulSoup,
    tags: list[str],
    attrs: list[str],
    base_url: str,
    target_domain: str,
    output_dir: Path,
    html_file: Path,
) -> bool:
    """Rewrite URLs in specified tags and attributes to local file paths.

    Args:
        soup: BeautifulSoup object.
        tags: List of tag names to process.
        attrs: List of attribute names to check on each tag.
        base_url: Base URL of the HTML file.
        target_domain: Domain to filter URLs by.
        output_dir: Root output directory.
        html_file: Path to the HTML file being processed.

    Returns:
        True if any URLs were rewritten, False otherwise.
    """
    modified = False

    for tag in soup.find_all(tags):
        for attr in attrs:
            url = tag.get(attr)
            if not url:
                continue

            # Skip anchors, javascript, mailto, data URLs, and already-relative paths
            if url.startswith(("#", "javascript:", "mailto:", "data:", "../")):
                continue

            # Convert to absolute URL (handles relative links like /about_us.php)
            absolute_url = urljoin(base_url, url)

            # Parse URL to check hostname
            try:
                parsed = urlparse(absolute_url)
                if parsed.scheme not in ("http", "https"):
                    continue
                if parsed.hostname != target_domain:
                    continue
            except Exception:
                continue

            # Map URL to expected local file path
            expected_path = url_to_filepath(absolute_url, output_dir)

            # Resolve actual file (Python now saves files where we expect)
            actual_path = get_actual_save_path(expected_path)

            if not actual_path.exists():
                # File doesn't exist locally, leave link unchanged
                continue

            # Build relative path from html_file to actual_path using os.path.relpath
            try:
                # os.path.relpath can bridge across sibling directories using ../
                rel_str = os.path.relpath(actual_path, html_file.parent)
                tag[attr] = Path(rel_str).as_posix()
                modified = True
            except ValueError:
                continue

    return modified


def _strip_cors_attrs(soup: BeautifulSoup) -> bool:
    """Strip CORS-blocking attributes (integrity, crossorigin) from tags.

    Args:
        soup: BeautifulSoup object.

    Returns:
        True if any attributes were removed, False otherwise.
    """
    modified = False
    for tag in soup.find_all(["link", "script", "img"]):
        if tag.get("integrity"):
            del tag["integrity"]
            modified = True
        if tag.get("crossorigin"):
            del tag["crossorigin"]
            modified = True
    return modified


def rewrite_external_html_links(
    html_file: Path,
    output_dir: Path,
    content: str,
    url_map: dict[str, str],
) -> bool:
    """Rewrite external URLs and strip CORS attributes in HTML file using BeautifulSoup.

    Args:
        html_file: Path to the HTML file.
        output_dir: Root output directory.
        content: HTML content string.
        url_map: Mapping of external URLs to local filenames.

    Returns:
        True if file was modified, False otherwise.
    """
    # Parse with BeautifulSoup
    soup = BeautifulSoup(content, "lxml")

    # Calculate relative path depth from this file to output root
    depth = relative_depth(html_file, output_dir)

    modified = False

    # Rewrite href and src attributes for mapped URLs
    for tag in soup.find_all(["link", "script", "img"]):
        for attr in ("href", "src"):
            url = tag.get(attr)
            if not url:
                continue

            # Check if this URL is in our map
            for original_url, filename in url_map.items():
                # Strip query string for comparison
                url_base = url.split("?")[0]
                if url_base == original_url or url == original_url:
                    # Build relative path to images directory
                    rel_link = "../" * depth + f"images/{filename}"
                    tag[attr] = rel_link
                    modified = True
                    break

    # Strip CORS-blocking attributes
    if _strip_cors_attrs(soup):
        modified = True

    if modified:
        write_if_changed(html_file, content, str(soup))

    return modified


def rewrite_internal_html_links(
    output_dir: Path,
    target_domain: str,
) -> int:
    """Rewrite internal HTML-to-HTML links to point to local files (for resume mode).

    When using resume mode, wget doesn't run with --convert-links, so internal
    links still point to https:// URLs. This function rewrites them to relative
    local paths using BeautifulSoup.

    Args:
        output_dir: Path to the directory containing downloaded files.
        target_domain: The primary domain being mirrored (used to identify internal links).

    Returns:
        Number of HTML files modified.
    """
    logger.info("[*] Rewriting internal links to local files...")

    modified_count = 0
    html_items = list(iter_html_files(output_dir))
    progress = ProgressTracker(len(html_items))

    for html_file, content in html_items:
        # Parse with BeautifulSoup
        soup = BeautifulSoup(content, "lxml")

        # Construct the original base URL of this local HTML file
        try:
            rel_path_from_root = html_file.resolve().relative_to(output_dir.resolve()).as_posix()
        except ValueError:
            rel_path_from_root = ""
        base_url = f"https://{target_domain}/{rel_path_from_root}"

        modified = False

        # Get all internal navigation URLs (already filtered)
        nav_urls = extract_internal_urls(soup, base_url, target_domain)

        # Rewrite <a> tags whose href matches a discovered internal URL
        for tag in soup.find_all("a", href=True):
            href = tag["href"]

            # Skip anchors, javascript, and mailto links
            if href.startswith(("#", "javascript:", "mailto:")):
                continue

            # Convert to absolute URL (handles relative links like /about_us.php)
            absolute_url = urljoin(base_url, href)

            # Only process URLs that were extracted as internal links
            if absolute_url.split("#")[0] not in nav_urls:
                continue

            # Map URL to expected local file path
            expected_path = url_to_filepath(absolute_url, output_dir)

            # Resolve actual file (Python now saves files where we expect)
            actual_path = get_actual_save_path(expected_path)

            if not actual_path.exists():
                # File doesn't exist locally, leave link unchanged
                continue

            # Build relative path from html_file to actual_path using os.path.relpath
            try:
                # os.path.relpath can bridge across sibling directories using ../
                rel_str = os.path.relpath(actual_path, html_file.parent)
                tag["href"] = Path(rel_str).as_posix()
                modified = True
            except ValueError:
                continue

        # Rewrite internal resource URLs (img, script, link, video, audio, source)
        # This fixes images like <img src="/images/art/intro_amazon.jpg">
        if _rewrite_tag_urls(
            soup,
            tags=["img", "script", "link", "video", "audio", "source"],
            attrs=["src", "href"],
            base_url=base_url,
            target_domain=target_domain,
            output_dir=output_dir,
            html_file=html_file,
        ):
            modified = True

        if modified:
            write_if_changed(html_file, content, str(soup))
            modified_count += 1

        progress.tick()

    progress.finish()

    logger.info("  Rewrote internal links in %d HTML file(s)", modified_count)
    return modified_count
