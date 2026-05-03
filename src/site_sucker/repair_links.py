"""External and internal URL rewriter for downloaded HTML and CSS files."""

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from site_sucker.file_iter import iter_html_files, iter_css_files
from site_sucker.paths import get_actual_save_path, url_to_filepath
from site_sucker.replacement_pipeline import ReplacementStep, run_replacement_pipeline


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


def _build_css_replacement_steps(
    css_dir: Path,
    output_dir: Path,
    url_map: dict[str, str],
) -> list[ReplacementStep]:
    """Build CSS replacement steps for a single CSS file.

    Args:
        css_dir: Directory containing the CSS file.
        output_dir: Root output directory.
        url_map: Mapping of external URLs to local filenames.

    Returns:
        List of replacement steps.
    """
    rel_from_root = css_dir.resolve().relative_to(output_dir.resolve())
    depth = len(rel_from_root.parts) if str(rel_from_root) != "." else 0
    prefix = "../" * depth

    css_steps = []

    # 1. Inline CSS @import statements to avoid CORS on file://
    def inline_imports(content: str) -> str:
        import_pattern = re.compile(r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\'](?:\s*\))?;')

        def inline_import(match: re.Match) -> str:
            import_path = match.group(1)

            # Skip external @import (http/https) - leave marker for later step
            if import_path.startswith(('http://', 'https://')):
                return f'/* External @import "{import_path}" stripped for offline use */'

            # Resolve relative import path
            try:
                import_file = css_dir / import_path

                if import_file.is_file():
                    try:
                        with open(import_file, "r", encoding="utf-8", errors="ignore") as f:
                            imported_content = f.read()

                        return f'/* Inlined from {import_path} */\n{imported_content}\n'
                    except (IOError, OSError) as e:
                        return f'/* @import "{import_path}" - READ ERROR: {e} */\n'
                else:
                    return f'/* @import "{import_path}" - FILE NOT FOUND */\n'
            except (ValueError, TypeError) as e:
                return f'/* @import "{import_path}" - PATH ERROR: {e} */\n'
            except Exception:
                return match.group(0)

        return import_pattern.sub(inline_import, content)

    css_steps.append(
        ReplacementStep(
            name="Inline CSS @import statements",
            pattern=inline_imports,
        )
    )

    # 2. Strip Google Fonts @import markers
    css_steps.append(
        ReplacementStep(
            name="Strip Google Fonts @import markers",
            pattern=re.compile(
                r'/\* External @import "https://fonts\.googleapis\.com/[^"]+" stripped for offline use \*/'
            ),
            replacement='/* Google Fonts @import stripped for offline use */',
        )
    )

    # 3. Replace mapped external CDN urls inside CSS (e.g. Google Fonts)
    for url, filename in url_map.items():
        rel_link = "../" * depth + f"images/{filename}"
        escaped_url = re.escape(url)
        pattern = re.compile(
            f'url\\(\\s*(["\']?)?{escaped_url}(?:\\?[^\\s"\'#>\\)]+)?\\1?\\s*\\)'
        )

        css_steps.append(
            ReplacementStep(
                name=f"Rewrite external CSS URL to local: {url[:50]}...",
                pattern=pattern,
                replacement=f'url(\\1?{rel_link}\\1?)',
            )
        )

    # 4. Strip external http/https url() references that weren't downloaded
    css_steps.append(
        ReplacementStep(
            name="Strip external url() references",
            pattern=re.compile(r'url\(\s*["\']?https?://[^"\'\\)]+["\']?\s*\)'),
            replacement='url("about:blank") /* External URL stripped for offline use */',
        )
    )

    # 5. Convert absolute local paths to relative paths
    css_steps.append(
        ReplacementStep(
            name="Convert absolute local paths to relative",
            pattern=re.compile(r'url\(\s*(["\']?)/([^"\'\)]*)\1\s*\)'),
            replacement=f'url(\\1{prefix}\\2\\1)',
        )
    )

    return css_steps


def _repair_html_links_from_content(
    html_file: Path,
    output_dir: Path,
    content: str,
    media_dir: Path,
    url_map: dict[str, str],
) -> bool:
    """Rewrite external URLs and strip CORS attributes in HTML file using BeautifulSoup.

    Args:
        html_file: Path to the HTML file.
        output_dir: Root output directory.
        content: HTML content string.
        media_dir: External media download directory.
        url_map: Mapping of external URLs to local filenames.

    Returns:
        True if file was modified, False otherwise.
    """
    # Parse with BeautifulSoup
    soup = BeautifulSoup(content, 'lxml')

    # Calculate relative path depth from this file to output root
    html_dir = html_file.parent
    try:
        rel_path = html_dir.resolve().relative_to(output_dir.resolve())
        depth = len(rel_path.parts) if str(rel_path) != "." else 0
    except ValueError:
        # html_dir is not relative to output_dir (shouldn't happen)
        depth = 0

    modified = False

    # Rewrite href and src attributes for mapped URLs
    for tag in soup.find_all(['link', 'script', 'img']):
        for attr in ('href', 'src'):
            url = tag.get(attr)
            if not url:
                continue

            # Check if this URL is in our map
            for original_url, filename in url_map.items():
                # Strip query string for comparison
                url_base = url.split('?')[0]
                if url_base == original_url or url == original_url:
                    # Build relative path to images directory
                    rel_link = "../" * depth + f"images/{filename}"
                    tag[attr] = rel_link
                    modified = True
                    break

    # Strip CORS-blocking attributes (integrity, crossorigin)
    for tag in soup.find_all(['link', 'script', 'img']):
        if tag.get('integrity'):
            del tag['integrity']
            modified = True
        if tag.get('crossorigin'):
            del tag['crossorigin']
            modified = True

    if modified:
        with open(html_file, "w", encoding="utf-8", newline="") as f:
            f.write(str(soup))

    return modified


