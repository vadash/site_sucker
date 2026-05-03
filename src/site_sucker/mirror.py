"""Main mirroring pipeline orchestrator."""

from pathlib import Path

from site_sucker.crawler import BFSCrawler, CrawlResult, WgetCrawler
from site_sucker.download import download_external_media
from site_sucker.media import get_external_media
from site_sucker.repair_links import repair_external_links, repair_internal_links
from site_sucker.repair_offline import repair_offline_html
from site_sucker.settings import Settings


def invoke_site_mirror(
    url: str,
    output_dir: Path | str,
    target_domain: str,
    settings: Settings,
    resume: bool = False,
) -> list[str]:
    """Execute the four-pass site mirroring process.

    Orchestrates:
    1. Pass 1: Full site mirror using wget --mirror (or resume mode with BFS crawler)
    2. Pass 2: Download external media with parallelism
    3. Pass 3: Rewrite external URLs in HTML to local paths
    4. Pass 4: Strip online-only resources for offline browsing

    Args:
        url: The base URL to mirror.
        output_dir: Output directory path.
        target_domain: Primary domain (used to filter external media).
        settings: Configuration dictionary.
        resume: If True, use Python BFS crawler instead of wget --mirror.

    Returns:
        List of failed URLs (if any).
    """
    output_dir = Path(output_dir)
    failed_urls = []

    # ── PASS 1: Full site mirror (unified crawler interface) ───────────────────────
    crawler_cls = BFSCrawler if resume else WgetCrawler
    crawler = crawler_cls(url, output_dir, target_domain, settings)
    crawl_result: CrawlResult = crawler.run()

    # If BFS mode was used, rewrite internal HTML-to-HTML links
    # (wget didn't run, so --convert-links wasn't applied)
    if crawl_result.needs_internal_link_repair:
        repair_internal_links(output_dir, target_domain)

    # Create log directory for failed replacements (CSS pipeline only)
    log_dir = output_dir / "logs"

    # ── PASS 2: External media with parallelism ────────────────────────────────
    ext_urls = get_external_media(output_dir, target_domain, settings)

    if not ext_urls:
        print("No external media URLs found. Skipping pass 2 & 3.")
        # Still run pass 4 to clean offline HTML
        repair_offline_html(output_dir)
        return failed_urls

    # Create media subdirectory
    media_dir = output_dir / "images"
    media_dir.mkdir(exist_ok=True)

    # Download external media files
    failed_urls = download_external_media(ext_urls, media_dir, settings)

    # ── PASS 3: Rewrite external URLs to local paths ────────────────────
    repair_external_links(output_dir, media_dir, ext_urls, log_dir)

    # ── PASS 4: Strip online-only resources for offline browsing ────────────────
    repair_offline_html(output_dir)

    return failed_urls
