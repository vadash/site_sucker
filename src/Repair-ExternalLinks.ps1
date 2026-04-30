<#
.SYNOPSIS
    Rewrites external CDN URLs in downloaded HTML to point to local copies.

.DESCRIPTION
    After pass 2 downloads external media (CSS, JS, fonts, images) to the
    output directory root, this function scans all HTML files and replaces
    absolute CDN URLs with relative paths to the local files, enabling
    fully offline browsing.

.PARAMETER OutputDir
    Path to the directory containing downloaded files.

.PARAMETER ExternalUrls
    Set of unique external media URLs that were downloaded by pass 2.

.OUTPUTS
    System.Int32
    Number of HTML files that were modified.

.EXAMPLE
    $count = Repair-ExternalLinks -OutputDir "./downloads" -ExternalUrls $extUrls
#>
function Repair-ExternalLinks {
    [CmdletBinding()]
    [OutputType([int])]
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutputDir,

        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.HashSet[string]]$ExternalUrls
    )

    if ($ExternalUrls.Count -eq 0) {
        Write-Host "No external URLs to rewrite." -ForegroundColor Yellow
        return 0
    }

    Write-Host "`n[3/3] Rewriting external URLs to local paths..." -ForegroundColor Cyan

    # Build URL -> local filename mapping
    $urlMap = @{}
    foreach ($url in $ExternalUrls) {
        try {
            $uri = [System.Uri]::new($url)
            $filename = [System.IO.Path]::GetFileName($uri.AbsolutePath)
            if ($filename) {
                $localPath = Join-Path $OutputDir $filename
                # Only map if the file actually exists locally
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

    $htmlFiles = Get-ChildItem -Path $OutputDir -Recurse -Include "*.html", "*.htm" -ErrorAction SilentlyContinue
    $modifiedCount = 0

    foreach ($f in $htmlFiles) {
        $raw = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
        if (-not $raw) { continue }

        $modified = $false
        $htmlDir = [System.IO.Path]::GetDirectoryName($f.FullName)

        foreach ($url in $urlMap.Keys) {
            $filename = $urlMap[$url]
            $localPath = Join-Path $OutputDir $filename

            # Compute relative path from the HTML file's directory to the local file
            $relPath = [System.IO.Path]::GetRelativePath($htmlDir, $localPath)
            # Normalize to forward slashes for HTML
            $relPath = $relPath -replace '\\', '/'

            # Match the URL with optional query string suffix
            $urlPattern = [regex]::Escape($url) + '(?:\?[^\s"''#]*)?'
            if ($raw -match $urlPattern) {
                $raw = $raw -replace $urlPattern, $relPath
                $modified = $true
            }
        }

        if ($modified) {
            # Strip integrity attributes - the SRI hash may not match local file content
            # and will cause browsers to refuse loading the resource
            $raw = $raw -replace '\s+integrity="[^"]*"', ''
            # Strip crossorigin - not needed for local files, can cause issues with file://
            $raw = $raw -replace '\s+crossorigin="[^"]*"', ''

            Set-Content -Path $f.FullName -Value $raw -NoNewline
            $modifiedCount++
        }
    }

    Write-Host "  Rewrote external links in $modifiedCount HTML file(s)" -ForegroundColor Yellow
    return $modifiedCount
}
