"""External URL rewriter for downloaded HTML and CSS files."""

import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


def repair_external_links(
    output_dir: Path | str,
    media_dir: Path | str,
    external_urls: set[str],
) -> int:
    """Rewrite external CDN URLs in downloaded HTML to point to local copies.

    Scans HTML files to replace absolute CDN URLs with relative paths to local files.
    Strips crossorigin/integrity attributes to prevent local file:// CORS errors.
    Also scans CSS files to convert absolute paths (url('/...')) to relative paths.

    Args:
        output_dir: Path to the directory containing downloaded files.
        media_dir: Path to the external media download directory.
        external_urls: Set of external URLs that were downloaded.

    Returns:
        Number of HTML files modified.
    """
    output_dir = Path(output_dir)
    media_dir = Path(media_dir)

    if not external_urls:
        print("No external URLs to rewrite.")
        # Don't return early - we still need to process CSS for absolute paths

    print(f"\n[3/4] Rewriting external URLs to local paths...")

    # Build URL -> local filename mapping
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

    if not url_map:
        print("No downloaded external files found on disk.")
        # Continue to process CSS for absolute paths even if no external URLs
    else:
        print(f"  Mapping {len(url_map)} external URLs to local files")

    # ── PART 1: Process HTML Files ──────────────────────────────────────────
    html_files = list(output_dir.rglob("*.html")) + list(output_dir.rglob("*.htm"))
    modified_count = 0

    for html_file in html_files:
        try:
            with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        except IOError:
            continue

        if not raw:
            continue

        original = raw
        modified = False
        html_dir = html_file.parent

        for url, filename in url_map.items():
            local_path = media_dir / filename
            rel_path = Path(html_dir).relative_to(output_dir)
            depth = len(rel_path.parts) if str(rel_path) != "." else 0
            rel_link = "../" * depth + f"images/{filename}"

            escaped_url = re.escape(url)
            # Match exact URL (with optional querystring) strongly bounded by quotes
            pattern = f'(["\']){escaped_url}(?:\\?[^\\s"\'#>]+)?\\1'

            if re.search(pattern, raw):
                raw = re.sub(pattern, f'\\1{rel_link}\\1', raw)
                modified = True

        if modified:
            # Aggressively strip integrity and crossorigin to prevent browser CORS blocking on file://
            raw = re.sub(r'(?i)\s+integrity=(["\']).*?\1', '', raw)
            raw = re.sub(r'(?i)\s+crossorigin=(["\']).*?\1', '', raw)
            raw = re.sub(r'(?i)\s+crossorigin\b', '', raw)

            with open(html_file, "w", encoding="utf-8", newline="") as f:
                f.write(raw)
            modified_count += 1

    print(f"  Rewrote external links in {modified_count} HTML file(s)")

    # ── PART 2: Process CSS Files (Fix Absolute Paths, Inline @import, Strip External) ─────
    css_files = list(output_dir.rglob("*.css"))
    css_modified_count = 0
    imports_inlined = 0
    external_fonts_stripped = 0
    external_urls_stripped = 0

    # Always process CSS files for absolute path conversion
    for css_file in css_files:
        try:
            with open(css_file, "r", encoding="utf-8", errors="ignore") as f:
                raw_css = f.read()
        except IOError:
            continue

        if not raw_css:
            continue

        original_css = raw_css
        modified_css = False
        css_dir = css_file.parent

        # 1. Inline CSS @import statements to avoid CORS on file://
        # Match: @import url("path.css"); @import 'path.css'; @import "path.css";
        import_pattern = re.compile(r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\'](?:\s*\))?;')

        def inline_import(match: re.Match) -> str:
            nonlocal modified_css, imports_inlined
            import_path = match.group(1)

            # Skip external @import (http/https) - these will be stripped separately
            # Return a marker comment so google_fonts_pattern can find it
            if import_path.startswith(('http://', 'https://')):
                modified_css = True
                return f'/* External @import "{import_path}" stripped for offline use */'

            # Resolve relative import path
            try:
                # Import path is relative to the CSS file
                import_file = css_dir / import_path

                if import_file.is_file():
                    try:
                        with open(import_file, "r", encoding="utf-8", errors="ignore") as f:
                            imported_content = f.read()

                        imports_inlined += 1
                        modified_css = True
                        return f'/* Inlined from {import_path} */\n{imported_content}\n'
                    except (IOError, OSError) as e:
                        # File exists but can't be read
                        return f'/* @import "{import_path}" - READ ERROR: {e} */\n'
                else:
                    # Import file not found - leave warning comment
                    modified_css = True
                    return f'/* @import "{import_path}" - FILE NOT FOUND */\n'
            except (ValueError, TypeError) as e:
                # Path construction error
                modified_css = True
                return f'/* @import "{import_path}" - PATH ERROR: {e} */\n'
            except Exception:
                # Any other error - leave original to be safe
                return match.group(0)

        raw_css = import_pattern.sub(inline_import, raw_css)

        # 2. Strip Google Fonts @import (e.g., @import url("https://fonts.googleapis.com/..."))
        # Note: This runs AFTER inline_import, which already left a comment marker
        # We now replace those marker comments with a standard message
        google_fonts_comment_pattern = re.compile(r'/\* External @import "https://fonts\.googleapis\.com/[^"]+" stripped for offline use \*/')
        if google_fonts_comment_pattern.search(raw_css):
            raw_css = google_fonts_comment_pattern.sub('/* Google Fonts @import stripped for offline use */', raw_css)
            external_fonts_stripped += 1
            modified_css = True

        # 3. Replace mapped external CDN urls inside CSS (e.g. Google Fonts)
        for url, filename in url_map.items():
            local_path = media_dir / filename
            rel_path = Path(css_dir).relative_to(output_dir)
            depth = len(rel_path.parts) if str(rel_path) != "." else 0
            rel_link = "../" * depth + f"images/{filename}"

            escaped_url = re.escape(url)
            pattern = f'url\\(\\s*(["\']?)?{escaped_url}(?:\\?[^\\s"\'#>\\)]+)?\\1?\\s*\\)'

            if re.search(pattern, raw_css):
                raw_css = re.sub(pattern, f'url(\\1?{rel_link}\\1?)', raw_css)
                modified_css = True

        # 4. Strip external http/https url() references that weren't downloaded
        # These cause timeouts when opening HTML locally
        external_url_pattern = re.compile(r'url\(\s*["\']?https?://[^"\'\\)]+["\']?\s*\)')
        if external_url_pattern.search(raw_css):
            raw_css = external_url_pattern.sub('url("about:blank") /* External URL stripped for offline use */', raw_css)
            external_urls_stripped += 1
            modified_css = True

        # 5. Convert absolute local paths to relative paths
        rel_from_root = Path(css_dir).relative_to(output_dir)
        depth = len(rel_from_root.parts) if str(rel_from_root) != "." else 0
        prefix = "../" * depth

        # Regex match url('/path...') avoiding protocol-relative //paths
        abs_url_pattern = r'url\(\s*(["\']?)/([^"\'\)]*)\1\s*\)'
        if re.search(abs_url_pattern, raw_css):
            raw_css = re.sub(abs_url_pattern, f'url(\\1{prefix}\\2\\1)', raw_css)
            modified_css = True

        if modified_css:
            with open(css_file, "w", encoding="utf-8", newline="") as f:
                f.write(raw_css)
            css_modified_count += 1

    if css_modified_count > 0:
        print(f"  Processed {css_modified_count} CSS file(s)")
        if imports_inlined > 0:
            print(f"    - Inlined {imports_inlined} @import statement(s)")
        if external_fonts_stripped > 0:
            print(f"    - Stripped {external_fonts_stripped} external font @import(s)")
        if external_urls_stripped > 0:
            print(f"    - Neutralized {external_urls_stripped} external url() reference(s)")

    return modified_count
