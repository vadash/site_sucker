# AI Agents Development Guide

This document provides guidance for AI agents (including Factory Droids) working on the SiteSucker codebase.

## Architecture Overview

SiteSucker is a modular Python application that mirrors websites for offline use. It uses a 4-pass pipeline:

1. **Pass 1**: Wget-based full site mirror (or Python BFS crawler in `--resume` mode)
2. **Pass 2**: Parallel external media download
3. **Pass 3**: External URL → local path rewriting
4. **Pass 4**: Online-only resource stripping

### Resume Mode (--resume flag)

When resuming an interrupted download, SiteSucker can use a Python-based BFS crawler instead of wget's built-in spidering:

- **Why**: Wget's `-nc` (no-clobber) + `--convert-links` are incompatible. With `-nc`, wget skips existing files but can't discover links inside them, so the crawl stops. Without `-nc`, wget re-checks every file against the server, triggering 429 bot protection.
- **How**: Python manages the entire crawl state (visited set, depth tracking, link discovery) and uses wget only as a single-file downloader (`--level=1`).
- **Benefits**: Bypasses 429 bot protection by only hitting the server for genuinely missing pages. Existing files are parsed locally for links at full speed.

## Key Modules

### Core Pipeline

- **`mirror.py`**: Orchestrates the entire 4-pass pipeline
  - Entry point: `invoke_site_mirror()`
  - Returns: List of failed URLs
  - Creates `output_dir/logs/` for replacement error logging

- **`wget.py`**: Wget binary wrapper
  - `get_wget_path()`: Resolves `bin/wget.exe`
  - `build_wget_args()`: Constructs argument arrays from settings

- **`media.py`**: External media scanner (BeautifulSoup for HTML, regex for CSS)
  - `get_external_media()`: Parses HTML/CSS for external media URLs
  - HTML: Uses BeautifulSoup to scan href/src attributes on relevant tags
  - CSS: Uses regex to scan url() references
  - Handles deduplication and URL normalization

### Post-Processing & Replacement Pipeline

- **`replacement_pipeline.py`**: Unified replacement engine with validation (CSS-only)
  - `ReplacementStep`: Dataclass for defining regex/callable replacements
  - `run_replacement_pipeline()`: Executes steps with automatic rollback on validation failure
  - Validates CSS content after each replacement (checks for non-empty content)
  - Logs failed replacements to `logs/NNNNN/` with file snapshot and pattern details
  - **Key feature**: Prevents regex bugs from corrupting CSS files
  - **Note**: HTML processing now uses BeautifulSoup, not this pipeline

- **`repair_links.py`**: URL rewriter (BeautifulSoup for HTML, pipeline for CSS)
  - `repair_external_links()`: Rewrites external URLs to local paths
  - `repair_internal_links()`: Rewrites internal HTML-to-HTML links to local paths (for resume mode)
  - HTML files: Uses BeautifulSoup for safe DOM manipulation (URL rewriting + CORS attribute stripping)
  - CSS files: Uses regex pipeline for @import inlining, absolute path conversion, and external URL stripping
  - Each CSS replacement step validated automatically

- **`repair_offline.py`**: Offline optimizer (BeautifulSoup-based)
  - `repair_offline_html()`: Removes online-only resources using BeautifulSoup DOM operations
  - Handles MediaWiki (load.php), phpBB, tracking scripts, preconnect/dns-prefetch hints
  - Injects fallback CSS
  - All HTML tag removal uses `find_all()` + `.decompose()` — safe, cannot corrupt HTML structure
  - Inline JavaScript cleanup (GA calls, push calls) uses regex on serialized output

### Configuration & Reporting

- **`settings.py`**: Configuration management
  - `load_settings()`: Loads and merges settings.jsonc (with fallback to settings.json)
  - `_strip_jsonc_comments()`: Removes `//` and `/* */` comments from JSONC files
  - `merge_cli_overrides()`: Applies CLI parameter overrides

