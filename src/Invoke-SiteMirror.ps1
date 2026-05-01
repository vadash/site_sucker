<#
.SYNOPSIS
    Executes the two-pass site mirroring process.

.DESCRIPTION
    Orchestrates:
    1. Pass 1: Full site mirror using wget --mirror
    2. Pass 2: Download external media with parallelism
    3. Pass 3: Rewrite external URLs in HTML to local paths
    4. Pass 4: Strip online-only resources for offline browsing

.PARAMETER Url
    The base URL to mirror.

.PARAMETER OutputDir
    Output directory path.

.PARAMETER TargetDomain
    Primary domain (used to filter external media).

.PARAMETER Settings
    Hashtable containing configuration.

.PARAMETER WgetPath
    Path to wget.exe binary.

.OUTPUTS
    System.Collections.Generic.List[string]
    List of failed URLs (if any).

.EXAMPLE
    $failed = Invoke-SiteMirror -Url "https://example.com" -OutputDir "./downloads" -TargetDomain "example.com" -Settings $Settings -WgetPath $WgetPath
#>
function Invoke-SiteMirror {
    [CmdletBinding()]
    [OutputType([System.Collections.Generic.List[string]])]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,

        [Parameter(Mandatory = $true)]
        [string]$OutputDir,

        [Parameter(Mandatory = $true)]
        [string]$TargetDomain,

        [Parameter(Mandatory = $true)]
        [hashtable]$Settings,

        [Parameter(Mandatory = $true)]
        [string]$WgetPath
    )

    # Track failures
    $failedUrls = [System.Collections.Generic.List[string]]::new()

    # ── PASS 1: Full site mirror ───────────────────────────────────────────────
    Write-Host "`n[1/4] Mirroring $Url (Proxies Disabled, Timeouts Active) ..." -ForegroundColor Cyan

    # --page-requisites downloads CSS/JS/images needed to render pages.
    # --domains restricts all downloads (including requisites) to the target domain only,
    # preventing external CDN files from bleeding into the project root.
    $pass1Args = New-WgetArgs -Settings $Settings -OutputDir $OutputDir -ExtraArgs @(
        "--mirror",
        "--no-parent",
        "--page-requisites",
        "--domains=$TargetDomain"
    )

    & $WgetPath @pass1Args $Url

    if ($LASTEXITCODE -notin 0, 8) {
        Write-Warning "wget pass 1 exited with code $LASTEXITCODE"
    }

    # ── PASS 2: External media with parallelism ────────────────────────────────
    $extUrls = Get-ExternalMedia -OutputDir $OutputDir -TargetDomain $TargetDomain -Settings $Settings

    if ($extUrls.Count -eq 0) {
        Write-Host "No external media URLs found. Skipping pass 2 & 3." -ForegroundColor Yellow
        # Still run pass 4 to clean offline HTML
        Repair-OfflineHtml -OutputDir $OutputDir
        return $failedUrls
    }

    # Create media subdirectory to avoid dumping images in root
    $MediaDir = Join-Path $OutputDir "images"
    $null = New-Item -Path $MediaDir -ItemType Directory -Force -ErrorAction SilentlyContinue

    Write-Host "`nDownloading external media (parallel: $($Settings.ParallelDownloads))..." -ForegroundColor Cyan

    # Build common args for pass 2 - no link conversion to prevent bleed,
    # no directories to flatten external media into media dir
    $pass2Args = New-WgetArgs -Settings $Settings -OutputDir $MediaDir -NoLinkConversion -ExtraArgs @(
        "--level=1",
        "--no-directories"
    )

    # Process URLs in parallel batches
    $batchSize = $Settings.ParallelDownloads
    $urlArray = @($extUrls)
    $totalUrls = $urlArray.Count
    $batches = [Math]::Ceiling($totalUrls / $batchSize)

    for ($b = 0; $b -lt $batches; $b++) {
        $startIdx = $b * $batchSize
        $endIdx = [Math]::Min(($b + 1) * $batchSize, $totalUrls) - 1
        $batch = $urlArray[$startIdx..$endIdx]

        Write-Host "  Batch $($b + 1)/$batches [$($startIdx + 1)-$endIdx] of $totalUrls" -ForegroundColor DarkGray

        # Run downloads in parallel using runspaces
        $runspaces = @()
        $results = [System.Collections.ArrayList]::new()

        foreach ($url in $batch) {
            $powershell = [powershell]::Create()
            $powershell.AddScript({
                param($WgetExecutable, $WgetParams, $TargetUrl)

                $env:http_proxy = $null
                $env:https_proxy = $null
                $env:all_proxy = $null

                # Don't capture output - it can interfere with exit code
                & $WgetExecutable @WgetParams $TargetUrl 2>$null
                return @{
                    Url      = $TargetUrl
                    ExitCode = $LASTEXITCODE
                }
            }).AddArgument($WgetPath).AddArgument($pass2Args).AddArgument($url) | Out-Null

            $runspaces += @{
                PowerShell = $powershell
                AsyncResult = $powershell.BeginInvoke()
            }
        }

        # Wait for all to complete
        foreach ($rs in $runspaces) {
            $result = $rs.PowerShell.EndInvoke($rs.AsyncResult)
            $results.Add($result) | Out-Null
            $rs.PowerShell.Dispose()
        }

        # Check for failures
        foreach ($result in $results) {
            if ($result.ExitCode -notin 0, 8) {
                $failedUrls.Add($result.Url)
            }
        }
    }

    # ── PASS 3: Rewrite external URLs to local paths ────────────────────
    Repair-ExternalLinks -OutputDir $OutputDir -MediaDir $MediaDir -ExternalUrls $extUrls

    # ── PASS 4: Strip online-only resources for offline browsing ────────────────
    Repair-OfflineHtml -OutputDir $OutputDir

    return $failedUrls
}
