
## Findings & Plan

### Bugs / Issues Needing Attention

1. **`repair_offline.py:203` — double-increment bug**: `processed` is the `enumerate` loop variable (already 1-based), but then `processed += 1` increments it again. The progress counter skips every other number and overshoots `total`. Fix: remove the manual `+= 1`.

2. **`media.py:112` — dead expression**: `url_count + css_url_count` is a bare expression (result discarded). Likely meant to be assigned or removed.

3. **`repair_html.py:179-180` — dead computation in `rewrite_internal_html_links`**: `depth` is computed but never used (the `len(rel_path.parts)` result is discarded). Should be removed.

4. **`download.py:40` — duplicated env-cleaning logic**: Manually copies `os.environ` and strips proxy vars, duplicating `wget.get_clean_env()`. Should call the shared helper.

---

### 1. Unified Progress Tracker (new module `progress.py`)

All pipeline stages will use a single reusable progress helper that prints the same-line counter format you showed:

```
[4/4] Stripping online-only resources for offline browsing... (4514 file(s))
  [2273/4514]
```

```python
# site_sucker/progress.py
import sys

class ProgressTracker:
    def __init__(self, total: int) -> None:
        self.total = total
        self._current = 0

    def update(self, current: int) -> None:
        self._current = current
        print(f"\r  [{current}/{self.total}]", end="", flush=True)

    def tick(self) -> None:
        self._current += 1
        self.update(self._current)

    def finish(self) -> None:
        if self.total > 0:
            print(flush=True)  # newline
```

Stages that will get progress tracking (currently missing it):

| Stage | Module | Currently has progress? |
|---|---|---|
| Pass 1 wget | `crawler.py` WgetCrawler | No (wget prints its own) |
| Pass 1 BFS | `resume.py` ResumeCrawler | Yes (custom inline `print`) — will migrate |
| Pass 2 media download | `download.py` | Partial (per-URL log, no counter line) |
| Pass 2 media scan | `media.py` | No |
| Pass 3 HTML rewrite | `repair_links.py` | No |
| Pass 3 CSS rewrite | `repair_css.py` | No |
| Pass 4 offline strip | `repair_offline.py` | Yes (has the bug) — will migrate |
| Internal link repair | `repair_html.py` | No |

I'll add the `ProgressTracker` to: **repair_offline** (fix bug), **repair_links/repair_html** (HTML rewrite loop), **repair_css** (CSS loop), **media** (scan loop), **download** (parallel download), and **resume** (BFS crawl). Wget mode pass 1 is a subprocess so it stays as-is.

---

### 2. DRY Refactors

| What | Where | Action |
|---|---|---|
| Proxy env cleaning | `download.py:40` duplicates `wget.get_clean_env()` | Replace with `get_clean_env()` call |
| Depth-from-output-dir calculation | `repair_html.py` lines 108-112 and 177-180 | Extract to `paths.py::relative_depth(file_path, output_dir)` helper |
| Dead expression | `media.py:112` | Remove bare `url_count + css_url_count` |
| Dead depth computation | `repair_html.py:179-180` | Remove unused variable |

---

### 3. Cyclomatic Complexity Reduction

Current radon report shows 11 functions at grade C (complexity > 10). Target: all functions at B or below (<=10).

| Function | CC | Strategy |
|---|---|---|
| `get_external_media` (media.py) | C | Split into `_scan_html_media` + `_scan_css_media` helpers |
| `rewrite_external_html_links` (repair_html.py) | C | Extract CORS-stripping into `_strip_cors_attrs(soup)` |
| `rewrite_internal_html_links` (repair_html.py) | C | Extract `<a>` rewriting loop into `_rewrite_anchor_tags()` |
| `run_replacement_pipeline` (replacement_pipeline.py) | C | Extract step-application into `_apply_step()` |
| `ResumeCrawler.run` (resume.py) | C | Extract download-or-cache logic into `_process_url()` |
| `_parse_range_expression` (settings.py) | C | Minor: early-return restructuring |
| `_strip_jsonc_comments` (settings.py) | C | Minor: extract line-comment stripping to helper |
| `merge_cli_overrides` (settings.py) | C | Extract reject expansion loop to helper |
| `should_reject_url` (url_filter.py) | C | Already flat guard clauses — will try to simplify |
| `print_validation_results` (validate_html.py) | C | Extract repeated block-printing into `_print_issue_block()` |
| `validate_html_files` (validate_html.py) | C | Extract per-file accumulation into helper |

---

### 4. Files Changed Summary

| File | Changes |
|---|---|
| **NEW** `progress.py` | `ProgressTracker` class |
| `repair_offline.py` | Fix double-increment bug, use `ProgressTracker` |
| `resume.py` | Use `ProgressTracker`, extract `_process_url()` |
| `download.py` | Use `get_clean_env()`, add `ProgressTracker` |
| `media.py` | Remove dead expression, split into helpers, add progress |
| `repair_html.py` | Remove dead code, extract helpers, add progress |
| `repair_links.py` | Add progress to HTML rewrite loop |
| `repair_css.py` | Add progress to CSS loop |
| `replacement_pipeline.py` | Extract `_apply_step()` |
| `settings.py` | Extract helpers for complexity reduction |
| `url_filter.py` | Simplify guard clauses |
| `validate_html.py` | Extract `_print_issue_block()` helper |
| `paths.py` | Add `relative_depth()` helper |
| Tests | Update any tests affected by signature changes; add tests for `ProgressTracker` |
