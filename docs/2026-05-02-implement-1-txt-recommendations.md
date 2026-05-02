## Implementation Plan (from 1.txt analysis)

### 1. Add phpBB sort + sid patterns to `settings.jsonc`
Add 4 new entries to the `RejectPatterns` array under the phpBB section:
```jsonc
"&sk=",               // Sort Key (Author, Time, Subject) - prevents re-downloading forum indexes in every sort order
"&sd=",               // Sort Direction (Ascending, Descending) - same as above
"&st=",               // Sort Time (1 day, 7 days, etc.) - same as above
// ─── ⚠️ EXPERIMENTAL: sid= Session ID blocking ─────────────────────
// phpBB appends &sid=<32-char-hex> to every URL on the first page load.
// This can cause infinite crawl loops. Blocking it is generally safe for
// guest/archival crawls because Wget handles cookies natively and drops
// sid after the first few requests. HOWEVER: if the crawler stops
// discovering ANY links after adding this, REMOVE THIS PATTERN IMMEDIATELY
// — it means the starting page links all carry sid= and Wget rejects them all.
"&sid=",              // Session IDs (infinite loop trap — TEST FIRST!)
```

### 2. Add `-nc` (no-clobber) to Pass 2 in `mirror.py`
In the `pass2_args` block (~line 86), add `"-nc"` to `extra_args`:
```python
pass2_args = build_wget_args(
    settings,
    media_dir,
    no_link_conversion=True,
    extra_args=[
        "--level=1",
        "--no-directories",
        "-nc",                 # Skip already-downloaded media for resume support
    ],
)
```
**Rationale**: Pass 2 is a flat list of known media URLs — no link discovery needed. `-nc` means if you restart a partial crawl, already-downloaded images are skipped instantly. Pass 1 keeps `-N` because it *must* re-download HTML to discover new links.

### 3. Update tests
- **`test_wget.py`**: Add a test verifying the new reject patterns (`&sk=`, `&sd=`, `&st=`, `&sid=`) appear in the built wget args when present in settings.
- Existing `test_build_wget_args_with_reject_patterns` should still pass since the hardcoded `viewtopic` patterns are unchanged.

### 4. Run test suite
Run `pytest` to verify no regressions.
