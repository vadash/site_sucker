<#
.SYNOPSIS
    Rewrites external CDN URLs in downloaded HTML to point to local copies.

.DESCRIPTION
    Scans HTML files to replace absolute CDN URLs with relative paths to the local files.
    Strips crossorigin/integrity attributes to prevent local file:// CORS errors.
    Also scans CSS files to convert absolute paths (url('/...')) to relative paths.
#>
function Repair-ExternalLinks {
    [CmdletBinding()]
    [OutputType([int])]
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutputDir,

        [Parameter(Mandatory = $true)]
        [string]$MediaDir,

        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.HashSet[string]]$ExternalUrls
    )

    if ($ExternalUrls.Count -eq 0) {
        Write-Host "No external URLs to rewrite." -ForegroundColor Yellow
        return 0
    }

    Write-Host "`n[3/4] Rewriting external URLs to local paths..." -ForegroundColor Cyan

    # Build URL -> local filename mapping
    $urlMap = @{}
    foreach ($url in $ExternalUrls) {
        try {
            $uri = [System.Uri]::new($url)
            $filename = [System.IO.Path]::GetFileName($uri.AbsolutePath)
            if ($filename) {
                $localPath = Join-Path $MediaDir $filename
                if (Test-Path $localPath -PathType Leaf) {
                    $urlMap[$url] = $filename
                }
            }
        }
        catch {
            Write-Verbose "Skipping invalid URL: $url"
        }
    }

    if ($urlMap.Count -eq 0) {
        Write-Host "No downloaded external files found on disk. Nothing to rewrite." -ForegroundColor Yellow
        return 0
    }

    Write-Host "  Mapping $($urlMap.Count) external URLs to local files" -ForegroundColor DarkGray

    # ── PART 1: Process HTML Files ──────────────────────────────────────────
    $htmlFiles = Get-ChildItem -Path $OutputDir -Recurse -Include "*.html", "*.htm" -ErrorAction SilentlyContinue
    $modifiedCount = 0

    foreach ($f in $htmlFiles) {
        $raw = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $raw) { continue }

        $modified = $false
        $htmlDir = [System.IO.Path]::GetDirectoryName($f.FullName)

        foreach ($url in $urlMap.Keys) {
            $filename = $urlMap[$url]
            $localPath = Join-Path $MediaDir $filename

            $relPath = [System.IO.Path]::GetRelativePath($htmlDir, $localPath) -replace '\\', '/'

            $escapedUrl = [regex]::Escape($url)
            # Match exact URL (with optional querystring) strongly bounded by quotes
            # This prevents accidental partial replacements inside inline Javascript
            $pattern = '(["''])' + $escapedUrl + '(?:\?[^\s"''#>]+)?\1'

            if ($raw -match $pattern) {
                $raw = [regex]::Replace($raw, $pattern, "`${1}$relPath`${1}")
                $modified = $true
            }
        }

        if ($modified) {
            # Aggressively strip integrity and crossorigin to prevent browser CORS blocking on file://
            $raw = $raw -replace '(?i)\s+integrity=(["'']).*?\1', ''
            $raw = $raw -replace '(?i)\s+crossorigin=(["'']).*?\1', ''
            $raw = $raw -replace '(?i)\s+crossorigin\b', ''

            Set-Content -Path $f.FullName -Value $raw -NoNewline
            $modifiedCount++
        }
    }

    Write-Host "  Rewrote external links in $modifiedCount HTML file(s)" -ForegroundColor Yellow

    # ── PART 2: Process CSS Files (Fix Absolute Paths) ──────────────────────
    $cssFiles = Get-ChildItem -Path $OutputDir -Recurse -Include "*.css" -ErrorAction SilentlyContinue
    $cssModifiedCount = 0

    foreach ($c in $cssFiles) {
        $rawCss = Get-Content $c.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $rawCss) { continue }

        $modifiedCss = $false
        $cssDir = [System.IO.Path]::GetDirectoryName($c.FullName)

        # 1. Replace mapped external CDN urls inside CSS (e.g. Google Fonts)
        foreach ($url in $urlMap.Keys) {
            $filename = $urlMap[$url]
            $localPath = Join-Path $MediaDir $filename
            $relPath = [System.IO.Path]::GetRelativePath($cssDir, $localPath) -replace '\\', '/'

            $escapedUrl = [regex]::Escape($url)
            $pattern = 'url\(\s*(["'']?)' + $escapedUrl + '(?:\?[^\s"''#>\)]+)?\1\s*\)'

            if ($rawCss -match $pattern) {
                $rawCss = [regex]::Replace($rawCss, $pattern, "url(`${1}$relPath`${1})")
                $modifiedCss = $true
            }
        }

        # 2. Convert absolute local paths to relative paths so they don't break on file://
        # e.g., convert url('/styles/img/bg.png') to url('../../styles/img/bg.png')
        $relFromRoot = [System.IO.Path]::GetRelativePath($OutputDir, $cssDir)
        if ($relFromRoot -eq ".") {
            $prefix = ""
        } else {
            $depth = ($relFromRoot -split '[\\/]').Count
            $prefix = "../" * $depth
        }

        # Regex match url('/path...') avoiding protocol-relative //paths
        $absUrlPattern = 'url\(\s*(["'']?)/([^/"''][^\)"'']*)\1\s*\)'
        if ($rawCss -match $absUrlPattern) {
            $rawCss = [regex]::Replace($rawCss, $absUrlPattern, "url(`${1}$prefix`${2}`${1})")
            $modifiedCss = $true
        }

        if ($modifiedCss) {
            Set-Content -Path $c.FullName -Value $rawCss -NoNewline
            $cssModifiedCount++
        }
    }

    if ($cssModifiedCount -gt 0) {
        Write-Host "  Rewrote paths in $cssModifiedCount CSS file(s)" -ForegroundColor Yellow
    }

    return $modifiedCount
}
