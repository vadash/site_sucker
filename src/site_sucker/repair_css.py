"""CSS processing module for @import inlining, path conversion, and URL stripping."""

import logging
import re
from pathlib import Path

from site_sucker.file_iter import iter_css_files
from site_sucker.replacement_pipeline import ReplacementStep, run_replacement_pipeline

logger = logging.getLogger(__name__)


def build_css_replacement_steps(
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
    import_stack: set[str] = set()

    def inline_imports(content: str) -> str:
        import_pattern = re.compile(r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\'](?:\s*\))?;')

        def inline_import(match: re.Match[str]) -> str:
            import_path = match.group(1)

            # Skip external @import (http/https) - leave marker for later step
            if import_path.startswith(('http://', 'https://')):
                return f'/* External @import "{import_path}" stripped for offline use */'

            # Resolve relative import path
            try:
                import_file = css_dir / import_path

                if not import_file.exists():
                    return f'/* @import "{import_path}" - FILE NOT FOUND */\n'

                with open(import_file, encoding='utf-8', errors='ignore') as f:
                    imported_content = f.read()

                # Prevent infinite recursion with depth tracking
                if import_path in import_stack:
                    return f'/* @import "{import_path}" - CIRCULAR REFERENCE SKIPPED */\n'

                if len(import_stack) >= 10:
                    return f'/* @import "{import_path}" - MAX DEPTH REACHED */\n'

                # Recursively inline the imported CSS
                import_stack.add(import_path)
                inlined = inline_imports(imported_content)
                import_stack.remove(import_path)

                return f'/* INLINED: {import_path} */\n{inlined}'

            except OSError as e:
                return f'/* @import "{import_path}" - READ ERROR: {e} */\n'
            except (ValueError, TypeError) as e:
                return f'/* @import "{import_path}" - PATH ERROR: {e} */\n'
            except Exception:
                return match.group(0)
            import_path = match.group(1)

            # Skip external @import (http/https) - leave marker for later step
            if import_path.startswith(('http://', 'https://')):
                return f'/* External @import "{import_path}" stripped for offline use */'

            # Resolve relative import path
            try:
                import_file = css_dir / import_path

                if import_file.is_file():
                    try:
                        with open(import_file, encoding="utf-8", errors="ignore") as f:
                            imported_content = f.read()

                        return f'/* Inlined from {import_path} */\n{imported_content}\n'
                    except OSError as e:
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


def process_css_files(
    output_dir: Path,
    url_map: dict[str, str],
    log_dir: Path | None = None,
) -> int:
    """Process CSS files for @import inlining, path conversion, and URL stripping.

    Args:
        output_dir: Root output directory containing CSS files.
        url_map: Mapping of external URLs to local filenames.
        log_dir: Optional directory to log failed replacements. If None, failures are reverted but not logged.

    Returns:
        Number of CSS files modified.
    """
    css_modified_count = 0
    imports_inlined = 0
    external_fonts_stripped = 0
    external_urls_stripped = 0

    # Always process CSS files for absolute path conversion
    for css_file, _css_content in iter_css_files(output_dir):
        css_dir = css_file.parent

        # Build replacement steps for this specific CSS file
        css_steps = build_css_replacement_steps(
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
                with open(css_file, encoding="utf-8", errors="ignore") as f:
                    updated_content = f.read()

                if 'Google Fonts @import stripped' in updated_content:
                    external_fonts_stripped += 1

                if 'External URL stripped for offline use' in updated_content:
                    external_urls_stripped += 1
            except OSError:
                pass

    if css_modified_count > 0:
        logger.info("  Processed %d CSS file(s)", css_modified_count)
        if imports_inlined > 0:
            logger.info("    - Inlined %d @import statement(s)", imports_inlined)
        if external_fonts_stripped > 0:
            logger.info("    - Stripped %d external font @import(s)", external_fonts_stripped)
        if external_urls_stripped > 0:
            logger.info("    - Neutralized %d external url() reference(s)", external_urls_stripped)

    return css_modified_count
