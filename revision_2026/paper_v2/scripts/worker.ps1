param([Parameter(Mandatory=$true)][string]$Project,[Parameter(Mandatory=$true)][string]$Run,[Parameter(Mandatory=$true)][string]$OldRun,[Parameter(Mandatory=$true)][string]$Taskbook,[int]$SelfTestExitCode=-1)
$ErrorActionPreference='Stop'
$python='E:\anaconda\envs\pytorch_new\python.exe'
$runner=Join-Path $Project 'revision_2026\koopman_predict_v3x\scripts\resume_outer.py'
$started=(Get-Date).ToString('o')
try {
  if($SelfTestExitCode -ge 0){& $python -c "raise SystemExit($SelfTestExitCode)"}
  else{& $python -B $runner --project $Project --run $Run --old-run $OldRun --taskbook $Taskbook}
  $code=[int]$LASTEXITCODE
} catch {
  $code=24
  $_ | Out-String | Set-Content -LiteralPath (Join-Path $Run 'worker_error.txt') -Encoding UTF8
}
$record=[ordered]@{exit_code=$code;started_at=$started;ended_at=(Get-Date).ToString('o');pid=$PID}
$record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Run 'process_exit.json') -Encoding UTF8
exit $code