def repair_external_links(
    output_dir: Path | str,
    media_dir: Path | str,
    external_urls: set[str],
    log_dir: Path | None = None,
) -> int:
    """Rewrite external CDN URLs in downloaded HTML to point to local copies.

    Uses BeautifulSoup for HTML files (URL rewriting + CORS attribute stripping).
    Uses regex pipeline for CSS files (@import inlining, absolute path conversion, external URL stripping).

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
        print("No external URLs to rewrite.")
        # Don't return early - we still need to process CSS for absolute paths

    print(f"\n[3/4] Rewriting external URLs to local paths...")

    # Build URL -> local filename mapping
    url_map = _build_url_map(media_dir, external_urls)

    if not url_map:
        print("No downloaded external files found on disk.")
        # Continue to process CSS for absolute paths even if no external URLs
    else:
        print(f"  Mapping {len(url_map)} external URLs to local files")

    # ── PART 1: Process HTML Files (BeautifulSoup) ────────────────────────────
    modified_count = 0

    for html_file, content in iter_html_files(output_dir):
        if _repair_html_links_from_content(html_file, output_dir, content, media_dir, url_map):
            modified_count += 1

    print(f"  Rewrote external links in {modified_count} HTML file(s)")

    # ── PART 2: Process CSS Files (Regex Pipeline) ─────────────────────────────
    css_modified_count = 0
    imports_inlined = 0
    external_fonts_stripped = 0
    external_urls_stripped = 0

    # Always process CSS files for absolute path conversion
    for css_file, css_content in iter_css_files(output_dir):
        css_dir = css_file.parent

        # Build replacement steps for this specific CSS file
        css_steps = _build_css_replacement_steps(
            css_dir, output_dir, url_map
        )

        # Run the replacement pipeline
        steps_applied = run_replacement_pipeline(
            css_file,
            css_steps,
            log_dir,
        )

        if steps_applied > 0:
            css_modified_count += 1

            # Count specific transformations for reporting
            # Note: run_replacement_pipeline already wrote the file, so we read it back
            try:
                with open(css_file, "r", encoding="utf-8", errors="ignore") as f:
                    updated_content = f.read()

                if 'Google Fonts @import stripped' in updated_content:
                    external_fonts_stripped += 1

                if 'External URL stripped for offline use' in updated_content:
                    external_urls_stripped += 1
            except (IOError, OSError):
                pass

    if css_modified_count > 0:
        print(f"  Processed {css_modified_count} CSS file(s)")
        if imports_inlined > 0:
            print(f"    - Inlined {imports_inlined} @import statement(s)")
        if external_fonts_stripped > 0:
            print(f"    - Stripped {external_fonts_stripped} external font @import(s)")
        if external_urls_stripped > 0:
            print(f"    - Neutralized {external_urls_stripped} external url() reference(s)")

    return modified_count


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


def repair_internal_links(
    output_dir: Path | str,
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
    output_dir = Path(output_dir)
    print(f"\n[*] Rewriting internal links to local files...")

    modified_count = 0

    for html_file, content in iter_html_files(output_dir):
        # Parse with BeautifulSoup
        soup = BeautifulSoup(content, 'lxml')

        # Calculate relative path depth from this file to output root
        html_dir = html_file.parent
        try:
            rel_path = html_dir.resolve().relative_to(output_dir.resolve())
            depth = len(rel_path.parts) if str(rel_path) != "." else 0
        except ValueError:
            # html_dir is not relative to output_dir (shouldn't happen)
            depth = 0

        # Construct the original base URL of this local HTML file
        try:
            rel_path_from_root = html_file.resolve().relative_to(output_dir.resolve()).as_posix()
        except ValueError:
            rel_path_from_root = ""
        base_url = f"https://{target_domain}/{rel_path_from_root}"

        modified = False

        # Rewrite all href attributes pointing to target_domain (for <a> tags)
        # Skip anchors, javascript, and mailto links by passing them to the helper
        for tag in soup.find_all("a", href=True):
            href = tag["href"]

            # Skip anchors, javascript, and mailto links
            if href.startswith(("#", "javascript:", "mailto:")):
                continue

            # Convert to absolute URL (handles relative links like /about_us.php)
            absolute_url = urljoin(base_url, href)

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
                tag["href"] = Path(rel_str).as_posix()
                modified = True
            except ValueError:
                continue

        # Rewrite internal resource URLs (img, script, link, video, audio, source)
        # This fixes images like <img src="/images/art/intro_amazon.jpg">
        if _rewrite_tag_urls(
            soup,
            tags=['img', 'script', 'link', 'video', 'audio', 'source'],
            attrs=('src', 'href'),
            base_url=base_url,
            target_domain=target_domain,
            output_dir=output_dir,
            html_file=html_file,
        ):
            modified = True

        if modified:
            with open(html_file, "w", encoding="utf-8", newline="") as f:
                f.write(str(soup))
            modified_count += 1

    print(f"  Rewrote internal links in {modified_count} HTML file(s)")
    return modified_count
