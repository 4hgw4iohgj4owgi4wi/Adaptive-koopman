param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
$freezeRoot = Join-Path $ProjectRoot 'revision_2026\koopman\frozen\efd_r13_20260824'
$manifestPath = Join-Path $freezeRoot 'freeze_manifest.json'
$csvPath = Join-Path $freezeRoot 'file_manifest.csv'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$rows = @(Import-Csv -LiteralPath $csvPath)
$failures = [System.Collections.Generic.List[object]]::new()

foreach ($row in $rows) {
    $base = if ($row.Scope -eq 'code') { $manifest.code_root } else { $manifest.result_root }
    $path = Join-Path $base $row.RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $failures.Add([pscustomobject]@{ Scope = $row.Scope; RelativePath = $row.RelativePath; Reason = 'missing' })
        continue
    }
    $file = Get-Item -LiteralPath $path
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ([int64]$row.Length -ne $file.Length -or $row.SHA256 -ne $hash) {
        $failures.Add([pscustomobject]@{ Scope = $row.Scope; RelativePath = $row.RelativePath; Reason = 'length_or_hash_changed' })
    }
}

$known = @{}
foreach ($row in $rows) { $known["$($row.Scope)|$($row.RelativePath)"] = $true }
foreach ($scope in @('code', 'results')) {
    $base = if ($scope -eq 'code') { $manifest.code_root } else { $manifest.result_root }
    Get-ChildItem -LiteralPath $base -Recurse -File | ForEach-Object {
        $relative = $_.FullName.Substring($base.Length).TrimStart('\')
        if (-not $known.ContainsKey("$scope|$relative")) {
            $failures.Add([pscustomobject]@{ Scope = $scope; RelativePath = $relative; Reason = 'unmanifested_new_file' })
        }
    }
}

[pscustomobject]@{
    verified_at = (Get-Date).ToString('o')
    passed = ($failures.Count -eq 0)
    checked_files = $rows.Count
    failures = @($failures)
}
