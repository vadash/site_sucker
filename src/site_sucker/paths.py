"""URL-to-filepath conversion utilities.

Shared by resume crawler and link repair modules.
"""

from pathlib import Path
from urllib.parse import urlparse

# Known file extensions that should not have .html appended
KNOWN_EXTENSIONS = {
    ".css",
    ".js",
    ".html",
    ".htm",
    ".json",
    ".xml",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".bmp",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
    ".mp4",
    ".webm",
    ".avi",
    ".mkv",
    ".mov",
    ".mp3",
    ".pdf",
}


def url_to_filepath(url: str, output_dir: Path) -> Path:
    """Convert a URL to its expected local file path.

    Mimics wget's --restrict-file-names=windows behavior:
    - Converts ? to @
    - Converts / in query strings to %2F
    - Strips fragments
    - Handles root and trailing-slash URLs as index.html

    Args:
        url: The URL to convert.
        output_dir: Root output directory.

    Returns:
        Expected local file path.
    """
    parsed = urlparse(url)

    path = parsed.path

    # Handle root URLs and trailing slashes
    if not path or path.endswith("/"):
        path = path + "index.html"

    # Append query parameters (if any) - ? becomes @
    if parsed.query:
        escaped_query = parsed.query.replace("/", "%2F")
        path = f"{path}@{escaped_query}"

    # Build full path
    if path.startswith("/"):
        path = path[1:]

    full_path = output_dir / path
    return full_path


def get_actual_save_path(expected_path: Path) -> Path:
    """Determine the final save path (appending .html if necessary).

    Since Python now controls file saving, we dictate the extension.
    If the URL doesn't end in a known extension, we append .html.

    Args:
        expected_path: Expected path from url_to_filepath().

    Returns:
        Final save path with .html appended if needed.
    """
    if expected_path.suffix.lower() in KNOWN_EXTENSIONS:
        return expected_path
    return expected_path.with_name(expected_path.name + ".html")


def relative_depth(file_path: Path, root_dir: Path) -> int:
    """Calculate the directory depth of a file relative to a root directory.

    Useful for building ``"../" * depth`` relative paths from a nested file
    back to the root output directory.

    Args:
        file_path: Path to the file (can be absolute or relative).
        root_dir: Root directory to calculate depth from.

    Returns:
        Number of directory levels between the file's parent and root_dir.
        Returns 0 if the file is directly inside root_dir.
    """
    try:
        rel_path = file_path.resolve().relative_to(root_dir.resolve())
        return len(rel_path.parts) - 1 if str(rel_path) != "." else 0
    except ValueError:
        return 0
