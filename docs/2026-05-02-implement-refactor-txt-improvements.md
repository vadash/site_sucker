
## Implementation Plan for refactor.txt improvements

I'll address all items from the review, split into 5 work items:

---

### 1. Bug Fix: Shallow copy of DEFAULT_SETTINGS (`settings.py`)

**Problem:** `DEFAULT_SETTINGS.copy()` is shallow — nested lists (`RejectPatterns`, `MediaExtensions`, `RejectDomains`) are shared references. Mutating them in user settings would corrupt the global defaults.

**Fix:** Add `import copy` and change `settings = DEFAULT_SETTINGS.copy()` to `settings = copy.deepcopy(DEFAULT_SETTINGS)` in `load_settings()`.

Also audit `merge_cli_overrides()` — it already does `result = settings.copy()` (shallow) and `list(result.get(...))` for RejectPatterns, which is safe because it creates a new list. But the shallow copy of the full dict still shares the nested lists. Fix: use `copy.deepcopy` there too.

---

### 2. Bug Fix: Thread Pool Anti-Pattern (`mirror.py`)

**Problem:** Creating/destroying a `ThreadPoolExecutor` per batch defeats thread pooling.

**Fix:** Replace the batch loop with a single `ThreadPoolExecutor` that submits all URLs at once:

```python
with ThreadPoolExecutor(max_workers=settings["ParallelDownloads"]) as executor:
    futures = {
        executor.submit(subprocess.run, [str(wget_path), *pass2_args, url], capture_output=True): url
        for url in url_list
    }
    for future in as_completed(futures):
        ...
```

Keep the batch progress reporting by tracking completed count.

---

### 3. Bug Fix: `re.DOTALL` in `repair_offline.py` violating AGENTS.md rule

**Problem:** `re.DOTALL` with `.*?` is equivalent to `[\s\S]*?`, which can cross `</script>` boundaries — exactly what AGENTS.md warns against.

**Fix:** Add the `(?:(?!</script>)[\s\S])*?` boundary guard to the affected patterns:
- "Remove MediaWiki load.php scripts"
- "Remove Matomo analytics scripts"
- "Remove FontAwesome CDN loader script"
- "Remove phpBB posting.php links" (and similar `<a>` patterns with `DOTALL` — these cross `</a>` boundaries, same class of bug)

---

### 4. Minor: Safer subprocess environment (`mirror.py`)

**Problem:** `os.environ.pop()` mutates the process-global environment.

**Fix:** Build a local `env` dict and pass it to all `subprocess.run()` calls:

```python
env = os.environ.copy()
for var in ["http_proxy", ...]:
    env.pop(var, None)
# pass env=env to subprocess.run()
```

---

### 5. Minor: Path safety in `repair_links.py`

**Problem:** `Path(html_dir).relative_to(output_dir)` can fail if paths are mixed absolute/relative.

**Fix:** Use `.resolve()` on both sides:
```python
rel_path = html_dir.resolve().relative_to(output_dir.resolve())
```

Same for the CSS section's `Path(css_dir).relative_to(output_dir)`.

---

### 6. Minor: DRY URL scheme check in `__main__.py`

**Problem:** URL protocol check (`http://`/`https://`) is done in both `interactive_prompt()` and `main()`.

**Fix:** Extract a `normalize_url(url: str) -> str` helper that prepends `https://` if missing. Use it once in `main()` before parsing, remove it from `interactive_prompt()` (the prompt already delegates to `main()`).

---

### Note on BeautifulSoup suggestion

The review recommends replacing regex with BeautifulSoup4. **I recommend deferring this** because:
1. The project explicitly uses **stdlib only** — no external runtime dependencies
2. It would be a massive architectural change touching every module
3. The current replacement pipeline + validation + rollback is a solid safety net
4. Adding `beautifulsoup4` + `lxml` as runtime deps changes the project's identity

If you want the BS4 refactor, I can plan it as a separate follow-up.

---

### Test updates

- Add test verifying `DEFAULT_SETTINGS` is not mutated after `load_settings()` + modification
- Add test for the single-pool parallel download behavior
- Verify all existing tests still pass
