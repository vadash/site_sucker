"""Wget binary resolver and argument builder."""

from pathlib import Path
from typing import Any


def get_wget_path() -> Path:
    """Resolve the path to wget.exe binary.

    Looks for wget.exe in the bin/ directory relative to the project root.

    Returns:
        Path to wget.exe.

    Raises:
        FileNotFoundError: If wget.exe is not found in bin/ directory.
    """
    # Assume we're in src/site_sucker/, go up to project root
    module_dir = Path(__file__).parent.parent.parent
    wget_path = module_dir / "bin" / "wget.exe"

    if not wget_path.exists():
        raise FileNotFoundError(
            f"wget.exe not found at: {wget_path}. "
            "Please ensure wget.exe is in the bin/ directory."
        )

    return wget_path


def build_wget_args(
    settings: dict[str, Any],
    output_dir: Path | str,
    extra_args: list[str] | None = None,
    no_link_conversion: bool = False,
) -> list[str]:
    """Build wget argument array from settings and CLI parameters.

    Args:
        settings: Configuration dictionary from settings.json.
        output_dir: Output directory path for downloaded files.
        extra_args: Additional arguments to pass to wget.
        no_link_conversion: If True, skip --convert-links and --adjust-extension.

    Returns:
        List of wget command-line arguments.
    """
    args = [
        "-e", "robots=off",
        "--no-proxy",
        "--no-verbose",
        "--restrict-file-names=windows",
        "--no-host-directories",
        f"--directory-prefix={output_dir}",
        f"--user-agent={settings['UserAgent']}",
        f"--timeout={settings['Timeout']}",
        f"--tries={settings['Retries']}",
        "--header=Accept-Encoding: identity",
    ]

    # Add wait if specified (helps avoid 429 rate limiting)
    if settings.get("WaitBetweenRequests", 0) > 0:
        args.append(f"--wait={settings['WaitBetweenRequests']}")
        args.append("--random-wait")

    # Only add link conversion for pass 1 (mirroring), not pass 2 (plain downloads)
    if not no_link_conversion:
        args.append("--convert-links")
        args.append("--adjust-extension")

    # Build reject-regex from patterns and domains
    reject_parts = []

    if settings.get("RejectPatterns"):
        reject_parts.extend(settings["RejectPatterns"])

    if settings.get("RejectDomains"):
        reject_domains = "|".join(settings["RejectDomains"])
        reject_parts.append(f"({reject_domains})")

    # Forum-specific: reject viewtopic.php?p= per-post duplicates
    # POSIX ERE doesn't support \d, use [0-9] instead
    reject_parts.append(r"viewtopic\.php.*&p=[0-9]+|viewtopic\.php\?p=[0-9]+")

    if reject_parts:
        combined = "|".join(reject_parts)
        args.append("--reject-regex")
        args.append(f".*({combined}).*")

    if extra_args:
        args.extend(extra_args)

    return args
