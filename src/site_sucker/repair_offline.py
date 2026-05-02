"""Offline HTML cleaner - strips online-only resources."""

import re
from pathlib import Path

from site_sucker.replacement_pipeline import ReplacementStep, run_replacement_pipeline


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


def repair_offline_html(output_dir: Path | str, log_dir: Path | None = None) -> int:
    """Strip online-only resources from HTML for offline browsing.

    Removes or neutralizes HTML elements that block offline rendering:
    - Removes remote CSS/JS links (load.php) that weren't downloaded
    - Removes preconnect/dns-prefetch hints (useless offline)
    - Removes tracking/analytics scripts and pixels
    - Removes online-only navigation links (EditURI, Atom feeds, etc.)
    - Injects minimal fallback CSS

    Args:
        output_dir: Path to the directory containing downloaded HTML files.
        log_dir: Optional directory to log failed replacements. If None, failures are reverted but not logged.

    Returns:
        Number of HTML files modified.
    """
    output_dir = Path(output_dir)
    log_dir = Path(log_dir) if log_dir else None

    print(f"\n[4/4] Stripping online-only resources for offline browsing...")

    # Define all replacement steps as a list for easy maintenance
    replacement_steps = [
        ReplacementStep(
            name="Remove MediaWiki load.php stylesheets",
            pattern=re.compile(
                r'<link\s+[^>]*rel=(")stylesheet(")[^>]*href="https?://[^"]*load\.php[^"]*\?[^"]*"[^>]*/?>'
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove MediaWiki load.php scripts",
            pattern=re.compile(
                r'<script[^>]*src="https?://[^"]*load\.php[^"]*"[^>]*>.*?</script>',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove preconnect hints",
            pattern=re.compile(r'<link\s+[^>]*rel=(")preconnect(")[^>]*/?>'),
            replacement='',
        ),
        ReplacementStep(
            name="Remove dns-prefetch hints",
            pattern=re.compile(r'<link\s+[^>]*rel=(")dns-prefetch(")[^>]*/?>'),
            replacement='',
        ),
        ReplacementStep(
            name="Remove EditURI link",
            pattern=re.compile(r'<link\s+[^>]*rel=(")EditURI(")[^>]*/?>'),
            replacement='',
        ),
        ReplacementStep(
            name="Remove alternate feed links (Atom/RSS)",
            pattern=re.compile(
                r'<link\s+[^>]*rel=(")alternate(")[^>]*type="application/(atom|rss)\+xml"[^>]*/?>'
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove Matomo analytics scripts",
            pattern=re.compile(
                r'<script[^>]*>\s*var\s+_paq\s*=\s*window\._paq.*?</script>',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove Google Analytics bootstrap script",
            pattern=re.compile(
                r'<script[^>]*(?:src=["\'][^"\']*google-analytics\.com[^"\']*["\'])?[^>]*>(?:(?!</script>)[\s\S])*?google-analytics\.com(?:(?!</script>)[\s\S])*?</script>',
                flags=re.IGNORECASE,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove Google Analytics inline calls (create)",
            pattern=re.compile(r"ga\(['\"]create['\"],\s*[^)]+\);?"),
            replacement='',
        ),
        ReplacementStep(
            name="Remove Google Analytics inline calls (send)",
            pattern=re.compile(r"ga\(['\"]send['\"],\s*[^)]+\);?"),
            replacement='',
        ),
        ReplacementStep(
            name="Remove noscript tracking pixels",
            pattern=re.compile(
                r'<noscript>\s*<img[^>]*(?:matomo|analytics|doubleclick|google-analytics)[^>]*/?>\s*</noscript>',
                flags=re.IGNORECASE,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove inline analytics push calls (trackPageView)",
            pattern=re.compile(r'\.push\(\s*\[?\s*(")trackPageView(").*?\);?'),
            replacement='',
        ),
        ReplacementStep(
            name="Remove inline analytics push calls (enableLinkTracking)",
            pattern=re.compile(r'\.push\(\s*\[?\s*(")enableLinkTracking(").*?\);?'),
            replacement='',
        ),
        ReplacementStep(
            name="Remove FontAwesome CDN loader script",
            pattern=re.compile(
                r'<script[^>]*src=["\'].*?9a832b96e0\.js["\'][^>]*>.*?</script>',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove FontAwesome CDN link tags",
            pattern=re.compile(
                r'<link[^>]*href=["\']https://use\.fontawesome\.com/[^"\']+["\'][^>]*/?>',
                flags=re.IGNORECASE,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove FontAwesome CDN config (complex)",
            pattern=re.compile(
                r'window\.FontAwesomeCdnConfig\s*=\s*\{.*?\};.*?function\s*\([^)]*\)[^{]*\{.*?\}\s*\([\s\S]*?\);',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove FontAwesome CDN config (simple)",
            pattern=re.compile(
                r'window\.FontAwesomeCdnConfig\s*=\s*\{.*?\};',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove phpBB posting.php links",
            pattern=re.compile(
                r'<a\s+[^>]*href="posting\.php[^"]*"[^>]*>.*?</a>',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove phpBB tradegold.php links",
            pattern=re.compile(
                r'<a\s+[^>]*href="tradegold\.php[^"]*"[^>]*>.*?</a>',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove phpBB memberlist.php links",
            pattern=re.compile(
                r'<a\s+[^>]*href="memberlist\.php[^"]*"[^>]*>.*?</a>',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove phpBB search.php links",
            pattern=re.compile(
                r'<a\s+[^>]*href="search\.php[^"]*"[^>]*>.*?</a>',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
        ReplacementStep(
            name="Remove phpBB ucp/mcp.php links",
            pattern=re.compile(
                r'<a\s+[^>]*href="(ucp|mcp)\.php[^"]*"[^>]*>.*?</a>',
                flags=re.DOTALL,
            ),
            replacement='',
        ),
    ]

    html_files = list(output_dir.rglob("*.html")) + list(output_dir.rglob("*.htm"))
    modified_count = 0
    total_steps_applied = 0

    for html_file in html_files:
        # Run the replacement pipeline
        steps_applied = run_replacement_pipeline(
            html_file,
            replacement_steps,
            log_dir,
        )

        if steps_applied > 0:
            modified_count += 1
            total_steps_applied += steps_applied

            # Inject minimal fallback CSS before </head>
            try:
                with open(html_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if '</head>' in content:
                    content = content.replace('</head>', f'{FALLBACK_STYLE}</head>')
                    with open(html_file, "w", encoding="utf-8", newline="") as f:
                        f.write(content)
            except (IOError, OSError):
                pass

    if modified_count > 0:
        print(f"  Cleaned {modified_count} HTML file(s) for offline use")

    if log_dir and log_dir.exists():
        failure_count = len([d for d in log_dir.iterdir() if d.is_dir()])
        if failure_count > 0:
            print(f"  Warning: {failure_count} replacement(s) failed and were logged to {log_dir}")

    return modified_count
