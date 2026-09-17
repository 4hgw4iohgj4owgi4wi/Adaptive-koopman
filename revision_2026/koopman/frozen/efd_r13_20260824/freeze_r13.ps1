param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
$codeRoot = Join-Path $ProjectRoot 'revision_2026\koopman\innovation\efd_r13'
$resultRoot = Join-Path $ProjectRoot 'revision_2026\koopman\innovation_efd_r13_results'
$freezeRoot = Join-Path $ProjectRoot 'revision_2026\koopman\frozen\efd_r13_20260824'

foreach ($path in @($codeRoot, $resultRoot)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Freeze source does not exist: $path"
    }
}

New-Item -ItemType Directory -Path $freezeRoot -Force | Out-Null

function Get-TreeRows {
    param([string]$Scope, [string]$Root)
    Get-ChildItem -LiteralPath $Root -Recurse -File | Sort-Object FullName | ForEach-Object {
        $relative = $_.FullName.Substring($Root.Length).TrimStart('\')
        [pscustomobject]@{
            Scope = $Scope
            RelativePath = $relative
            Length = $_.Length
            LastWriteTimeUtc = $_.LastWriteTimeUtc.ToString('o')
            SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
    }
}

function Get-TreeDigest {
    param([object[]]$Rows)
    $canonical = ($Rows | Sort-Object Scope, RelativePath | ForEach-Object {
        '{0}|{1}|{2}|{3}' -f $_.Scope, $_.RelativePath, $_.Length, $_.SHA256
    }) -join "`n"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($canonical)
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
}

$codeRows = @(Get-TreeRows -Scope 'code' -Root $codeRoot)
$resultRows = @(Get-TreeRows -Scope 'results' -Root $resultRoot)
$allRows = @($codeRows + $resultRows)
$csvPath = Join-Path $freezeRoot 'file_manifest.csv'
$allRows | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8

$manifest = [ordered]@{
    schema = 'efd-r13-freeze-v1'
    status = 'FROZEN_NEGATIVE_BASELINE'
    frozen_at = (Get-Date).ToString('o')
    host = $env:COMPUTERNAME
    project_root = $ProjectRoot
    code_root = $codeRoot
    result_root = $resultRoot
    code_file_count = $codeRows.Count
    code_bytes = [int64](($codeRows | Measure-Object Length -Sum).Sum)
    code_tree_sha256 = Get-TreeDigest -Rows $codeRows
    result_file_count = $resultRows.Count
    result_bytes = [int64](($resultRows | Measure-Object Length -Sum).Sum)
    result_tree_sha256 = Get-TreeDigest -Rows $resultRows
    manifest_csv_sha256 = (Get-FileHash -LiteralPath $csvPath -Algorithm SHA256).Hash
    executed_through = 'U7'
    blocked_stages = @('U8', 'U9', 'U10')
    development_read = $false
    confirm_generated = $false
    active_training_at_freeze = $false
    scientific_decision = [ordered]@{
        strongest_core = 'V-FL92-U8'
        strongest_core_family_macro_J = 0.10198935809638017
        bilinear_advantage = $false
        continuous_irsp_certificate = $false
        physical_lift_advantage = $false
        V_M_validation_passed = $false
    }
    future_innovation = [ordered]@{
        name = 'EPD-Koopman'
        status = 'NOT_STARTED'
        code_created = $false
        data_generated = $false
        training_started = $false
        explicit_user_authorization_required = $true
    }
}

$manifestPath = Join-Path $freezeRoot 'freeze_manifest.json'
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
$manifest
