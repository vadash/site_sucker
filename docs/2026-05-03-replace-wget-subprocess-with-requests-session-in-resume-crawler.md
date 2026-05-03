
## Refactoring Plan: Native Python HTTP for Resume Crawler

### Problem
The resume crawler spawns thousands of `wget.exe` subprocess calls. This causes:
1. **Redirect naming bugs** - wget follows 301/302 and saves under the *redirected* filename, but Python looks for the *original* filename
2. **Network drops (exit 4)** - no structured retry mechanism
3. **CPU overhead** - thousands of subprocess spawns on Windows

### Solution
Replace wget subprocess calls with `requests.Session` (persistent TCP, built-in retry with backoff, no subprocess overhead). Python now controls where files are saved, eliminating the "guess what wget did" problem entirely.

---

### Step 1: Add `requests` dependency
- Add `requests>=2.31.0` to `pyproject.toml` dependencies

### Step 2: Rewrite `resume.py`
- **Add `get_actual_save_path()`** - simple function: if URL has no known extension, append `.html`
- **Create `ResumeCrawler` class** with:
  - `__init__` - initializes settings, `requests.Session` with `HTTPAdapter(max_retries=Retry(total=N, backoff_factor=1, status_forcelist=[429,500,502,503]))`
  - `fetch_file()` - uses `session.get()` with retries, writes to the exact path we expect
  - `run()` - BFS loop (same logic as current `crawl_loop`, but uses `fetch_file` instead of subprocess)
  - `process_discovered_links()` - dispatches to `discover_links` or `discover_css_imports` based on extension
- **Keep `url_to_filepath()`** unchanged (same mapping logic)
- **Keep `discover_links()` and `discover_css_imports()`** unchanged
- **Remove** `file_exists_on_disk()`, `resolve_local_file()`, `_check_path_exists()`, `_ADJUST_EXTENSION_SUFFIXES`
- **Update `crawl_loop()`** to be a thin wrapper: instantiates `ResumeCrawler` and calls `.run()`
- **Remove `wget_path` parameter** from `crawl_loop()` signature

### Step 3: Update `mirror.py`
- Remove `wget_path` argument from the `crawl_loop()` call in `invoke_site_mirror()`

### Step 4: Update `repair_links.py`
- Replace `from site_sucker.resume import resolve_local_file, url_to_filepath` with `from site_sucker.resume import get_actual_save_path, url_to_filepath`
- Replace `resolve_local_file(expected_path, output_dir)` with `get_actual_save_path(expected_path)` (simple one-liner, no `output_dir` needed)

### Step 5: Update tests
- **Remove tests for deleted functions**: all `test_file_exists_on_disk_*` and `test_resolve_local_file_*` tests (11 tests)
- **Add tests for `get_actual_save_path()`**:
  - Known extensions (.css, .js, .html) → returned unchanged
  - Unknown extension (.php, no extension) → `.html` appended
  - Query-string filenames → `.html` appended
- **Update `test_resume.py` imports**: remove `file_exists_on_disk`, `resolve_local_file`; add `ResumeCrawler`, `get_actual_save_path`
- **Update `test_repair_links.py`**: no changes needed (tests use `tmp_path` with real files, not mocked path resolution)

### Files Modified
| File | Change |
|------|--------|
| `pyproject.toml` | Add `requests>=2.31.0` |
| `src/site_sucker/resume.py` | Major rewrite: OOP crawler, `requests.Session`, remove wget logic |
| `src/site_sucker/mirror.py` | Remove `wget_path` arg from `crawl_loop` call |
| `src/site_sucker/repair_links.py` | Use `get_actual_save_path` instead of `resolve_local_file` |
| `tests/test_resume.py` | Remove old tests, add new ones |
