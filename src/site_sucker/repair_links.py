"""External URL rewriter for downloaded HTML and CSS files."""

import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from site_sucker.replacement_pipeline import ReplacementStep, run_replacement_pipeline


def repair_external_links(
    output_dir: Path | str,
    media_dir: Path | str,
    external_urls: set[str],
    log_dir: Path | None = None,
) -> int:
    """Rewrite external CDN URLs in downloaded HTML to point to local copies.

    Scans HTML files to replace absolute CDN URLs with relative paths to local files.
    Strips crossorigin/integrity attributes to prevent local file:// CORS errors.
    Also scans CSS files to convert absolute paths (url('/...')) to relative paths.

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
        html_dir = html_file.parent
        rel_path = Path(html_dir).relative_to(output_dir)
        depth = len(rel_path.parts) if str(rel_path) != "." else 0

        # Build replacement steps for this specific file
        html_steps = []

        # Add URL rewriting steps for each mapped URL
        for url, filename in url_map.items():
            rel_link = "../" * depth + f"images/{filename}"
            escaped_url = re.escape(url)
            # Match exact URL (with optional querystring) strongly bounded by quotes
            pattern_str = f'(["\']){escaped_url}(?:\\?[^\\s"\'#>]+)?\\1'
            pattern = re.compile(pattern_str)

            html_steps.append(
                ReplacementStep(
                    name=f"Rewrite external URL to local: {url[:50]}...",
                    pattern=pattern,
                    replacement=f'\\1{rel_link}\\1',
                )
            )

        # Add CORS-stripping steps (always applied at the end)
        html_steps.extend([
            ReplacementStep(
                name="Strip integrity attribute",
                pattern=re.compile(r'(?i)\s+integrity=(["\']).*?\1'),
                replacement='',
            ),
            ReplacementStep(
                name="Strip crossorigin attribute with value",
                pattern=re.compile(r'(?i)\s+crossorigin=(["\']).*?\1'),
                replacement='',
            ),
            ReplacementStep(
                name="Strip standalone crossorigin attribute",
                pattern=re.compile(r'(?i)\s+crossorigin\b'),
                replacement='',
            ),
        ])

        # Run the replacement pipeline
        steps_applied = run_replacement_pipeline(
            html_file,
            html_steps,
            log_dir,
        )

        if steps_applied > 0:
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
        css_dir = css_file.parent
        rel_from_root = Path(css_dir).relative_to(output_dir)
        depth = len(rel_from_root.parts) if str(rel_from_root) != "." else 0
        prefix = "../" * depth

        # Build replacement steps for this specific CSS file
        css_steps = []

        # 1. Inline CSS @import statements to avoid CORS on file://
        def inline_imports(content: str) -> str:
            nonlocal imports_inlined
            import_pattern = re.compile(r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\'](?:\s*\))?;')

            def inline_import(match: re.Match) -> str:
                nonlocal imports_inlined
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

                            imports_inlined += 1
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

        # Run the replacement pipeline
        steps_applied = run_replacement_pipeline(
            css_file,
            css_steps,
            log_dir,
        )

        if steps_applied > 0:
            css_modified_count += 1

            # Count specific transformations for reporting
            try:
                with open(css_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if 'Google Fonts @import stripped' in content:
                    external_fonts_stripped += 1

                if 'External URL stripped for offline use' in content:
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
