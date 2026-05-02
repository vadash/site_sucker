"""Download report generator."""

from datetime import datetime
from pathlib import Path


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted size string (e.g., "1.23 MB").
    """
    if size_bytes >= 1_073_741_824:  # 1 GB
        return f"{size_bytes / 1_073_741_824:.2f} GB"
    elif size_bytes >= 1_048_576:  # 1 MB
        return f"{size_bytes / 1_048_576:.2f} MB"
    elif size_bytes >= 1_024:  # 1 KB
        return f"{size_bytes / 1_024:.2f} KB"
    else:
        return f"{size_bytes} bytes"


def write_site_report(
    output_dir: Path | str,
    start_time: datetime,
    failed_urls: list[str] | None = None,
) -> None:
    """Write a final download report.

    Generates a summary report of the download operation, including
    statistics on files downloaded, failures, and total size.

    Args:
        output_dir: Path to the directory containing downloaded files.
        start_time: DateTime when the download started.
        failed_urls: List of URLs that failed to download (if any).
    """
    output_dir = Path(output_dir)
    end_time = datetime.now()
    duration = end_time - start_time

    print("\n" + "=" * 60)
    print("DOWNLOAD COMPLETE")
    print("=" * 60)

    # Count downloaded files
    files = list(output_dir.rglob("*"))
    files = [f for f in files if f.is_file()]
    total_files = len(files)
    total_size = sum(f.stat().st_size for f in files)

    size_str = format_size(total_size)

    print("\nStatistics:")
    print(f"  Total files:     {total_files}")
    print(f"  Total size:      {size_str}")
    print(f"  Duration:        {duration}")

    if failed_urls:
        print(f"\nFailed downloads: {len(failed_urls)}")
        fail_log_path = output_dir / "failures.log"

        try:
            with open(fail_log_path, "w", encoding="utf-8") as f:
                for url in failed_urls:
                    f.write(f"{url}\n")
            print(f"  Failed URLs logged to: {fail_log_path}")
        except IOError as e:
            print(f"  Warning: Could not write failures.log: {e}")
    else:
        print("\nFailed downloads: 0")

    print(f"\nOutput directory: {output_dir}")
    print("=" * 60)
