# AI Agents Development Guide

This document provides guidance for AI agents (including Factory Droids) working on the SiteSucker codebase.

## Architecture Overview

SiteSucker is a modular Python application that mirrors websites for offline use. It uses a 4-pass pipeline:

1. **Pass 1**: Wget-based full site mirror
2. **Pass 2**: Parallel external media download
3. **Pass 3**: External URL → local path rewriting
4. **Pass 4**: Online-only resource stripping

## Key Modules

### Core Pipeline

- **`mirror.py`**: Orchestrates the entire 4-pass pipeline
  - Entry point: `invoke_site_mirror()`
  - Returns: List of failed URLs
  - Creates `output_dir/logs/` for replacement error logging

- **`wget.py`**: Wget binary wrapper
  - `get_wget_path()`: Resolves `bin/wget.exe`
  - `build_wget_args()`: Constructs argument arrays from settings

- **`media.py`**: External media scanner
  - `get_external_media()`: Parses HTML for external media URLs
  - Handles deduplication and URL normalization

### Post-Processing & Replacement Pipeline

- **`replacement_pipeline.py`**: Unified replacement engine with validation
  - `ReplacementStep`: Dataclass for defining regex/callable replacements
  - `run_replacement_pipeline()`: Executes steps with automatic rollback on validation failure
  - Validates HTML structure after each replacement (using `validate_html.py`)
  - Logs failed replacements to `logs/NNNNN/` with file snapshot and pattern details
  - **Key feature**: Prevents regex bugs from corrupting downloads

- **`repair_links.py`**: URL rewriter (now uses pipeline)
  - `repair_external_links()`: Rewrites external URLs to local paths
  - Processes both HTML and CSS files
  - Strips CORS-blocking attributes
  - Each replacement step validated automatically

- **`repair_offline.py`**: Offline optimizer (now uses pipeline)
  - `repair_offline_html()`: Removes online-only resources
  - Handles MediaWiki (load.php), phpBB, tracking scripts
  - Injects fallback CSS
  - All regex replacements defined as `ReplacementStep` list for clarity
  - **CAUTION**: Regex patterns removing `<script>` blocks MUST use `(?:(?!</script>)[\s\S])*?` boundary guards (see Regex Pitfalls)

### Configuration & Reporting

- **`settings.py`**: Configuration management
  - `load_settings()`: Loads and merges settings.json
  - `merge_cli_overrides()`: Applies CLI parameter overrides

- **`report.py`**: Report generation
  - `write_site_report()`: Generates download summary
  - Creates failures.log for failed URLs

- **`validate_html.py`**: HTML integrity checker
  - `validate_html_files()`: Detects truncated/corrupt downloads (directory scan)
  - `validate_html_string()`: Validates single HTML content string (used by pipeline)
  - Checks for missing `</head>`, `<body>`, `</body>` tags and empty bodies
  - Runs after wget pass 1, before post-processing; also after each replacement step

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
pytest

# With coverage
pytest --cov=site_sucker

# Specific module
pytest tests/test_media.py
```

### Test Patterns

- Use `tmp_path` fixture for file operations
- Mock subprocess calls in integration tests
- Test both success and failure paths
- Verify file content changes, not just return codes

## Common Tasks

### Adding New URL Patterns

When adding new reject patterns or URL handling:

1. Update `settings.json` with the pattern
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

- **Stdlib only**: No external runtime dependencies
- **Dev dependencies**: `pytest`, `pytest-cov` (for testing)
- **Binary**: `wget.exe` in `bin/` directory

## Platform Notes

**Windows 11 Only**: This implementation is Windows-specific.

- Uses `wget.exe` binary (not Linux wget)
- Path handling assumes Windows separators
- No cross-platform testing required

### Running Python

- **System `python`/`python3` does NOT work** — Windows App Execution Aliases intercept it and show a Store prompt.
- **`uv run python` fails** — the editable install is marked `--no-build`.
- **Correct path**: `/.venv/Scripts/python.exe` (relative to project root).
- For inline scripts: `<project-root>/.venv/Scripts/python.exe -c "..."`
- For tests: `<project-root>/.venv/Scripts/python.exe -m pytest`
- **Temp files**: `curl -o /tmp/file` on Windows Git Bash saves to `C:/Users/<user>/AppData/Local/Temp/file`, not `/tmp/`. Use the Windows path when reading from Python.

## Settings File Schema

```json
{
  "UserAgent": "string",
  "Timeout": int,
  "Retries": int,
  "MaxDepth": int,
  "OutputRoot": "string",
  "WaitBetweenRequests": float,
  "ParallelDownloads": int,
  "RejectPatterns": ["string"],
  "RejectDomains": ["string"],
  "MediaExtensions": ["string"]
}
```

## CLI Interface

```bash
site-sucker [url] [options]

Options:
  -o, --output-dir DIR     Output directory
  -s, --settings PATH      Custom settings.json
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

### Unified Replacement Architecture

All regex and content replacements now go through `replacement_pipeline.py`:

1. Each replacement is a `ReplacementStep` with name, pattern, and replacement
2. Steps run sequentially; content validated after each change
3. On validation failure: change reverted, logged to `logs/NNNNN/`, pipeline continues
4. After all steps: final content written (only if modified)

### Log Directory Structure

Failed replacements create:
```
<output_dir>/logs/
  00001/
    index.html        # File content at point of failure
    pattern.txt       # Step name, regex pattern, validation error
  00002/
    style.css
    pattern.txt
```

This provides a debug trail for fixing problematic regexes without corrupting downloads.

## Regex Pitfalls

### Never use `[\s\S]*?` across `<script>` boundaries

Patterns like `<script[^>]*>[\s\S]*?something[\s\S]*?</script>` will match from the **first** `<script>` tag that can reach `something` via `[\s\S]*?` — even if that means crossing intermediate `</script>` tags. This can delete entire page bodies.

**Bad** (crosses `</script>` boundaries):
```python
r'<script[^>]*>[\s\S]*?google-analytics\.com[\s\S]*?</script>'
```

**Good** (stays within one script block using negative lookahead):
```python
r'<script[^>]*>(?:(?!</script>)[\s\S])*?google-analytics\.com(?:(?!</script>)[\s\S])*?</script>'
```

The `(?:(?!</script>)[\s\S])*?` construct matches any character (`[\s\S]`) but only after confirming the upcoming text is NOT `</script>`. This prevents the match from leaking into adjacent script blocks or page content.

**Rule**: Any regex that matches `<script>...X...</script>` where X is content found inside script blocks MUST use the `(?:(?!</script>)[\s\S])*?` boundary guard instead of `[\s\S]*?`.

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
