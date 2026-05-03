# SiteSucker Refactoring Plan

**Date:** 2026-05-03
**Status:** Completed (partial)

## Summary

This refactoring unified the wget and BFS resume modes under a common `CrawlerBase` abstraction, extracted shared utilities for URL filtering and path resolution, and improved test quality. The primary goal was to reduce code duplication and complexity in the mirroring pipeline.

## Completed Refactorings

### 1. Extracted `paths.py` Module

**Files Created:**
- `src/site_sucker/paths.py`

**Changes:**
- Moved `url_to_filepath()` and `get_actual_save_path()` from `resume.py` to a new shared module.
- Updated `resume.py` to import from `paths.py`.
- Updated `repair_links.py` to import from `paths.py` instead of `resume.py`.

**Benefit:** Removes confusing dependency where `repair_links.py` imports from `resume.py` despite not being resume-specific.

### 2. Extracted `url_filter.py` Module

**Files Created:**
- `src/site_sucker/url_filter.py`

**Changes:**
- Created `should_reject_url()` function to consolidate URL filtering logic.
- Updated `resume.py::discover_links()` and `discover_css_imports()` to use the shared filter.

**Benefit:** Eliminates duplication of reject pattern, reject domain, scheme, and hostname checks across 3 modules.

### 3. Extracted `file_iter.py` Module

**Files Created:**
- `src/site_sucker/file_iter.py`

**Changes:**
- Created `iter_html_files()`, `iter_parsed_html()`, and `iter_css_files()` utility functions.
- These functions encapsulate the common pattern of globbing, reading, and parsing HTML/CSS files with error handling.

**Benefit:** Ready for future use in `media.py`, `repair_links.py`, `repair_offline.py`, and `validate_html.py` (all of which currently duplicate this pattern).

### 4. Created `CrawlerBase` Abstraction

**Files Created:**
- `src/site_sucker/crawler.py`

**Changes:**
- Defined `CrawlerBase` abstract protocol with `run() -> CrawlResult` method.
- Created `WgetCrawler` class wrapping wget subprocess + validation logic.
- Created `BFSCrawler` class wrapping the Python BFS crawler.
- Defined `CrawlResult` dataclass with `failed_urls` and `needs_internal_link_repair` fields.
- Updated `mirror.py::invoke_site_mirror()` to use the unified crawler interface.

**Before:**
```python
if resume:
    crawl_loop(url, output_dir, target_domain, settings)
    repair_internal_links(output_dir, target_domain)
else:
    # 20+ lines of wget subprocess + validation code
```

**After:**
```python
crawler_cls = BFSCrawler if resume else WgetCrawler
crawler = crawler_cls(url, output_dir, target_domain, settings)
crawl_result = crawler.run()
if crawl_result.needs_internal_link_repair:
    repair_internal_links(output_dir, target_domain)
```

**Benefit:** The mirror pipeline is now mode-agnostic. The branching logic for choosing a crawler is isolated to a single line, making the flow easier to understand and maintain.

### 5. Improved Test Quality

**Files Modified:**
- `tests/test_mirror.py`

**Changes:**
- Replaced source-code-reading test with proper mock-based tests.
- Added `test_wget_crawler_used_when_resume_false()` to verify WgetCrawler behavior.
- Added `test_bfs_crawler_used_when_resume_true()` to verify BFSCrawler behavior.

**Benefit:** Tests now verify actual behavior instead of implementation details, making them more robust and maintainable.

### 6. Updated AGENTS.md

**Files Modified:**
- `AGENTS.md`

**Changes:**
- Added explicit instructions to use `.\.venv\Scripts\python.exe -m pytest` instead of `uv run pytest`.
- Documented the one-time setup step: `uv pip install -e ".[dev]"`.

**Benefit:** Prevents future confusion about why `uv run pytest` doesn't work.

## Skipped Refactorings

The following items from the original plan were deferred for stability:

### 1. Split `repair_links.py::repair_external_links()`

The CSS processing section with its nested `inline_imports` closure and dynamic `ReplacementStep` construction is complex, but the function works correctly and has comprehensive test coverage. Breaking it up would require significant testing effort with unclear benefit.

### 2. Data-driven `_remove_dom_nodes()` in `repair_offline.py`

Attempted to replace 15+ repetitive `find_all` + `decompose` blocks with a data-driven approach using a list of rules. However, the special-case handling for script content filtering and noscript tracking images made the data-driven approach more complex than the original straightforward implementation. Reverted to the original for stability.

## Test Results

All 151 tests pass:
```
151 passed in 1.56s
```

## New Module Dependency Graph

```
mirror.py
  └─> crawler.py
        ├─> resume.py
        │     ├─> paths.py
        │     └─> url_filter.py
        └─> wget.py
              └─> validate_html.py
  └─> media.py
  └─> repair_links.py
        ├─> paths.py
        └─> replacement_pipeline.py
  └─> repair_offline.py
  └─> report.py
```

## Future Enhancement Opportunities

1. **Use `file_iter.py` utilities** in `media.py`, `repair_offline.py`, and `validate_html.py` to eliminate HTML file iteration duplication.
2. **Extract CSS replacement steps** from `repair_links.py::repair_external_links()` into a standalone function for better testability.
3. **Add integration tests** for the full `invoke_site_mirror()` flow with mocked subprocesses.
4. **Consider a strategy pattern** for DOM removal rules in `repair_offline.py` if new removal patterns are frequently added.
