<#
.SYNOPSIS
    Writes a final download report.

.DESCRIPTION
    Generates a summary report of the download operation, including
    statistics on files downloaded, failures, and total size.

.PARAMETER OutputDir
    Path to the directory containing downloaded files.

.PARAMETER StartTime
    DateTime when the download started.

.PARAMETER FailedUrls
    List of URLs that failed to download (if any).

.EXAMPLE
    Write-SiteReport -OutputDir "./downloads" -StartTime $startTime -FailedUrls @()
#>
function Write-SiteReport {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutputDir,

        [Parameter(Mandatory = $true)]
        [DateTime]$StartTime,

        [Parameter(Mandatory = $false)]
        [string[]]$FailedUrls = @()
    )

    $endTime = Get-Date
    $duration = $endTime - $StartTime

    Write-Host "`n" -NoNewline
    Write-Host "=" * 60 -ForegroundColor DarkGray
    Write-Host "DOWNLOAD COMPLETE" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor DarkGray

    # Count downloaded files
    $files = Get-ChildItem -Path $OutputDir -Recurse -File -ErrorAction SilentlyContinue
    $totalFiles = $files.Count
    $totalSize = ($files | Measure-Object -Property Length -Sum).Sum

    # Format size
    if ($totalSize -gt 1GB) {
        $sizeStr = "{0:N2} GB" -f ($totalSize / 1GB)
    }
    elseif ($totalSize -gt 1MB) {
        $sizeStr = "{0:N2} MB" -f ($totalSize / 1MB)
    }
    elseif ($totalSize -gt 1KB) {
        $sizeStr = "{0:N2} KB" -f ($totalSize / 1KB)
    }
    else {
        $sizeStr = "{0} bytes" -f $totalSize
    }

    Write-Host "`nStatistics:" -ForegroundColor Cyan
    Write-Host "  Total files:     $totalFiles" -ForegroundColor White
    Write-Host "  Total size:      $sizeStr" -ForegroundColor White
    Write-Host "  Duration:        $($duration.ToString('hh\:mm\:ss'))" -ForegroundColor White

    if ($FailedUrls.Count -gt 0) {
        Write-Host "`nFailed downloads: $($FailedUrls.Count)" -ForegroundColor Red
        $failLogPath = Join-Path $OutputDir "failures.log"

        $FailedUrls | Out-File -FilePath $failLogPath -Encoding utf8
        Write-Host "  Failed URLs logged to: $failLogPath" -ForegroundColor Yellow
    }
    else {
        Write-Host "`nFailed downloads: 0" -ForegroundColor Green
    }

    Write-Host "`nOutput directory: $OutputDir" -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor DarkGray
}
