## Root Cause Analysis

Two problems prevent images from loading in resume mode:

### Problem 1: `repair_internal_links()` only rewrites `<a href>` tags
The function (in `repair_links.py`) rewrites HTML-to-HTML navigation links, but ignores `<img src>`, `<script src>`, `<link href>` for internal resources. So all `<img src="/images/art/intro_amazon.jpg">` remain as absolute paths that resolve to the filesystem root on `file://`.

### Problem 2: CSS `url()` with absolute paths not fully converted
The CSS pipeline step 5 converts `url('/...')` to relative paths, but the CSS file lives in `images/stylesheet11.css` (not in `styles/`), so the relative prefix depth is wrong. The CSS references like `url(../styles/img/bg/tran.webp)` which assumes the CSS is at the site root, but it's actually in `images/`.

## Fix Plan

### 1. Extend `repair_internal_links()` to rewrite all internal resource URLs
Currently only handles `<a href>`. Add rewriting for:
- `<img src="/images/...">` → relative path
- `<script src="/js/...">` → relative path  
- `<link href="/styles/...">` → relative path
- `<video src>`, `<audio src>`, `<source src>` (same pattern)

The logic is identical to the existing `<a>` rewriting: resolve to absolute URL → map to local file → compute relative path from HTML file to local file.

### 2. Fix CSS depth calculation for absolute path conversion
The CSS `url('/...')` → `url('../...')` conversion in `repair_external_links()` calculates depth from the CSS file's position. The CSS file `images/stylesheet11.css` is 1 level deep, so `../` would go to the site root. But the CSS references `../styles/img/bg/tran.webp` which is already a relative path from the original site location. Need to verify the depth calculation is correct.

Actually, looking more carefully at the CSS output, the `url(../styles/img/bg/...)` references are already relative paths (not absolute). The pipeline step 5 only handles `url('/...')` (absolute paths starting with `/`). The existing relative paths like `url(../styles/img/bg/tran.webp)` are left as-is, which is correct IF the CSS file hasn't moved. But the CSS was moved from the site root to `images/`, so those relative paths now resolve incorrectly.

**Fix**: After step 5 (absolute path conversion), add a new step that converts **all remaining relative `url()` paths** to account for the CSS file's actual location vs. its original location. Or more simply: if the CSS file was placed by wget in a non-standard location, recalculate relative paths based on the CSS file's actual position in the output directory.

### Files to modify:
1. **`src/site_sucker/repair_links.py`** - Extend `repair_internal_links()` to handle `<img>`, `<script>`, `<link>`, `<video>`, `<audio>`, `<source>` tags
2. **Tests** - Add test cases for the new tag rewriting