- **`report.py`**: Report generation
  - `write_site_report()`: Generates download summary
  - Creates failures.log for failed URLs

- **`validate_html.py`**: HTML integrity checker (BeautifulSoup-based)
  - `validate_html_files()`: Detects truncated/corrupt downloads (directory scan)
  - `validate_html_string()`: Validates single HTML content string using BeautifulSoup
  - Checks for missing `<head>`, `<body>` elements and empty bodies
  - Runs after wget pass 1, before post-processing

### Resume Mode

- **`resume.py`**: Python-based BFS crawler (bypasses 429 bot protection)
  - `crawl_loop()`: Main BFS crawl loop that replaces wget's built-in spidering
  - `url_to_filepath()`: Converts URLs to expected local file paths (mimics wget's `--restrict-file-names=windows`)
  - `file_exists_on_disk()`: Checks if file exists (with or without `.html` suffix for wget's `--adjust-extension` behavior)
  - `resolve_local_file()`: Returns actual file path that exists on disk
  - `discover_links()`: Extracts internal links from HTML using BeautifulSoup, applies reject patterns
  - **Key feature**: Wget becomes a single-file downloader (`--level=1`), Python manages all crawl state
  - **Solves**: The Catch-22 of `-nc` + `--convert-links` incompatibility for resume
  - **Bypasses**: 429 bot protection by only hitting the server for genuinely missing pages

### CLI

- **`__main__.py`**: CLI entry point
  - Parses arguments (argparse)
  - Handles interactive prompts
  - Calls `mirror.invoke_site_mirror()`

## Testing Strategy

### Test Files

- **`conftest.py`**: Shared fixtures (sample HTML, CSS, settings)
- **`test_*.py`**: Module-specific unit tests

### Running Tests

```bash
# Run all tests
uv run pytest

# With coverage
uv run pytest --cov=site_sucker

# Specific module
uv run pytest tests/test_media.py
```

### Test Patterns

- Use `tmp_path` fixture for file operations
- Mock subprocess calls in integration tests
- Test both success and failure paths
- Verify file content changes, not just return codes

## Common Tasks

### Adding New URL Patterns

When adding new reject patterns or URL handling:

1. Update `settings.jsonc` with the pattern (add inline comment explaining what it does)
2. Add test case to `test_wget.py` (for arg building)
3. Add test case to relevant module (`test_media.py`, `test_repair_offline.py`)

### Extending the Pipeline

To add a new processing pass:

1. Create new function in appropriate module (or new module)
2. Wire it up in `mirror.py::invoke_site_mirror()`
3. Add comprehensive tests
4. Update this AGENTS.md

### Fixing Bugs

When fixing bugs:

1. Add failing test case first
2. Fix the bug
3. Verify all tests pass
4. Check for similar issues in other modules

## Code Conventions

### Python Style

- Follow PEP 8
- Use type hints for function signatures
- Docstrings for all public functions
- Maximum line length: 100 (soft)

### Error Handling

- Raise `FileNotFoundError` for missing wget binary
- Return empty lists/sets for "not found" scenarios
- Use `try/except` for file operations
- Print warnings for non-critical issues

### Path Handling

- Use `pathlib.Path` for all path operations
- Resolve to absolute paths before file operations
- Use `Path.expanduser()` for user paths
- Cross-platform: use `Path` methods, not string concatenation

## Dependencies

- **Runtime dependencies**:
  - `beautifulsoup4>=4.12.0`: HTML parsing and DOM manipulation
  - `lxml>=5.0.0`: Fast HTML parser for BeautifulSoup
- **Dev dependencies**: `pytest`, `pytest-cov` (for testing)
- **Binary**: `wget.exe` in `bin/` directory

## Platform Notes

**Windows 11 Only**: This implementation is Windows-specific.

- Uses `wget.exe` binary (not Linux wget)
- Path handling assumes Windows separators
- No cross-platform testing required

### Running Python

**System `python`/`python3` does NOT work** — Windows App Execution Aliases intercept it and show a Store prompt.

**Use `uv run`** for all commands:
- `uv run python -m site_sucker` - Run the tool
- `uv run pytest` - Run tests
- `uv run site-sucker` - Run the installed CLI script

The `uv sync` command creates `.venv` and installs the project in editable mode. The `[tool.uv] no-build = false` setting in `pyproject.toml` allows building the project even if your global uv config has `no-build = true`.

**Temp files**: `curl -o /tmp/file` on Windows Git Bash saves to `C:/Users/<user>/AppData/Local/Temp/file`, not `/tmp/`. Use the Windows path when reading from Python.

## Settings File Schema

Settings are stored in `settings.jsonc` (JSON with Comments) format. The file supports inline `//` comments and block `/* */` comments for documentation.

```jsonc
{
  // HTTP client settings
  "UserAgent": "Mozilla/5.0 ...",
  "Timeout": 15,          // seconds
  "Retries": 3,

  // Crawl behavior
  "MaxDepth": 0,          // 0 = unlimited
  "ParallelDownloads": 2,
  "WaitBetweenRequests": 1.5,  // seconds between requests

  // Output settings
  "OutputRoot": "./downloads",

  // URL rejection patterns (matched as substrings)
  "RejectPatterns": [
    "action=",            // MediaWiki: edit/history pages
    "oldid=",             // MediaWiki: old revisions
    // ... more patterns with inline comments
  ],

  // Domains to block entirely
  "RejectDomains": ["analytics."],

  // File extensions for media download pass
  "MediaExtensions": [".png", ".jpg", ...]
}
```

**Note**: The loader falls back to `settings.json` if `settings.jsonc` is not found (for backwards compatibility).

## CLI Interface

```bash
site-sucker [url] [options]

Options:
  -o, --output-dir DIR     Output directory
  -s, --settings PATH      Custom settings.jsonc (default: ./settings.jsonc)
  -d, --depth INT          Max recursion depth
  -p, --parallel INT       Parallel downloads count
```

## Debugging

### Enable Verbose Output

The tool doesn't have a verbose flag, but you can:

1. Check `bin/` directory for wget logs
2. Look for printed status messages
3. Examine `failures.log` in output directory

### Common Issues

- **wget not found**: Ensure `bin/wget.exe` exists
- **Permission errors**: Run with appropriate permissions
- **Rate limiting**: Increase `WaitBetweenRequests`
- **Large downloads**: Monitor disk space

## Replacement Pipeline & Safety

### Unified Replacement Architecture (CSS-only)

**HTML processing**: Uses BeautifulSoup DOM operations — safe by design, cannot corrupt HTML structure.

**CSS processing**: All regex replacements go through `replacement_pipeline.py`:

1. Each replacement is a `ReplacementStep` with name, pattern, and replacement
2. Steps run sequentially; content validated after each change
3. On validation failure: change reverted, logged to `logs/NNNNN/`, pipeline continues
4. After all steps: final content written (only if modified)

CSS operations include:
- @import inlining (to avoid CORS on file://)
- Absolute path conversion (url('/...') → url('../...'))
- External URL stripping (url('https://...') → url('about:blank'))

### Log Directory Structure

Failed CSS replacements create:
```
<output_dir>/logs/
  00001/
    style.css         # File content at point of failure
    pattern.txt       # Step name, regex pattern, validation error
  00002/
    theme.css
    pattern.txt
```

This provides a debug trail for fixing problematic regexes without corrupting CSS files.

Note: HTML replacements no longer create log entries since BeautifulSoup operations are inherently safe.

## Future Enhancements

Potential areas for improvement:

1. **Progress bars**: Add `tqdm` for download progress
2. **Resume support**: Track completed URLs for resume capability
3. **Different output formats**: PDF, single-file HTML
4. **Content filtering**: Regex-based content inclusion/exclusion

## Contact & Support

For questions or issues:
- Check existing tests for usage patterns
- Review this AGENTS.md
- Examine the original PowerShell implementation in `docs/`
