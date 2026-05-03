"""External media downloader using parallel wget subprocess calls."""

import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from site_sucker.progress import ProgressTracker
from site_sucker.settings import Settings
from site_sucker.wget import build_wget_args, get_clean_env, get_wget_path

logger = logging.getLogger(__name__)


def download_external_media(
    ext_urls: set[str],
    media_dir: Path,
    settings: Settings,
) -> list[str]:
    """Download external media URLs using parallel wget subprocess calls.

    Args:
        ext_urls: Set of external media URLs to download.
        media_dir: Directory to save downloaded media files.
        settings: Settings instance.

    Returns:
        List of failed URLs (if any).
    """
    if not ext_urls:
        logger.info("No external media URLs found. Skipping download.")
        return []

    # Create media subdirectory
    media_dir.mkdir(exist_ok=True)

    logger.info("Downloading external media (parallel: %d)...", settings.parallel_downloads)

    # Disable proxies for subprocess calls
    env = get_clean_env()

    wget_path = get_wget_path()

    wget_args = build_wget_args(
        settings,
        media_dir,
        no_link_conversion=True,
        extra_args=[
            "--level=1",
            "--no-directories",
            "-nc",
        ],
    )

    # Process all URLs in parallel using a single thread pool
    url_list = list(ext_urls)
    total_urls = len(url_list)

    logger.info("  Downloading %d external media file(s)...", total_urls)

    failed_urls = []
    progress = ProgressTracker(total_urls)

    with ThreadPoolExecutor(max_workers=settings.parallel_downloads) as executor:
        futures = {
            executor.submit(
                subprocess.run,
                [str(wget_path), *wget_args, url],
                capture_output=True,
                env=env,
            ): url
            for url in url_list
        }

        for completed_count, future in enumerate(as_completed(futures), start=1):
            url = futures[future]

            try:
                result = future.result()
                if result.returncode != 0:
                    failed_urls.append(url)
                    stderr = result.stderr.decode(errors="replace").strip()
                    if stderr:
                        logger.warning("    wget error: %s", stderr.splitlines()[-1])
            except Exception:
                failed_urls.append(url)

            progress.update(completed_count)

    progress.finish()

    if failed_urls:
        logger.warning("  %d download(s) failed.", len(failed_urls))

    return failed_urls
