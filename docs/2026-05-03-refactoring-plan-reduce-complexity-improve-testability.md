
## Current State

The codebase is already well-structured for a hobby project: 16 modules, 171 passing tests, 75% coverage. The architecture (4-pass pipeline, crawler abstraction, shared utilities) is sound. The suggestions below target specific complexity hotspots and testability gaps, not a rewrite.

---

## 1. Replace `dict[str, Any]` settings with a dataclass

**Problem**: `settings` is passed as `dict[str, Any]` through every function. Typos in key names are silent bugs, IDE autocomplete doesn't work, and there's no validation at the boundary.

**Fix**: Create a `Settings` dataclass in `settings.py` with typed fields. `load_settings()` returns `Settings` instead of a dict. All downstream signatures change from `dict[str, Any]` to `Settings`.

```python
@dataclass
class Settings:
    user_agent: str = "Mozilla/5.0 ..."
    timeout: int = 15
    retries: int = 3
    max_depth: int = 0
    output_root: str = "./downloads"
    wait_between_requests: float = 0.5
    parallel_downloads: int = 2
    reject_patterns: list[str] = field(default_factory=list)
    reject_domains: list[str] = field(default_factory=list)
    media_extensions: list[str] = field(default_factory=lambda: [".png", ...])
```

**Impact**: Every module that takes `settings` (mirror, crawler, resume, wget, media). ~30 call sites. Mechanical but high-value change.

---

## 2. Extract `mirror.py` pass 2 (external media download) into its own module

**Problem**: `invoke_site_mirror()` is 90 lines and directly manages wget subprocess calls, ThreadPoolExecutor, and progress reporting for pass 2. This is the only untestable part of the pipeline (20% coverage on mirror.py, all from pass 2).

**Fix**: Create `download.py` with a `download_external_media(urls, media_dir, settings) -> list[str]` function. `mirror.py` becomes a thin orchestrator calling 4 functions.

```python
# mirror.py becomes:
def invoke_site_mirror(...):
    crawl_result = crawler.run()
    if crawl_result.needs_internal_link_repair:
        repair_internal_links(...)
    ext_urls = get_external_media(...)
    failed = download_external_media(ext_urls, media_dir, settings)  # new module
    repair_external_links(...)
    repair_offline_html(...)
    return failed
```

**Impact**: `mirror.py` drops to ~30 lines. `download.py` can be tested independently with mocked subprocess.

---

## 3. Decouple `repair_links.py` -- split HTML and CSS repair

**Problem**: `repair_links.py` is the largest module (208 statements). It mixes two unrelated concerns: BeautifulSoup-based HTML rewriting and regex-pipeline CSS processing. The `repair_external_links()` function is 50+ lines of orchestration with inline counting logic.

**Fix**: Split into `repair_html.py` (external + internal HTML link rewriting) and keep CSS processing in `repair_links.py` (or rename to `repair_css.py`). The orchestration in `repair_external_links()` calls both.

Alternatively, just extract `_repair_html_links_from_content` and `_build_css_replacement_steps` into their own focused modules and keep `repair_links.py` as the orchestrator. The key win is making the HTML and CSS paths independently testable.

---

## 4. Remove direct `print()` calls -- use `logging` module

**Problem**: Every module uses `print()` for progress and warnings. This makes functions hard to test (need `capsys`), impossible to silence, and can't be redirected to a file. Several tests already use `capsys` as a workaround.

**Fix**: Replace `print()` with `logging.getLogger(__name__)` calls. Configure a console handler in `__main__.py`. Tests can assert on log records instead of captured stdout.

```python
# Before
print(f"  Mapping {len(url_map)} external URLs to local files")

# After
logger.info("Mapping %d external URLs to local files", len(url_map))
```

**Impact**: Every module. Mechanical find-and-replace. Progress counters (`\r  [5/10]`) become `logger.info` with a custom formatter or stay as `print` in a dedicated progress helper.

---

## 5. Make `ResumeCrawler` testable by injecting the HTTP client

**Problem**: `ResumeCrawler` creates its own `requests.Session` internally. Testing `run()` requires mocking `requests.Session` at the module level. Coverage is 36%.

**Fix**: Accept an optional `session: requests.Session | None` parameter. If None, create the default session. Tests pass a mock session.

```python
class ResumeCrawler:
    def __init__(self, output_dir, target_domain, settings, session=None):
        ...
        self.session = session or self._build_default_session()
```

**Impact**: `resume.py` only. Enables proper unit tests for `fetch_file()` and `run()` without network mocking.

---

## 6. Consolidate duplicated proxy-stripping and file-writing patterns

**Problem**: The proxy-stripping block (`env = os.environ.copy(); for var in [...]: env.pop(var, None)`) appears in both `mirror.py` and `crawler.py`. The "write file only if modified" pattern with `open(..., newline="")` appears in 3 places in `repair_links.py` and `repair_offline.py`.

**Fix**:
- Add `get_clean_env() -> dict` helper to `wget.py` (it already owns wget concerns).
- Add `write_if_changed(path, original, new_content) -> bool` helper to `file_iter.py`.

---

## 7. Improve `__main__.py` testability

**Problem**: `__main__.py` has 0% coverage. `main()` does URL parsing, interactive prompts, directory creation, and pipeline invocation all in one function.

**Fix**: Extract the logic between argument parsing and `invoke_site_mirror()` into a `resolve_config(args) -> tuple[str, Path, str, Settings]` function that can be unit tested. Keep `main()` as the thin CLI wrapper.

---

## Summary: Priority Order

| # | Change | Effort | Value | Risk |
|---|--------|--------|-------|------|
| 1 | Settings dataclass | Medium | High | Low |
| 2 | Extract download.py | Low | High | Low |
| 3 | Split repair_links.py | Medium | Medium | Low |
| 4 | logging instead of print | Medium | Medium | Low |
| 5 | Inject session in ResumeCrawler | Low | Medium | Low |
| 6 | Consolidate helpers | Low | Low | Low |
| 7 | Testable __main__.py | Low | Medium | Low |

All changes are backwards-compatible and can be done incrementally. None require changing the 4-pass pipeline architecture, which is solid.
