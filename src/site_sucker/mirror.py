"""Main mirroring pipeline orchestrator."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from site_sucker.media import get_external_media
from site_sucker.repair_links import repair_external_links
from site_sucker.repair_offline import repair_offline_html
from site_sucker.report import write_site_report
from site_sucker.validate_html import print_validation_results, validate_html_files
from site_sucker.wget import build_wget_args, get_wget_path


def invoke_site_mirror(
    url: str,
    output_dir: Path | str,
    target_domain: str,
    settings: dict[str, Any],
) -> list[str]:
    """Execute the two-pass site mirroring process.

    Orchestrates:
    1. Pass 1: Full site mirror using wget --mirror
    2. Pass 2: Download external media with parallelism
    3. Pass 3: Rewrite external URLs in HTML to local paths
    4. Pass 4: Strip online-only resources for offline browsing

    Args:
        url: The base URL to mirror.
        output_dir: Output directory path.
        target_domain: Primary domain (used to filter external media).
        settings: Configuration dictionary.

    Returns:
        List of failed URLs (if any).
    """
    output_dir = Path(output_dir)
    failed_urls = []

    # Disable proxies
    for var in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
        os.environ.pop(var, None)

    wget_path = get_wget_path()

    # ── PASS 1: Full site mirror ───────────────────────────────────────────────
    print(f"\n[1/4] Mirroring {url} (Proxies Disabled, Timeouts Active) ...")

    pass1_args = build_wget_args(
        settings,
        output_dir,
        extra_args=[
            "--mirror",
            "--no-parent",
            "--page-requisites",
            f"--domains={target_domain}",
        ],
    )

    result = subprocess.run(
        [str(wget_path), *pass1_args, url],
        capture_output=False,
    )

    if result.returncode not in (0, 8):
        print(f"Warning: wget pass 1 exited with code {result.returncode}")

    # ── VALIDATION: Check HTML integrity ────────────────────────────────────────
    validation_results = validate_html_files(output_dir)
    print_validation_results(validation_results)

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

    print(f"\nDownloading external media (parallel: {settings['ParallelDownloads']})...")

    pass2_args = build_wget_args(
        settings,
        media_dir,
        no_link_conversion=True,
        extra_args=[
            "--level=1",
            "--no-directories",
        ],
    )

    # Process URLs in parallel batches
    batch_size = settings["ParallelDownloads"]
    url_list = list(ext_urls)
    total_urls = len(url_list)

    for i in range(0, total_urls, batch_size):
        batch = url_list[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_urls + batch_size - 1) // batch_size

        print(f"  Batch {batch_num}/{total_batches} [{i + 1}-{min(i + batch_size, total_urls)}] of {total_urls}")

        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = {
                executor.submit(
                    subprocess.run,
                    [str(wget_path), *pass2_args, url],
                    capture_output=True,
                ): url
                for url in batch
            }

            for future in as_completed(futures):
                url = futures[future]
                try:
                    result = future.result()
                    if result.returncode not in (0, 8):
                        failed_urls.append(url)
                except Exception:
                    failed_urls.append(url)

    # ── PASS 3: Rewrite external URLs to local paths ────────────────────
    repair_external_links(output_dir, media_dir, ext_urls)

    # ── PASS 4: Strip online-only resources for offline browsing ────────────────
    repair_offline_html(output_dir)

    return failed_urls
