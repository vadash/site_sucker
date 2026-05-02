
## BeautifulSoup4 Refactor Plan

### Goal
Replace regex-based HTML processing with `beautifulsoup4` + `lxml` for safer, simpler, and more maintainable HTML manipulation. CSS processing remains regex-based (appropriate for CSS).

### New Dependency
- Add `beautifulsoup4` and `lxml` to `pyproject.toml` as runtime dependencies.

### Step-by-step Plan

---

#### 1. Add dependencies to `pyproject.toml`
Add `beautifulsoup4>=4.12` and `lxml>=5.0` to `dependencies = [...]`.

---

#### 2. Refactor `repair_offline.py` — BS4 for HTML, keep regex for inline JS snippets
The biggest change. Replace all HTML tag-removal regex patterns with BS4 `.find_all()` + `.decompose()`:

| Current regex step | BS4 replacement |
|---|---|
| Remove MediaWiki load.php stylesheets | `soup.find_all('link', rel='stylesheet', href=re.compile(r'load\.php'))` → decompose |
| Remove MediaWiki load.php scripts | `soup.find_all('script', src=re.compile(r'load\.php'))` → decompose |
| Remove preconnect hints | `soup.find_all('link', rel='preconnect')` → decompose |
| Remove dns-prefetch hints | `soup.find_all('link', rel='dns-prefetch')` → decompose |
| Remove EditURI link | `soup.find_all('link', rel='EditURI')` → decompose |
| Remove RSS/Atom feeds | `soup.find_all('link', type=re.compile(r'application/(atom\|rss)\+xml'))` → decompose |
| Remove Matomo analytics scripts | `soup.find_all('script', string=re.compile(r'_paq'))` → decompose |
| Remove Google Analytics bootstrap | `soup.find_all('script', string=re.compile(r'google-analytics'))` → decompose |
| Remove FontAwesome CDN loader | `soup.find_all('script', src=re.compile(r'9a832b96e0\.js'))` → decompose |
| Remove FontAwesome CDN link tags | `soup.find_all('link', href=re.compile(r'use\.fontawesome\.com'))` → decompose |
| Remove phpBB links (posting/trade/member/search/ucp/mcp) | `soup.find_all('a', href=re.compile(r'(posting\|tradegold\|memberlist\|search\|ucp\|mcp)\.php'))` → decompose |
| Inject fallback CSS | `soup.head.append(BeautifulSoup(FALLBACK_STYLE, 'lxml'))` |

**Keep regex** for inline JS removal (ga('create'...), .push(['trackPageView']...), FontAwesomeCdnConfig) — these are string-level operations within script tag contents, not DOM operations. Apply these via a small regex pass on the serialized BS4 output.

**New architecture for `repair_offline_html()`:**
1. Parse HTML with BS4 (`lxml` parser)
2. Remove unwanted DOM nodes (decompose)
3. Serialize back to string
4. Apply remaining inline-JS regex cleanup on the string
5. Write result

This eliminates the need for `replacement_pipeline.py` in `repair_offline.py` entirely for HTML DOM operations. No more `ReplacementStep` list, no more rollback/validate cycle for HTML — BS4 cannot corrupt the DOM.

---

#### 3. Refactor `repair_links.py` — BS4 for HTML URL rewriting + CORS stripping
Replace regex URL rewriting in HTML files with BS4:

- Rewrite `href`/`src` attributes on `<link>`, `<script>`, `<img>` tags using BS4 attribute access
- Strip `integrity` and `crossorigin` attributes via `del tag['integrity']`, `del tag['crossorigin']`

**Keep `replacement_pipeline.py` for CSS processing** — all CSS-related steps (@import inlining, absolute path conversion, external url() stripping) remain regex. This is the correct tool for CSS.

---

#### 4. Refactor `media.py` — BS4 for HTML scanning
Replace regex `href/src` attribute scanning in HTML with BS4:

```python
for tag in soup.find_all(['img', 'script', 'link', 'video', 'audio', 'source']):
    for attr in ('src', 'href', 'data-src'):
        url = tag.get(attr)
        # ... existing filtering logic
```

**Keep regex for CSS `url()` scanning** — CSS files are not HTML.

---

#### 5. Simplify `validate_html.py`
Since BS4 + lxml parses broken HTML gracefully, simplify validation:
- Remove regex-based tag detection (`</head>`, `<body>`, `</body>`)
- Use BS4 to check: `soup.find('head')`, `soup.find('body')` exist and body has text content
- Keep `validate_html_files()` and `validate_html_string()` API unchanged for compatibility
- This module is still used by `mirror.py` after pass 1 to detect truncated downloads

---

#### 6. Update `replacement_pipeline.py` — CSS-only usage
This module remains valuable for CSS processing. Changes:
- No code changes needed — it's already well-structured
- Update docstring to clarify it's now CSS-only (HTML uses BS4)
- The pipeline is still used by `repair_links.py` for CSS @import inlining, absolute path conversion, and external URL stripping

---

#### 7. Update `mirror.py`
- Minor: remove `log_dir` passing to `repair_offline_html()` since BS4 doesn't need rollback logging
  - Actually, keep `log_dir` param for future CSS logging. But `repair_offline_html` no longer needs it since it uses BS4. Remove it from that function signature.
- Keep `log_dir` for `repair_external_links()` since CSS pipeline still uses it

---

#### 8. Update tests
All existing tests should pass with minimal changes:
- `test_repair_offline.py` — tests check output content, not implementation. Most should pass as-is since they verify end results (e.g., "load.php not in output").
- `test_repair_links.py` — same, tests check rewritten URLs. BS4 rewrites should produce same results.
- `test_media.py` — tests check extracted URL sets. BS4 parsing should find same URLs.
- `test_replacement_pipeline.py` — untouched, still used for CSS.
- `test_validate_html.py` — update to work with BS4-based validation (API stays the same).
- May need minor adjustments for whitespace/formatting differences between regex and BS4 serialization.

---

#### 9. Update `AGENTS.md`
- Remove "Regex Pitfalls" section (no longer relevant for HTML)
- Update "Replacement Pipeline & Safety" section to clarify HTML uses BS4, CSS uses regex pipeline
- Update module descriptions for `repair_offline.py`, `repair_links.py`, `media.py`, `validate_html.py`
- Update "Dependencies" section to include `beautifulsoup4` and `lxml`
- Remove references to `ReplacementStep` in HTML processing contexts

---

### Files Modified (summary)
| File | Change |
|---|---|
| `pyproject.toml` | Add beautifulsoup4, lxml dependencies |
| `repair_offline.py` | Rewrite with BS4 DOM operations |
| `repair_links.py` | BS4 for HTML, keep pipeline for CSS |
| `media.py` | BS4 for HTML scanning, keep regex for CSS |
| `validate_html.py` | BS4-based tag detection |
| `mirror.py` | Remove log_dir from repair_offline call |
| `AGENTS.md` | Update to reflect BS4 architecture |
| `tests/test_repair_offline.py` | Adjust for BS4 output format |
| `tests/test_repair_links.py` | Adjust for BS4 output format |
| `tests/test_media.py` | Adjust if needed |
| `tests/test_validate_html.py` | Adjust for BS4 validation |
