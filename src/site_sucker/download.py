"""External media downloader using parallel wget subprocess calls."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from site_sucker.settings import Settings
from site_sucker.wget import build_wget_args, get_wget_path


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
        print("No external media URLs found. Skipping download.")
        return []

    # Create media subdirectory
    media_dir.mkdir(exist_ok=True)

    print(f"\nDownloading external media (parallel: {settings.parallel_downloads})...")

    # Disable proxies for subprocess calls
    env = os.environ.copy()
    for var in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
        env.pop(var, None)

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

    print(f"  Downloading {total_urls} external media file(s)...")

    failed_urls = []

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

        completed_count = 0
        for future in as_completed(futures):
            url = futures[future]
            completed_count += 1
            print(f"  [{completed_count}/{total_urls}] {url}")

            try:
                result = future.result()
                if result.returncode != 0:
                    failed_urls.append(url)
                    stderr = result.stderr.decode(errors="replace").strip()
                    if stderr:
                        print(f"    wget error: {stderr.splitlines()[-1]}")
            except Exception:
                failed_urls.append(url)

    if failed_urls:
        print(f"  {len(failed_urls)} download(s) failed.")

    return failed_urls
