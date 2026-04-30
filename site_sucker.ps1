#Requires -Version 7.0
<#
.SYNOPSIS
    SiteSucker - Universal Wiki/Site Downloader

.DESCRIPTION
    Mirrors websites and wikis locally using wget. Features:
    - Interactive prompts when no URL provided
    - Parallel external media downloads
    - Intelligent deduplication and URL normalization
    - Configurable via settings.json

.PARAMETER Url
    The base URL to mirror.

.PARAMETER OutputDir
    Output directory path (default: ./downloads/<domain>).

.PARAMETER SettingsPath
    Path to custom settings.json (default: ./settings.json).

.PARAMETER Depth
    Maximum recursion depth (default: 0 = unlimited).

.PARAMETER Parallel
    Number of parallel downloads for external media (default: 4).

.EXAMPLE
    .\site_sucker.ps1
    # Interactive mode

.EXAMPLE
    .\site_sucker.ps1 -Url "https://wiki.projectdiablo2.com/wiki/Main_Page"
    # Direct mode with defaults

.EXAMPLE
    .\site_sucker.ps1 -Url "https://example.com" -Parallel 8 -Depth 2
    # Custom parallelism and depth
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Url,

    [Parameter(Mandatory = $false)]
    [string]$OutputDir,

    [Parameter(Mandatory = $false)]
    [string]$SettingsPath = (Join-Path $PSScriptRoot "settings.json"),

    [Parameter(Mandatory = $false)]
    [int]$Depth = 0,

    [Parameter(Mandatory = $false)]
    [int]$Parallel = 4
)

begin {
    # Import the module
    $ModulePath = Join-Path $PSScriptRoot "src\SiteSucker.psm1"
    Import-Module $ModulePath -Force

    # Load settings
    if (Test-Path $SettingsPath) {
        $Settings = Get-Content $SettingsPath -Raw | ConvertFrom-Json -AsHashtable
    }
    else {
        Write-Warning "Settings file not found at $SettingsPath. Using defaults."
        $Settings = @{
            UserAgent          = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            Timeout            = 15
            Retries            = 3
            MaxDepth           = 0
            OutputRoot         = "./downloads"
            WaitBetweenRequests = 0
            ParallelDownloads  = 4
            RejectPatterns     = @()
            RejectDomains      = @()
            MediaExtensions    = @(".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".webm")
        }
    }

    # Get wget path
    try {
        $WgetPath = Get-WgetPath
    }
    catch {
        Write-Error $_.Exception.Message
        return
    }

    # Parse URL and determine target domain
    if ([string]::IsNullOrWhiteSpace($Url)) {
        # Interactive mode
        Write-Host "`nSiteSucker - Universal Site Downloader" -ForegroundColor Green
        Write-Host "=" * 50 -ForegroundColor DarkGray

        $Url = Read-Host "Site URL to mirror"

        if ([string]::IsNullOrWhiteSpace($Url)) {
            Write-Error "URL is required."
            return
        }

        if (-not ($Url -match '^https?://')) {
            $Url = "https://$Url"
        }
    }

    # Extract domain from URL
    try {
        $uri = [uri]$Url
        $TargetDomain = $uri.Host
    }
    catch {
        Write-Error "Invalid URL: $Url"
        return
    }

    # Determine output directory
    if ([string]::IsNullOrWhiteSpace($OutputDir)) {
        $defaultOutput = Join-Path $Settings.OutputRoot $TargetDomain

        if ([string]::IsNullOrWhiteSpace($Url)) {
            $OutputDir = Read-Host "Output folder [$defaultOutput]"
            if ([string]::IsNullOrWhiteSpace($OutputDir)) {
                $OutputDir = $defaultOutput
            }
        }
        else {
            $OutputDir = $defaultOutput
        }
    }

    # Create output directory
    $null = New-Item -Path $OutputDir -ItemType Directory -Force

    # Override settings with CLI params
    if ($Parallel -gt 0) {
        $Settings.ParallelDownloads = $Parallel
    }
    if ($Depth -gt 0) {
        $Settings.MaxDepth = $Depth
    }

    # Disable proxies
    $env:http_proxy = $null
    $env:https_proxy = $null
    $env:all_proxy = $null
    $env:HTTP_PROXY = $null
    $env:HTTPS_PROXY = $null

    $ErrorActionPreference = "Continue"
}

process {
    $startTime = Get-Date

    try {
        # Execute the mirror
        $failedUrls = Invoke-SiteMirror -Url $Url -OutputDir $OutputDir -TargetDomain $TargetDomain -Settings $Settings -WgetPath $WgetPath

        # Write report
        Write-SiteReport -OutputDir $OutputDir -StartTime $startTime -FailedUrls $failedUrls
    }
    catch {
        Write-Error "Error during download: $_"
    }
}

end {
    # Cleanup
}
