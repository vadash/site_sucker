"""Offline HTML cleaner - strips online-only resources."""

import re
from pathlib import Path


FALLBACK_STYLE = '''

<style>
/* Minimal fallback CSS for offline browsing */
body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0; }
#content { max-width: 960px; margin: 0 auto; padding: 20px; }
h1, h2, h3 { margin-top: 1.5em; }
a { color: #0645ad; text-decoration: none; }
a:hover { text-decoration: underline; }
.mw-body-content { padding: 1em; }
</style>
'''


def repair_offline_html(output_dir: Path | str) -> int:
    """Strip online-only resources from HTML for offline browsing.

    Removes or neutralizes HTML elements that block offline rendering:
    - Removes remote CSS/JS links (load.php) that weren't downloaded
    - Removes preconnect/dns-prefetch hints (useless offline)
    - Removes tracking/analytics scripts and pixels
    - Removes online-only navigation links (EditURI, Atom feeds, etc.)
    - Injects minimal fallback CSS

    Args:
        output_dir: Path to the directory containing downloaded HTML files.

    Returns:
        Number of HTML files modified.
    """
    output_dir = Path(output_dir)
    print(f"\n[4/4] Stripping online-only resources for offline browsing...")

    html_files = list(output_dir.rglob("*.html")) + list(output_dir.rglob("*.htm"))
    modified_count = 0

    for html_file in html_files:
        try:
            with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        except IOError:
            continue

        if not raw:
            continue

        original = raw
        modified = False

        # Remove remote load.php stylesheets (MediaWiki ResourceLoader - never downloaded)
        raw = re.sub(
            r'<link\s+[^>]*rel=(")stylesheet(")[^>]*href="https?://[^"]*load\.php[^"]*\?[^"]*"[^>]*/?>',
            '', raw
        )
        if raw != original:
            modified = True
            original = raw

        # Remove remote load.php scripts
        raw = re.sub(
            r'<script[^>]*src="https?://[^"]*load\.php[^"]*"[^>]*>.*?</script>',
            '', raw, flags=re.DOTALL
        )
        if raw != original:
            modified = True
            original = raw

        # Remove preconnect hints (no effect offline)
        raw = re.sub(r'<link\s+[^>]*rel=(")preconnect(")[^>]*/?>', '', raw)
        if raw != original:
            modified = True
            original = raw

        # Remove dns-prefetch hints (no effect offline)
        raw = re.sub(r'<link\s+[^>]*rel=(")dns-prefetch(")[^>]*/?>', '', raw)
        if raw != original:
            modified = True
            original = raw

        # Remove EditURI link
        raw = re.sub(r'<link\s+[^>]*rel=(")EditURI(")[^>]*/?>', '', raw)
        if raw != original:
            modified = True
            original = raw

        # Remove alternate feed links (Atom, RSS - not available offline)
        raw = re.sub(
            r'<link\s+[^>]*rel=(")alternate(")[^>]*type="application/(atom|rss)\+xml"[^>]*/?>',
            '', raw
        )
        if raw != original:
            modified = True
            original = raw

        # Remove analytics/tracking scripts (Matomo, Google Analytics, etc.)
        raw = re.sub(
            r'<script[^>]*>\s*var\s+_paq\s*=\s*window\._paq.*?</script>',
            '', raw, flags=re.DOTALL
        )
        if raw != original:
            modified = True
            original = raw

        # Remove noscript tracking pixels
        raw = re.sub(
            r'<noscript>\s*<img[^>]*(?:matomo|analytics|doubleclick|google-analytics)[^>]*/?>\s*</noscript>',
            '', raw, flags=re.IGNORECASE
        )
        if raw != original:
            modified = True
            original = raw

        # Remove inline event logging and analytics calls
        raw = re.sub(r'\.push\(\s*\[?\s*(")trackPageView(").*?\);?', '', raw)
        raw = re.sub(r'\.push\(\s*\[?\s*(")enableLinkTracking(").*?\);?', '', raw)
        if raw != original:
            modified = True
            original = raw

        # phpBB-specific: Remove posting.php (reply forms)
        raw = re.sub(r'<a\s+[^>]*href="posting\.php[^"]*"[^>]*>.*?</a>', '', raw, flags=re.DOTALL)
        if raw != original:
            modified = True
            original = raw

        # phpBB-specific: Remove tradegold.php links
        raw = re.sub(r'<a\s+[^>]*href="tradegold\.php[^"]*"[^>]*>.*?</a>', '', raw, flags=re.DOTALL)
        if raw != original:
            modified = True
            original = raw

        # phpBB-specific: Remove memberlist.php links
        raw = re.sub(r'<a\s+[^>]*href="memberlist\.php[^"]*"[^>]*>.*?</a>', '', raw, flags=re.DOTALL)
        if raw != original:
            modified = True
            original = raw

        # phpBB-specific: Remove search.php links
        raw = re.sub(r'<a\s+[^>]*href="search\.php[^"]*"[^>]*>.*?</a>', '', raw, flags=re.DOTALL)
        if raw != original:
            modified = True
            original = raw

        # phpBB-specific: Remove ucp/mcp.php links
        raw = re.sub(r'<a\s+[^>]*href="(ucp|mcp)\.php[^"]*"[^>]*>.*?</a>', '', raw, flags=re.DOTALL)
        if raw != original:
            modified = True
            original = raw

        if modified:
            # Inject minimal fallback CSS before </head>
            raw = raw.replace('</head>', f'{FALLBACK_STYLE}</head>')

            with open(html_file, "w", encoding="utf-8", newline="") as f:
                f.write(raw)
            modified_count += 1

    if modified_count > 0:
        print(f"  Cleaned {modified_count} HTML file(s) for offline use")

    return modified_count
