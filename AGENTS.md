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

- **`mirror.py`**: Orchestrates the entire 4-pass pipeline (simplified)
  - Entry point: `invoke_site_mirror()`
  - Returns: List of failed URLs
  - Creates `output_dir/logs/` for replacement error logging
  - Uses `CrawlerBase` abstraction for mode-agnostic crawling
  - **Note**: Pass 2 (external media download) extracted to `download.py`

- **`download.py`**: External media downloader (extracted from mirror.py)
  - `download_external_media()`: Downloads external URLs in parallel batches
  - Uses ThreadPoolExecutor for concurrent wget subprocess calls
  - Returns list of failed URLs for retry/failure logging
  - Fully testable with mocked subprocess calls

- **`crawler.py`**: Unified crawler abstraction
  - `CrawlerBase`: Abstract base class for crawler implementations
  - `WgetCrawler`: Wget-based full site mirroring (default mode)
  - `BFSCrawler`: Python-based BFS crawler for `--resume` mode
  - `CrawlResult`: Dataclass containing failed URLs and internal link repair flag
  - Enables pipeline to be mode-agnostic (wget vs. resume)

- **`wget.py`**: Wget binary wrapper
  - `get_wget_path()`: Resolves `bin/wget.exe`
  - `build_wget_args()`: Constructs argument arrays from settings
  - `get_clean_env()`: Returns environment with proxy variables stripped

- **`media.py`**: External media scanner (BeautifulSoup for HTML, regex for CSS)
  - `get_external_media()`: Parses HTML/CSS for external media URLs
  - HTML: Uses BeautifulSoup to scan href/src attributes on relevant tags
  - CSS: Uses regex to scan url() references
  - Handles deduplication and URL normalization
  - Uses `file_iter.py` utilities for file iteration

### Post-Processing & Replacement Pipeline

- **`repair_html.py`**: HTML link rewriter (extracted from repair_links.py)
  - `repair_external_links()`: Rewrites external HTML URLs to local paths
  - `repair_internal_links()`: Rewrites internal HTML-to-HTML links to local paths (resume mode)
  - `_build_url_map()`: Builds URL → local filename mapping
  - `_rewrite_tag_urls()`: Shared helper for resource tag URL rewriting
  - Uses BeautifulSoup for safe DOM manipulation (URL rewriting + CORS attribute stripping)
  - Uses `file_iter.py` utilities for file iteration

- **`repair_links.py`**: CSS link rewriter (HTML processing moved to repair_html.py)
  - `repair_external_links()`: Rewrites external CSS URLs to local paths
  - `_build_css_replacement_steps()`: Constructs CSS replacement steps per file
  - CSS files: Uses regex pipeline for @import inlining, absolute path conversion, and external URL stripping
  - Each CSS replacement step validated automatically
  - Uses `file_iter.py` utilities for file iteration

- **`replacement_pipeline.py`**: Unified replacement engine with validation (CSS-only)
  - `ReplacementStep`: Dataclass for defining regex/callable replacements
  - `run_replacement_pipeline()`: Executes steps with automatic rollback on validation failure
  - Validates CSS content after each replacement (checks for non-empty content)
  - Logs failed replacements to `logs/NNNNN/` with file snapshot and pattern details
  - **Key feature**: Prevents regex bugs from corrupting CSS files
  - **Note**: HTML processing uses BeautifulSoup, not this pipeline

- **`repair_offline.py`**: Offline optimizer (BeautifulSoup-based)
  - `repair_offline_html()`: Removes online-only resources using BeautifulSoup DOM operations
  - `RemovalRule`: Dataclass for defining removal rules (tag, attrs, content checks)
  - `_REMOVAL_RULES`: Data-driven list of removal patterns (MediaWiki load.php, phpBB, tracking, etc.)
  - `_remove_dom_nodes()`: Applies removal rules using BeautifulSoup
  - `_clean_inline_javascript()`: Regex-based cleanup of inline JS (GA calls, push calls)
  - Handles MediaWiki (load.php), phpBB, tracking scripts, preconnect/dns-prefetch hints
  - Injects fallback CSS
  - All HTML tag removal uses `find_all()` + `.decompose()` — safe, cannot corrupt HTML structure
  - Uses `file_iter.py` utilities for file iteration

### Configuration & Reporting

- **`config.py`**: Type-safe configuration dataclass
  - `Settings`: Dataclass with typed fields for all configuration values
  - Provides compile-time validation and IDE autocomplete
  - Used throughout codebase instead of `dict[str, Any]`

