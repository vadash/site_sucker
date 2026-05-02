"""Offline HTML cleaner - strips online-only resources using BeautifulSoup."""

import re
from pathlib import Path

from bs4 import BeautifulSoup


def _remove_dom_nodes(soup: BeautifulSoup) -> int:
    """Remove unwanted DOM nodes using BeautifulSoup.

    Args:
        soup: BeautifulSoup object representing the HTML document.

    Returns:
        Number of nodes removed.
    """
    removed_count = 0

    # Remove MediaWiki load.php stylesheets
    for tag in soup.find_all('link', rel='stylesheet', href=re.compile(r'load\.php')):
        tag.decompose()
        removed_count += 1

    # Remove MediaWiki load.php scripts
    for tag in soup.find_all('script', src=re.compile(r'load\.php')):
        tag.decompose()
        removed_count += 1

    # Remove preconnect hints
    for tag in soup.find_all('link', rel='preconnect'):
        tag.decompose()
        removed_count += 1

    # Remove dns-prefetch hints
    for tag in soup.find_all('link', rel='dns-prefetch'):
        tag.decompose()
        removed_count += 1

    # Remove EditURI link
    for tag in soup.find_all('link', rel='EditURI'):
        tag.decompose()
        removed_count += 1

    # Remove RSS/Atom feed links
    for tag in soup.find_all('link', type=re.compile(r'application/(atom|rss)\+xml')):
        tag.decompose()
        removed_count += 1

    # Remove Matomo analytics scripts (by content)
    for tag in soup.find_all('script', string=re.compile(r'_paq')):
        tag.decompose()
        removed_count += 1

    # Remove Google Analytics bootstrap scripts (by src or content)
    for tag in soup.find_all('script', src=re.compile(r'google-analytics\.com', re.IGNORECASE)):
        tag.decompose()
        removed_count += 1
    for tag in soup.find_all('script', string=re.compile(r'google-analytics\.com', re.IGNORECASE)):
        tag.decompose()
        removed_count += 1

    # Remove noscript tracking pixels
    for tag in soup.find_all('noscript'):
        if tag.find('img', src=re.compile(r'(matomo|analytics|doubleclick|google-analytics)', re.IGNORECASE)):
            tag.decompose()
            removed_count += 1

    # Remove FontAwesome CDN loader script
    for tag in soup.find_all('script', src=re.compile(r'9a832b96e0\.js')):
        tag.decompose()
        removed_count += 1

    # Remove FontAwesome CDN link tags
    for tag in soup.find_all('link', href=re.compile(r'use\.fontawesome\.com', re.IGNORECASE)):
        tag.decompose()
        removed_count += 1

    # Remove scripts with FontAwesome CDN config
    for tag in soup.find_all('script', string=re.compile(r'FontAwesomeCdnConfig')):
        tag.decompose()
        removed_count += 1

    # Remove scripts with Google Analytics calls
    for tag in soup.find_all('script', string=re.compile(r"""ga\(['\"]create['""]""")):
        tag.decompose()
        removed_count += 1
    for tag in soup.find_all('script', string=re.compile(r"""ga\(['\"]send['""]""")):
        tag.decompose()
        removed_count += 1

    # Remove phpBB links
    for tag in soup.find_all('a', href=re.compile(r'(posting|tradegold|memberlist|search|ucp|mcp)\.php')):
        tag.decompose()
        removed_count += 1

    return removed_count


def _clean_inline_javascript(content: str) -> str:
    """Clean inline JavaScript code using regex (string-level operations).

    These are content-level replacements within script tag contents,
    not DOM operations, so regex is appropriate.

    Args:
        content: Serialized HTML string from BeautifulSoup.

    Returns:
        Cleaned HTML string.
    """
    # Remove Google Analytics inline calls (more flexible pattern)
    content = re.sub(r"""ga\(['\"]create['\"],\s*[^)]+\);?""", '', content)
    content = re.sub(r"""ga\(['\"]send['\"],\s*[^)]+\);?""", '', content)  # This should match both 'pageview' and "pageview"

    # Remove analytics push calls
    content = re.sub(r"""\.push\(\s*\[?\s*['"]trackPageView['"].*?\);?""", '', content)
    content = re.sub(r"""\.push\(\s*\[?\s*['"]enableLinkTracking['"].*?\);?""", '', content)

    # Remove FontAwesome CDN config (simple and complex patterns)
    content = re.sub(r'''window\.FontAwesomeCdnConfig\s*=\s*\{[^}]+\}\s*;''', '', content, flags=re.DOTALL)
    content = re.sub(r'''window\.FontAwesomeCdnConfig\s*=\s*\{[^}]+\}\s*;.*?function\s*\([^)]*\)[^{]*\{[^}]*\}\s*\([^)]*\)\s*;''', '', content, flags=re.DOTALL)

    return content


def repair_offline_html(output_dir: Path | str) -> int:
    """Strip online-only resources from HTML for offline browsing using BeautifulSoup.

    Removes or neutralizes HTML elements that block offline rendering:
    - Removes remote CSS/JS links (load.php) that weren't downloaded
    - Removes preconnect/dns-prefetch hints (useless offline)
    - Removes tracking/analytics scripts and pixels
    - Removes online-only navigation links (EditURI, Atom feeds, etc.)
    - Injects minimal fallback CSS

    Uses BeautifulSoup DOM operations for tag removal (safe, cannot corrupt HTML)
    and regex only for inline JavaScript content cleanup.

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
                content = f.read()
        except (IOError, OSError):
            continue

        if not content:
            continue

        # Parse with BeautifulSoup using lxml parser
        soup = BeautifulSoup(content, 'lxml')

        # 1. Remove unwanted DOM nodes
        removed = _remove_dom_nodes(soup)

        # 2. Inject fallback CSS before </head> (DOM operation, before serializing)
        if soup.head:
            style_tag = soup.new_tag('style')
            style_tag.string = (
                "/* Minimal fallback CSS for offline browsing */\n"
                "body { font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0; }\n"
                "#content { max-width: 960px; margin: 0 auto; padding: 20px; }\n"
                "h1, h2, h3 { margin-top: 1.5em; }\n"
                "a { color: #0645ad; text-decoration: none; }\n"
                "a:hover { text-decoration: underline; }\n"
                ".mw-body-content { padding: 1em; }"
            )
            soup.head.append(style_tag)

        # 3. Serialize to string once
        cleaned_content = str(soup)

        # 4. Clean inline JavaScript (regex is appropriate for string-level ops)
        cleaned_content = _clean_inline_javascript(cleaned_content)

        # 5. Only write if content changed
        if removed > 0 or cleaned_content != content:
            with open(html_file, "w", encoding="utf-8", newline="") as f:
                f.write(cleaned_content)
            modified_count += 1

    if modified_count > 0:
        print(f"  Cleaned {modified_count} HTML file(s) for offline use")

    return modified_count
