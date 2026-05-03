# SiteSucker - Universal Wiki/Site Downloader

A Python-based site mirroring tool for creating offline copies of wikis and websites. Converts the original PowerShell implementation to Python with uv for dependency management.

## Features

- **Full Site Mirroring**: Downloads entire sites using wget
- **Parallel Downloads**: Configurable parallelism for external media
- **Intelligent Deduplication**: URL normalization removes duplicates
- **Offline Optimization**: Strips online-only resources (tracking, feeds)
- **Forum Support**: Special handling for phpBB and MediaWiki
- **Configurable**: JSON-based settings with CLI overrides

## Requirements

- **OS**: Windows 11
- **Python**: 3.11+
- **uv**: For package management (optional, for development)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd site_sucker

# Sync dependencies and install project in editable mode
uv sync
```

## Usage

After running `uv sync`, use `uv run` to execute commands:

### Method 1: Python Module (Recommended)

```bash
# Show help
uv run python -m site_sucker --help

# Interactive mode
uv run python -m site_sucker

# Direct mode with URL
uv run python -m site_sucker https://wiki.example.com/wiki/Main_Page

# With options
uv run python -m site_sucker https://example.com --parallel 8 --depth 2
```

### Method 2: Installed Script

```bash
# Show help
uv run site-sucker --help

# Interactive mode
uv run site-sucker

# Direct mode with URL
uv run site-sucker https://wiki.example.com/wiki/Main_Page

# With options
uv run site-sucker https://example.com -o ./my_mirrors/example --parallel 8
```

### Interactive Mode

When you run without arguments, you'll be prompted for:
- Site URL to mirror
- Output folder (default: `./downloads/<domain>`)
- Max depth (default: 0 = unlimited)
- Parallel downloads (default: 4)

### Direct Mode Examples

```bash
# Basic usage
uv run python -m site_sucker https://wiki.example.com/wiki/Main_Page

# Custom output directory
uv run python -m site_sucker https://example.com -o ./my_mirrors/example

# Custom parallelism and depth
uv run python -m site_sucker https://example.com --parallel 8 --depth 2

# Custom settings file
uv run python -m site_sucker https://example.com --settings ./my_settings.json

# Block specific URL patterns (e.g., phpBB forum categories)
uv run python -m site_sucker https://forum.example.com --reject "f=31&;f=8&;f=11&"

# Use range expressions to block multiple patterns at once
# Reject forum IDs 1-100 except 4, 25, 40
uv run python -m site_sucker https://forum.example.com --reject "f={1..100%4,25,40}&"

# Use multiple --reject flags (they are combined)
uv run python -m site_sucker https://forum.example.com --reject "action=" --reject "f={1..10}&"

# Resume an interrupted download (bypasses 429 bot protection)
uv run python -m site_sucker https://example.com --resume --output-dir ./downloads/example
```

## Configuration

The `settings.jsonc` file controls download behavior (supports `//` and `/* */` comments):

```jsonc
{
  // HTTP client settings
  "UserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
  "Timeout": 15,
  "Retries": 3,

  // Crawl behavior
  "MaxDepth": 0,
  "OutputRoot": "./downloads",
  "WaitBetweenRequests": 0.5,
  "ParallelDownloads": 2,

  // URL rejection patterns (matched as substrings)
  "RejectPatterns": [
    "action=", "oldid=", "diff=", "printable=",
    "returnto=", "redirect=", "Special:", "Talk:",
    "User:", "User_talk:", "Category_talk:",
    "load.php", "api.php"
  ],

  // Domains to block entirely
  "RejectDomains": [
    "analytics.wikitide.net",
    "matomo."
  ],

  // File extensions for media download pass
  "MediaExtensions": [
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".mp4", ".webm", ".avi", ".mkv", ".mov",
    ".svg", ".ico", ".bmp", ".css", ".js", ".woff2"
  ]
}
```

**Note**: The tool falls back to `settings.json` if `settings.jsonc` is not found.

### Settings Explained

| Setting | Description |
|---------|-------------|
| `UserAgent` | User-Agent string for HTTP requests |
| `Timeout` | Connection timeout in seconds |
| `Retries` | Number of retry attempts for failed downloads |
| `MaxDepth` | Maximum recursion depth (0 = unlimited) |
| `OutputRoot` | Default root directory for downloads |
| `WaitBetweenRequests` | Delay between requests (helps avoid rate limiting) |
| `ParallelDownloads` | Number of parallel downloads for external media |
| `RejectPatterns` | URL patterns to skip (for deduplication) |
| `RejectDomains` | Domains to exclude (e.g., analytics) |
| `MediaExtensions` | File extensions considered as media |

## Download Pipeline

SiteSucker uses a 4-pass process:

### Normal Mode (default)

```
Pass 1: Full site mirror (wget --mirror)
  - Downloads all pages within target domain
  - Validates HTML integrity after download
  - Applies reject patterns to skip low-value URLs
  - Converts links to local paths

Pass 2: External media collection and download
  - Scans HTML/CSS for external media URLs
  - Deduplicates URLs (strips query strings)
  - Downloads in parallel batches using wget

Pass 3: External URL rewriting
  - Rewrites external CDN URLs to local paths (HTML via BeautifulSoup)
  - Converts absolute CSS paths to relative (regex pipeline with validation)
  - Strips CORS-blocking attributes (integrity, crossorigin)
  - Inlines CSS @import statements to avoid CORS on file://

Pass 4: Offline optimization
  - Removes online-only resources (load.php, feeds, preconnect hints)
  - Strips tracking/analytics scripts and pixels
  - Removes phpBB offline-useless navigation links
  - Injects fallback CSS for readability
```