- **`settings.py`**: Configuration loading (legacy dict interface for backwards compatibility)
  - `load_settings()`: Loads and merges settings.jsonc (with fallback to settings.json)
  - Returns `Settings` dataclass (not `dict[str, Any]`)
  - `_strip_jsonc_comments()`: Removes `//` and `/* */` comments from JSONC files
  - `merge_cli_overrides()`: Applies CLI parameter overrides
  - Supports range expression expansion: `{1..100}`, `{1..100..2}`, `{1..100%4,25,40}`

- **`report.py`**: Report generation
  - `write_site_report()`: Generates download summary
  - Creates failures.log for failed URLs

- **`validate_html.py`**: HTML integrity checker (BeautifulSoup-based)
  - `validate_html_files()`: Detects truncated/corrupt downloads (directory scan)
  - `validate_html_string()`: Validates single HTML content string using BeautifulSoup
  - Checks for missing `<head>`, `<body>` elements and empty bodies
  - Checks for binary/control characters indicating corrupted downloads
  - Uses `file_iter.py` utilities for file iteration
  - Called from `WgetCrawler.run()` after wget pass 1

- **`file_iter.py`**: File iteration utilities (shared infrastructure)
  - `iter_html_files()`: Yields (file_path, content) tuples for all HTML files
  - `iter_parsed_html()`: Yields (file_path, BeautifulSoup) tuples for parsed HTML
  - `iter_css_files()`: Yields (file_path, content) tuples for all CSS files
  - `write_if_changed()`: Writes file only if content changed (avoids mtime updates)
  - Centralizes error handling (read errors, empty content skipping)
  - Used by: `media.py`, `repair_html.py`, `repair_links.py`, `repair_offline.py`, `validate_html.py`

### URL Filtering & Path Conversion

- **`url_filter.py`**: Shared URL validation and extraction
  - `should_reject_url()`: Checks if URL should be rejected (domain, patterns, schemes)
  - `extract_internal_urls()`: Extracts all internal URLs from parsed HTML
  - Supports both navigation links (`<a href>`) and page requisites (`<img src>`, `<script src>`, etc.)
  - Handles relative URL resolution, fragment stripping, reject filtering
  - Used by: `resume.py::discover_links()`, `repair_links.py::repair_internal_links()`

- **`paths.py`**: URL-to-filepath conversion utilities
  - `url_to_filepath()`: Converts URLs to expected local file paths
  - `get_actual_save_path()`: Determines final save path (appends `.html` if needed)
  - `KNOWN_EXTENSIONS`: Module-level constant of known file extensions
  - Mimics wget's `--restrict-file-names=windows` behavior

### Resume Mode

- **`resume.py`**: Python-based BFS crawler (bypasses 429 bot protection)
  - `crawl_loop()`: Entry point for BFS crawling (delegates to `ResumeCrawler`)
  - `discover_links()`: Extracts internal links using shared `extract_internal_urls()`
  - `discover_css_imports()`: Extracts CSS @import references for BFS crawl
  - `ResumeCrawler`: Manages BFS crawl state (visited set, queue, depth tracking)
  - `fetch_file()`: Native HTTP fetching with retry logic
  - **Key feature**: Accepts injectable `session` parameter for testability
  - **Key feature**: Python manages entire crawl state; only hits server for missing pages
  - **Solves**: The Catch-22 of `-nc` + `--convert-links` incompatibility for resume
  - **Bypasses**: 429 bot protection by parsing existing files locally for links

### CLI

- **`__main__.py`**: CLI entry point
  - `main()`: Thin CLI wrapper that parses arguments and invokes pipeline
  - `resolve_config()`: Extractable function for URL, output dir, settings resolution
  - Parses arguments (argparse)
  - Handles interactive prompts
  - Calls `mirror.invoke_site_mirror()`
  - **Note**: `resolve_config()` can be unit tested independently

## Testing Strategy

### Test Files

- **`conftest.py`**: Shared fixtures (sample HTML, CSS, settings)
- **`test_*.py`**: Module-specific unit tests

### Running Tests

IMPORTANT: Use the direct venv Python executable for running tests.
The `uv run pytest` command will fail because pytest is installed in the venv,
not available as a standalone command.

```bash
# Install dev dependencies (pytest, pytest-cov) - ONE TIME SETUP
uv pip install -e ".[dev]"

# Run all tests
.\.venv\Scripts\python.exe -m pytest

# With coverage
.\.venv\Scripts\python.exe -m pytest --cov=site_sucker

# Specific module
.\.venv\Scripts\python.exe -m pytest tests/test_media.py
```

### Linting

The project uses **Ruff** for fast Python linting and import sorting.

