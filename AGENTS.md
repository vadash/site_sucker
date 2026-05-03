# SiteSucker — AI Agent Guide

Website mirror tool. 4-pass pipeline: wget mirror → external media download → URL rewriting → offline stripping.

## Pipeline Entry

`mirror.py::invoke_site_mirror()` orchestrates all passes. `CrawlerBase` abstraction: `WgetCrawler` (default) or `BFSCrawler` (`--resume`).

## Module Map

| Module | Role |
|---|---|
| `mirror.py` | Pipeline orchestrator, `invoke_site_mirror()` |
| `download.py` | Parallel external media download (ThreadPoolExecutor) |
| `crawler.py` | `CrawlerBase` ABC, `WgetCrawler`, `BFSCrawler`, `CrawlResult` |
| `wget.py` | Wget binary wrapper (`bin/wget.exe`), arg builder, env cleaner |
| `media.py` | Scans HTML (BS4) + CSS (regex) for external media URLs |
| `repair_html.py` | Rewrites HTML links to local paths (BS4 DOM ops) |
| `repair_links.py` | Rewrites CSS links via `replacement_pipeline.py` |
| `replacement_pipeline.py` | CSS regex engine with auto-rollback on validation failure |
| `repair_offline.py` | Removes online-only resources (data-driven `RemovalRule` list) |
| `config.py` | `Settings` dataclass (type-safe config) |
| `settings.py` | Loads `settings.jsonc`, CLI overrides, range expression expansion |
| `file_iter.py` | Shared `iter_html_files()`, `iter_css_files()`, `write_if_changed()` |
| `url_filter.py` | URL reject checks + internal URL extraction |
| `paths.py` | URL-to-filepath conversion (mimics wget windows mode) |
| `resume.py` | BFS crawler for `--resume` mode, injectable HTTP session |
| `validate_html.py` | Post-crawl HTML integrity check |
| `report.py` | Download summary + failures.log |
| `__main__.py` | CLI entry, `resolve_config()` for testable config resolution |

## Critical Design Rules

- **HTML processing**: Always BeautifulSoup DOM ops — never regex on HTML
- **CSS processing**: All regex via `replacement_pipeline.py` (auto-rollback + logging to `logs/NNNNN/`)
- **Config**: Use `Settings` dataclass everywhere, never raw dicts
- **File iteration**: Use `file_iter.py` helpers, never manual `os.walk` loops
- **Logging**: Use `logging` module, never `print()`
- **Paths**: Always `pathlib.Path`, resolve to absolute before file ops
- **Error style**: `FileNotFoundError` for missing wget; empty list/set for "not found"; `try/except` for IO

## Running Tests & Linting

```bash
# Tests (use venv python directly, NOT bare "pytest")
.\.venv\Scripts\python.exe -m pytest              # all
.\.venv\Scripts\python.exe -m pytest --cov=site_sucker  # with coverage

# Lint (Ruff — config in pyproject.toml, Python 3.12, line length 100)
uv run ruff check src/ tests/          # check
uv run ruff check --fix src/ tests/    # auto-fix
```

## Platform Gotchas

- **Windows only**. System `python`/`python3` shows Store prompt — always use `uv run` or `.venv\Scripts\python.exe`
- `wget.exe` lives in `bin/`
- Git Bash `/tmp/` maps to `C:/Users/<user>/AppData/Local/Temp/`

## Workflow

1. **Bug fix**: failing test → fix → verify all tests pass
2. **New pipeline pass**: create module → wire in `invoke_site_mirror()` → tests → update this file
3. **New URL pattern**: add to `settings.jsonc` with comment → test in `test_wget.py` + relevant module

## CLI Quick Ref

```
site-sucker [url] [-o DIR] [-s SETTINGS] [-d DEPTH] [-p PARALLEL] [-r PATTERN] [--resume]
```

`--reject` supports range expressions: `{1..100}`, `{1..100..2}`, `{1..100%4,25,40}`. Semicolons or multiple flags to combine.
