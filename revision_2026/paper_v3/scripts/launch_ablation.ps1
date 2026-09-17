param(
  [Parameter(Mandatory=$true)][string]$Project,
  [Parameter(Mandatory=$true)][string]$Protocol,
  [Parameter(Mandatory=$true)][ValidateSet('ABL-DEV','ABL-CORE','ABL-DELAY')][string]$Batch,
  [int]$Workers = 6,
  [int]$MaxTrials = 0
)
$ErrorActionPreference = 'Stop'
$py = 'E:\anaconda\envs\pytorch_new\python.exe'
$entry = Join-Path $Project 'revision_2026\paper_v3\scripts\ablation.py'
$args = @('-B', $entry, 'run', '--project', $Project, '--protocol', $Protocol, '--batch', $Batch, '--workers', "$Workers")
if($MaxTrials -gt 0){ $args += @('--max-trials', "$MaxTrials") }
& $py @args
exit $LASTEXITCODE