```bash
# Install ruff (one-time setup)
uv pip install ruff

# Run linter to check for issues
uv run ruff check src/ tests/

# Auto-fix fixable issues
uv run ruff check --fix src/ tests/

# Show linting rules and documentation
uv run ruff rule --all
```

**Ruff configuration** is in `pyproject.toml` under `[tool.ruff]`:
- Targets Python 3.12
- Line length: 100 characters
- Enabled rules: pycodestyle (E, W), pyflakes (F), isort (I), flake8-bugbear (B), flake8-comprehensions (C4), pyupgrade (UP), flake8-unused-arguments (ARG), flake8-simplify (SIM)
- Test files allow unused function arguments (for pytest fixtures)

**Note**: The linter found 64 issues on initial run. These are legitimate code quality problems that should be addressed incrementally.

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
- **Logging**: Use `logging` module instead of `print()` for all progress/warning messages
- Configure logging in `__main__.py` with console handler

### Path Handling

- Use `pathlib.Path` for all path operations
- Resolve to absolute paths before file operations
- Use `Path.expanduser()` for user paths
- Cross-platform: use `Path` methods, not string concatenation

## Dependencies

- **Runtime dependencies**:
  - `beautifulsoup4>=4.12.0`: HTML parsing and DOM manipulation
  - `lxml>=5.0.0`: Fast HTML parser for BeautifulSoup
- **Dev dependencies**: `pytest`, `pytest-cov` (for testing), `ruff` (for linting)
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
  url                      The base URL to mirror (optional for interactive mode)
  -o, --output-dir DIR     Output directory (default: ./downloads/<domain>)
  -s, --settings PATH      Custom settings.jsonc (default: ./settings.jsonc)
  -d, --depth INT          Max recursion depth (0 = unlimited)
  -p, --parallel INT       Parallel downloads count (default: 4)
  -r, --reject PATTERN     Additional URL patterns to reject (supports range expressions)
  --resume                 Resume interrupted download using Python BFS crawler
                          (requires --output-dir pointing to existing download)
```

### Range Expression Syntax (--reject flag)

The `--reject` flag supports powerful range expressions:

| Syntax | Meaning | Example |
|--------|---------|---------|
| `{START..END}` | Numeric range (inclusive) | `{1..10}` → 1, 2, ..., 10 |
| `{START..END..STEP}` | Range with step | `{1..10..2}` → 1, 3, 5, 7, 9 |
| `{START..END%EXCLUDE}` | Range excluding values | `{1..10%3,7}` → 1, 2, 4, 5, 6, 8, 9, 10 |

**Examples:**
```bash
# Reject forum IDs 1-100 except 4, 25, 40
--reject "f={1..100%4,25,40}&"

# Reject even forum IDs 2-20
--reject "f={2..20..2}&"

# Mix literal patterns and expressions (semicolon-delimited)
--reject "action=;f={1..10%5}&;Special:"

# Or use multiple --reject flags (they are combined)
--reject "action=" --reject "f={1..10}&" --reject "Special:"
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
2. **Logging framework**: Replace `print()` statements with `logging` module for better testability
3. **Settings dataclass**: Replace `dict[str, Any]` with type-safe `@dataclass` for compile-time validation
4. **Different output formats**: PDF, single-file HTML
5. **Content filtering**: Regex-based content inclusion/exclusion

### Recently Completed

- ✅ **2026-05-03 Refactoring**: Comprehensive refactoring completed
  - Settings dataclass (`config.py`) for type-safe configuration
  - Extracted `download.py` for testable external media download
  - Split `repair_links.py` into `repair_html.py` (HTML) and `repair_links.py` (CSS)
  - Replaced `print()` with `logging` module throughout codebase
  - Made `ResumeCrawler` testable via injectable HTTP session
  - Consolidated helpers: `get_clean_env()` in `wget.py`, `write_if_changed()` in `file_iter.py`
  - Extracted `resolve_config()` from `__main__.py` for unit testing
- ✅ **Resume support**: Python BFS crawler with `--resume` flag
- ✅ **Shared URL extraction**: `url_filter.py` for resume + repair modes
- ✅ **Data-driven DOM removal**: `RemovalRule` dataclass in `repair_offline.py`
- ✅ **Unified crawler abstraction**: `CrawlerBase` for wget/BFS mode switching
- ✅ **File iteration utilities**: `file_iter.py` for consistent HTML/CSS scanning
- ✅ **HTML processing safety**: BeautifulSoup-based operations, cannot corrupt HTML structure

## Contact & Support

For questions or issues:
- Check existing tests for usage patterns
- Review this AGENTS.md
- Examine the original PowerShell implementation in `docs/`
