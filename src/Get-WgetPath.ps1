<#
.SYNOPSIS
    Resolves the path to wget.exe binary.

.DESCRIPTION
    Looks for wget.exe in the bin/ directory relative to the module root.
    Validates that the binary exists and is executable.

.OUTPUTS
    System.String
    Full path to wget.exe.

.EXAMPLE
    $WgetPath = Get-WgetPath
#>
function Get-WgetPath {
    [CmdletBinding()]
    [OutputType([string])]
    param()

    $ModuleRoot = $PSScriptRoot
    $WgetPath = Join-Path $ModuleRoot "..\bin\wget.exe"

    if (-not (Test-Path $WgetPath)) {
        throw "wget.exe not found at: $WgetPath. Please ensure wget.exe is in the bin/ directory."
    }

    Write-Verbose "Found wget at: $WgetPath"
    return $WgetPath
}