### Resume Mode (--resume flag)

When resuming an interrupted download, use the `--resume` flag:

```bash
uv run python -m site_sucker https://example.com --resume --output-dir ./downloads/example
```

**Why use resume mode?**

When downloading large sites, you may encounter 429 (Too Many Requests) bot protection. Wget's normal resume behavior (`-nc`) has a Catch-22:
- With `-nc`: wget skips existing files but can't discover links inside them → crawl stops
- Without `-nc`: wget re-checks every file against the server → triggers 429 delays

**How resume mode solves this:**

Resume mode replaces wget's built-in spidering with a Python-based BFS crawler:

```
Pass 1: Python BFS crawler
  - Scans existing local HTML/CSS files for links (no server hits)
  - Downloads only genuinely missing pages via native HTTP (requests.Session)
  - Respects WaitBetweenRequests to avoid 429s
  - Tracks visited URLs to prevent infinite loops
  - Enforces MaxDepth settings
  - Discovers both HTML links and CSS @import chains

Pass 2: External media download (same as normal mode)
Pass 3: Internal link rewriting (BeautifulSoup converts https:// → relative paths)
Pass 4: Offline optimization (same as normal mode)
```

**Benefits:**
- Only hits the server for pages you don't have yet
- Existing files are parsed locally at full speed
- Bypasses 429 bot protection completely
- Can resume even after weeks of interruption

## Project Structure

```
site_sucker/
├── bin/
│   └── wget.exe              # Wget binary (Windows)
├── src/
│   └── site_sucker/
│       ├── __init__.py
│       ├── __main__.py       # CLI entry point
│       ├── settings.py       # Configuration loading
│       ├── wget.py           # Wget wrapper
│       ├── mirror.py         # Pipeline orchestrator
│       ├── crawler.py        # Crawler abstraction (WgetCrawler, BFSCrawler)
│       ├── media.py          # External media scanner
│       ├── repair_links.py   # URL rewriter
│       ├── repair_offline.py # Offline optimizer
│       ├── replacement_pipeline.py  # CSS replacement engine with validation
│       ├── resume.py         # Python BFS crawler (resume mode)
│       ├── url_filter.py     # Shared URL validation/extraction
│       ├── paths.py          # URL-to-filepath conversion
│       ├── file_iter.py      # File iteration utilities
│       ├── validate_html.py  # HTML integrity checker
│       └── report.py         # Report generator
├── tests/
│   ├── conftest.py           # Test fixtures
│   ├── test_settings.py
│   ├── test_wget.py
│   ├── test_mirror.py
│   ├── test_media.py
│   ├── test_repair_links.py
│   ├── test_repair_offline.py
│   ├── test_replacement_pipeline.py
│   ├── test_resume.py
│   ├── test_url_filter.py
│   ├── test_validate_html.py
│   └── test_report.py
├── settings.jsonc            # Default configuration (JSON with comments)
├── pyproject.toml            # uv project config
├── AGENTS.md                 # AI agent development guide
└── README.md
```

## Development

### Running Tests

```bash
# IMPORTANT: Use the direct venv Python executable
# (uv run pytest doesn't work because pytest is in the venv)

# Run all tests
.\.venv\Scripts\python.exe -m pytest

# With coverage
.\.venv\Scripts\python.exe -m pytest --cov=site_sucker

# Run specific test module
.\.venv\Scripts\python.exe -m pytest tests/test_media.py

# Or use the test script
.\run_tests.ps1
```

## Examples

### forum.median-xl.com

**Old way (typing 97 patterns manually):**
```bash
uv run site-sucker -d 3 --reject "f=1&;f=2&;f=3&;f=5&;f=6&;f=7&;f=8&;f=9&;f=10&;..." https://forum.median-xl.com
```

**New way (using range expression):**
```bash
uv run site-sucker -d 3 --reject "f={1..100%4,25,40}&" https://forum.median-xl.com
```

This rejects forum IDs 1-100, excluding IDs 4, 25, and 40.

### Range Expression Syntax

The `--reject` flag supports powerful range expressions:

| Syntax | Meaning | Example |
|--------|---------|---------|
| `{START..END}` | Numeric range (inclusive) | `{1..10}` → 1, 2, ..., 10 |
| `{START..END..STEP}` | Range with step | `{1..10..2}` → 1, 3, 5, 7, 9 |
| `{START..END%EXCLUDE}` | Range excluding values | `{1..10%3,7}` → 1, 2, 4, 5, 6, 8, 9, 10 |

**More examples:**
```bash
# Reject even forum IDs 2-20
--reject "f={2..20..2}&"

# Reject IDs 1-50 except multiples of 5
--reject "f={1..50%5,10,15,20,25,30,35,40,45,50}&"

# Mix literal patterns and expressions in one flag
--reject "action=;f={1..10%5}&;Special:"

# Or use multiple --reject flags (they are combined)
--reject "action=" --reject "f={1..10}&" --reject "Special:"
```
