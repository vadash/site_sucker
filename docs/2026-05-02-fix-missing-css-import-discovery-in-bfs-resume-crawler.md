
## Root Cause

The BFS crawler's `discover_links()` only parses **HTML** files for links (`<a>`, `<img>`, `<link>`, etc.). It does **not** parse **CSS** files for `@import` references.

In this site, `styles/stylesheet08.css` is discovered (it's a `<link>` tag in HTML), but it contains:
```css
@import url("colors.css");
@import url("docs08.css");
```

These two CSS files (`colors.css` and `docs08.css`) are never discovered by the BFS crawler, so they're never downloaded. Later, in pass 3 (`repair_links.py`), the `@import` inlining step finds them missing and writes `/* FILE NOT FOUND */` comments, resulting in a broken-looking site.

The **old wget download** worked because wget's `--page-requisites` flag parses CSS `@import` chains and downloads all referenced stylesheets recursively.

## Fix: Add CSS @import discovery to BFS crawler

Add a new function `discover_css_imports()` in `resume.py` that:
1. Parses CSS files for `@import url(...)` / `@import "..."` patterns
2. Returns the resolved internal URLs (same domain filtering as HTML discovery)

Then in `crawl_loop()`, after downloading a CSS file, also call `discover_css_imports()` and enqueue discovered CSS URLs.

### Changes in `src/site_sucker/resume.py`:

1. **New function `discover_css_imports(css_file, base_url, target_domain, reject_patterns, reject_domains)`**:
   - Reads the CSS file
   - Regex-matches `@import url("...")` and `@import "..."` patterns
   - Resolves relative URLs against `base_url`
   - Filters to same domain, applies reject patterns
   - Returns `set[str]` of absolute URLs

2. **Update `crawl_loop()`**:
   - After resolving `actual_path` for a downloaded/cached file
   - If the file is a CSS file (`.css` extension), call `discover_css_imports()` and enqueue results
   - Currently only HTML files are parsed for links — CSS files are now also parsed for `@import` chains

### Testing:

- Add test case in `tests/test_resume.py` for `discover_css_imports()` covering:
  - `@import url("relative.css")`
  - `@import "relative.css"`
  - External imports (should be filtered out)
  - Reject patterns applied
  - Multiple imports in one file
