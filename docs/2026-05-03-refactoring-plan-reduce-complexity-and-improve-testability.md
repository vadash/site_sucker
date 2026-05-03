
## Analysis Summary

The codebase is already reasonably well-structured with clear module boundaries. The main issues are around **duplicated patterns**, **god-function complexity**, **tight coupling to I/O**, and **unused abstractions**. Here's what I'd address, grouped by priority.

---

### 1. Duplicated HTML file iteration pattern

**Problem:** Every module (`media.py`, `repair_links.py`, `repair_offline.py`, `validate_html.py`) independently does the same `rglob("*.html") + rglob("*.htm")` + open + read + skip-empty dance. You already built `file_iter.py` with `iter_html_files()`, `iter_parsed_html()`, and `iter_css_files()` -- but **nothing uses them**.

**Fix:** Replace all manual file iteration loops with calls to `file_iter.py` utilities. This eliminates ~60 lines of duplicated boilerplate and centralizes error handling.

**Files:** `media.py`, `repair_links.py`, `repair_offline.py`, `validate_html.py`

---

### 2. `repair_external_links()` is a 120-line god-function

**Problem:** `repair_external_links()` in `repair_links.py` does too many things: builds URL maps, processes HTML files, builds per-file CSS replacement steps (with closures), runs the pipeline, and counts stats. The CSS step-building alone is ~60 lines with a nested closure.

**Fix:** Extract into focused helpers:
- `_build_url_map(media_dir, external_urls) -> dict` -- URL-to-filename mapping
- `_build_css_steps(css_file, output_dir, url_map) -> list[ReplacementStep]` -- CSS replacement step factory
- Keep `repair_external_links()` as a thin orchestrator calling these + `_repair_html_links()`

This makes each piece independently testable without needing full directory setups.

---

### 3. `repair_internal_links()` has duplicated tag-rewriting logic

**Problem:** The function has two nearly identical loops -- one for `<a>` tags and one for resource tags (`img`, `script`, `link`, etc.). Both do: parse URL -> check domain -> map to filepath -> resolve actual path -> build relative path. The only difference is the tag selector and attribute name.

**Fix:** Extract a shared `_rewrite_tag_urls(soup, tags, attrs, ...) -> bool` helper that both loops call. Cuts ~40 lines of duplication.

---

### 4. `mirror.py` has undefined variables (`wget_path`, `env`)

**Problem:** In `invoke_site_mirror()`, Pass 2 references `wget_path` and `env` that are never defined in the current function scope. This is a latent bug -- the code would crash at runtime when external media URLs are found.

**Fix:** Add `wget_path = get_wget_path()` and the `env` dict setup (proxy stripping) before the Pass 2 block. This was likely lost during the crawler refactor.

---

### 5. `ResumeCrawler` duplicates link-rewriting logic from `repair_links.py`

**Problem:** `resume.py::discover_links()` and `repair_links.py::repair_internal_links()` both parse HTML with BeautifulSoup, iterate tags, resolve URLs with `urljoin`, filter by domain, and check reject patterns. They share the same URL validation logic but implement it independently.

**Fix:** Extract a shared `extract_internal_urls(soup, base_url, target_domain, reject_patterns, reject_domains) -> set[str]` into `url_filter.py` (or a new `html_links.py`). Both modules call it instead of reimplementing.

---

### 6. `known_extensions` set is duplicated

**Problem:** `paths.py::get_actual_save_path()` has a hardcoded `known_extensions` set, and `settings.py::DEFAULT_SETTINGS` has `MediaExtensions`. These overlap but aren't shared, so adding a new extension requires updating two places.

**Fix:** Move `known_extensions` to a module-level constant in `paths.py` and reference it from both places. Or better: make `get_actual_save_path` accept the set as a parameter with a default, so tests can inject it.

---

### 7. `_remove_dom_nodes()` in `repair_offline.py` is a long flat list

**Problem:** 80+ lines of repetitive `soup.find_all(...) -> decompose()` calls. Each block is 3 lines (find, decompose, count). Adding a new pattern means copy-pasting the block.

**Fix:** Define removal rules as a data structure (list of dicts with selector kwargs), then loop over them:

```python
_REMOVAL_RULES = [
    {"tag": "link", "attrs": {"rel": "stylesheet", "href": re.compile(r"load\.php")}},
    {"tag": "script", "attrs": {"src": re.compile(r"load\.php")}},
    {"tag": "link", "attrs": {"rel": "preconnect"}},
    # ...
]

def _remove_dom_nodes(soup):
    removed = 0
    for rule in _REMOVAL_RULES:
        for tag in soup.find_all(rule["tag"], **rule["attrs"]):
            tag.decompose()
            removed += 1
    return removed
```

This is more maintainable and makes it trivial to add/remove rules.

---

### 8. Print statements everywhere instead of logging

**Problem:** All modules use `print()` for status output. This makes it impossible to control verbosity, filter by level, or suppress output in tests (you'd need `capsys` everywhere).

**Fix:** Replace `print()` with `logging.getLogger(__name__)` calls. Use `INFO` for progress, `WARNING` for non-fatal issues, `DEBUG` for details. Configure the root logger in `__main__.py`. Tests can then assert on log records without capsys hacks.

---

### 9. Settings passed as raw `dict[str, Any]` everywhere

**Problem:** Every function takes `settings: dict[str, Any]` and accesses keys by string (`settings["UserAgent"]`, `settings.get("MaxDepth", 0)`). Typos in key names are silent bugs. No IDE autocompletion. No validation at load time.

**Fix:** Define a `@dataclass` (or `TypedDict`) in `settings.py`:

```python
@dataclass
class SiteSettings:
    user_agent: str
    timeout: int
    retries: int
    max_depth: int
    output_root: str
    wait_between_requests: float
    parallel_downloads: int
    reject_patterns: list[str]
    reject_domains: list[str]
    media_extensions: list[str]
```

`load_settings()` returns a `SiteSettings` instance. All consumers get type safety and autocompletion. This is the highest-effort change but has the biggest long-term payoff.

---

### Suggested Priority Order

| # | Change | Effort | Impact |
|---|--------|--------|--------|
| 4 | Fix undefined `wget_path`/`env` bug | Low | Critical (runtime crash) |
| 1 | Use existing `file_iter.py` utilities | Low | Medium (DRY) |
| 7 | Data-driven DOM removal rules | Low | Medium (maintainability) |
| 2 | Extract helpers from `repair_external_links` | Medium | High (testability) |
| 3 | Deduplicate tag-rewriting in `repair_internal_links` | Medium | Medium (DRY) |
| 5 | Shared URL extraction for resume + repair | Medium | Medium (DRY) |
| 6 | Shared `known_extensions` constant | Low | Low (DRY) |
| 8 | Replace print with logging | Medium | High (testability, UX) |
| 9 | Settings dataclass | High | High (type safety) |

I'd recommend tackling items 4, 1, 7, and 2 first -- they're the best effort-to-impact ratio. Items 8 and 9 are larger but would significantly improve the codebase long-term.
