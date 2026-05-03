## Changes to `resume.py` — BFS crawl loop logging

### 1. Log wget stderr on failure (the debug fix)

Currently on wget exit code != 0 and != 8, only the code is printed. Change to also log `result.stderr` (decoded, stripped) so next time we see the actual HTTP error:

```
Warning: wget exited with code 4
  → https://forum.median-xl.com/viewtopic.php?p=588335
  stderr: Unable to establish SSL connection.
```

### 2. Reduce per-URL console output

**Before** — every URL prints a full line (your log is 200+ lines):
```
[177] Using cached (depth=2): https://forum.median-xl.com/viewtopic.php@f=40&t=22267&start=130.html
[178] Using cached (depth=2): https://forum.median-xl.com/viewtopic.php@f=40&t=22267.html
[184] Downloading (depth=2): https://forum.median-xl.com/viewtopic.php?p=588335
    Warning: wget exited with code 4
```

**After** — only download events and errors are printed. Cached hits use an inline progress counter:
```
[*] BFS crawl: forum.median-xl.com (depth=unlimited)
  [184] GET  viewtopic.php?p=588335
         ↳ wget exit 4 — Unable to establish SSL connection.
  [199] GET  viewtopic.php?p=587094
  ...
[*] BFS complete: 220 visited, 15 downloaded (4 failures)
```

Key changes:
- **Remove** per-URL "Using cached" lines entirely — replace with a running counter printed via `\r` (carriage return overwrite) showing `cached: N, downloaded: M`
- **Condense** "Downloading" to just `GET <short path>` (strip domain, show path only)
- **Show stderr** inline on wget failure
- **Remove** the `[iteration]` counter — not useful for debugging
- **Keep** header and summary lines as-is
- **Keep** "Error: File not found" line (rare, important)
