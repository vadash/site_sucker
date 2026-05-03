# SiteSucker — AI Agent Guide

Website mirror tool. 4-pass pipeline: wget mirror → external media download → URL rewriting → offline stripping.
Entry: `mirror.py::invoke_site_mirror()`. `CrawlerBase` → `WgetCrawler` (default) | `BFSCrawler` (`--resume`).

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
| `repair_offline.py` | Removes online-only resources (`RemovalRule` list) |
| `config.py` | `Settings` dataclass (type-safe config) |
| `settings.py` | Loads `settings.jsonc`, CLI overrides, range expansion |
| `file_iter.py` | `iter_html_files()`, `iter_css_files()`, `write_if_changed()` |
| `url_filter.py` | URL reject checks + internal URL extraction |
| `paths.py` | URL-to-filepath conversion (mimics wget windows mode) |
| `resume.py` | BFS crawler for `--resume` mode, injectable HTTP session |
| `validate_html.py` | Post-crawl HTML integrity check |
| `report.py` | Download summary + failures.log |
| `__main__.py` | CLI entry, `resolve_config()` |

## Design Rules

- **HTML**: Always BS4 DOM ops — never regex on HTML
- **CSS**: All regex via `replacement_pipeline.py` (auto-rollback, logs to `logs/NNNNN/`)
- **Config**: `Settings` dataclass everywhere, never raw dicts
- **File iteration**: `file_iter.py` helpers, never manual `os.walk`
- **Logging**: `logging` module, never `print()`
- **Paths**: `pathlib.Path`, resolve to absolute before file ops
- **Errors**: `FileNotFoundError` for missing wget; empty list/set for "not found"; `try/except` for IO
- **Naming**: PEP 8 — `snake_case`/`PascalCase`/`UPPER_CASE` (enforced by Ruff)

## Commands

```bash
.\.venv\Scripts\python.exe -m pytest                    # tests
.\.venv\Scripts\python.exe -m pytest --cov=site_sucker  # with coverage
uv run ruff check src/ tests/                           # lint
uv run ruff check --fix src/ tests/                     # lint --fix
uv run pre-commit run --all-files                       # all hooks
uv run radon cc src/ -a -s                              # complexity (C+ fails hook)
uv run vulture src/ --min-confidence 80                 # dead code (whitelist: .vulture.whitelist)
npx jscpd src/                                          # duplicate detection
```

**Pre-commit hooks** (auto on commit): Ruff, MyPy, Radon (complexity ≤10), Vulture (80% confidence), jscpd, file checks, private key detection, branch protection (no direct master commits). Install: `uv run pre-commit install`.

## Platform

- Windows only. Use `uv run` or `.venv\Scripts\python.exe` (system `python` opens Store)
- `wget.exe` in `bin/`
- Git Bash `/tmp/` → `C:/Users/<user>/AppData/Local/Temp/`

## Workflow

1. **Bug fix**: failing test → fix → verify all tests pass
2. **New pass**: create module → wire in `invoke_site_mirror()` → tests → update this file
3. **New URL pattern**: add to `settings.jsonc` → test in `test_wget.py` + relevant module

## CLI

```
site-sucker [url] [-o DIR] [-s SETTINGS] [-d DEPTH] [-p PARALLEL] [-r PATTERN] [--resume]
```

`--reject` ranges: `{1..100}`, `{1..100..2}`, `{1..100%4,25,40}`. Semicolons or multiple flags to combine.
