
## Changes

### 1. Fix regex bug in `src/site_sucker/wget.py`

The hardcoded `viewtopic\.php.*&p=\d+|viewtopic\.php\?p=\d+` uses `\d` which wget's POSIX ERE does not support (it matches literal "d" instead of digits). Replace `\d+` with `[0-9]+`:

```python
reject_parts.append(r"viewtopic\.php.*&p=[0-9]+|viewtopic\.php\?p=[0-9]+")
```

### 2. Update `settings.jsonc` RejectPatterns

**Remove** (replaced by broader patterns or `search.php`):
- `"sr=posts"` — superseded by `"search.php"` (search page blocked entirely)
- `"sr=topics"` — superseded by `"search.php"`
- `"view=unread"` — replaced by broader `"view="`

**Add** (new phpBB duplicate-trap patterns):
- `"search.php"` — blocks Active Topics, Unread Posts, user post histories (main source of duplicate link permutations)
- `"view="` — blocks view=unread, view=next, view=previous, view=print
- `"hilit="` — blocks search highlighting duplicates
- `"style="` — blocks theme-switching duplicates
- `"mark="` — blocks "mark forums read" duplicates

### 3. Update test in `tests/test_wget.py`

Update `test_build_wget_args_with_reject_patterns` to verify the corrected `[0-9]+` pattern instead of `\d+`.

No other test changes needed — no new code paths are being added, just regex/data fixes.
