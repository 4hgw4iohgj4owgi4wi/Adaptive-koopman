param([Parameter(Mandatory=$true)][string]$Protocol,[Parameter(Mandatory=$true)][ValidateSet('Q1')][string]$Batch,[string]$ResumeRun)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$project=Split-Path -Parent $root
$cfg=Get-Content -LiteralPath $Protocol -Raw -Encoding UTF8 | ConvertFrom-Json
$results=Join-Path $root 'paper_results'
$runs=Join-Path $results 'runs';$receipts=Join-Path $results 'receipts'
New-Item -ItemType Directory -Force -Path $runs,$receipts | Out-Null
if($ResumeRun){$run=(Resolve-Path -LiteralPath $ResumeRun).Path;if(-not $run.StartsWith((Resolve-Path $runs).Path)){throw 'Resume path escapes paper_results/runs'}}
else{$stamp=Get-Date -Format 'yyyyMMdd_HHmmss';$run=Join-Path $runs ($stamp+'_Q1_R01');New-Item -ItemType Directory -Path $run | Out-Null}
$task='Paper_Q1_'+(Split-Path -Leaf $run)
$worker=Join-Path $PSScriptRoot 'worker.ps1'
$taskbook=Join-Path (Split-Path -Parent $PSScriptRoot) 'protocol\paper_run.md'
$sourceRoot=(Resolve-Path -LiteralPath $cfg.predictor_source).Path
$sourceRows=Get-ChildItem -LiteralPath $sourceRoot -Recurse -File | Where-Object {$_.Extension -in '.py','.json','.ps1','.ini'} | Sort-Object FullName | ForEach-Object {[ordered]@{path=$_.FullName.Substring($sourceRoot.Length+1);sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash}}
$sourceManifestPath=Join-Path $run 'source_manifest.json'
$sourceRows | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $sourceManifestPath -Encoding UTF8
$sourceManifestSha=(Get-FileHash -Algorithm SHA256 -LiteralPath $sourceManifestPath).Hash
$arg="-NoProfile -ExecutionPolicy Bypass -File `"$worker`" -Project `"$project`" -Run `"$run`" -OldRun `"$($cfg.old_run)`" -Taskbook `"$taskbook`""
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5)
$principal=New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 12) -StartWhenAvailable
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
$receipt=[ordered]@{batch='Q1';run_id=(Split-Path -Leaf $run);run_dir=$run;task_name=$task;created_at=(Get-Date).ToString('o');source=$cfg.predictor_source;source_manifest_sha=$sourceManifestSha;protocol=(Resolve-Path $Protocol).Path;protocol_sha=(Get-FileHash -Algorithm SHA256 $Protocol).Hash;taskbook=$taskbook;taskbook_sha=(Get-FileHash -Algorithm SHA256 $taskbook).Hash;candidate_states=90;training=$false;budget_hours=12;stop='K1 verdict'}
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $receipts 'Q1.json') -Encoding UTF8
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $run 'launch_receipt.json') -Encoding UTF8
Start-ScheduledTask -TaskName $task
Start-Sleep -Seconds 4
Get-ScheduledTask -TaskName $task | Select-Object TaskName,State
Get-Content -LiteralPath (Join-Path $receipts 'Q1.json') -Raw
