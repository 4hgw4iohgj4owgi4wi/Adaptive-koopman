@echo off
cd /d D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main\revision_2026
set PYTHONPATH=paper_v4\src
E:\anaconda\envs\pytorch_new\python.exe -m paper_v4_core.r3_recovery_batch --out paper_v4\results\20260911_R3_UNFROZEN_FULL01 --selection paper_v4\results\20260911_R2C_COMPARE02\comparison.json --protocol paper_v4\inputs\experiment.md 1>paper_v4\results\20260911_R3_UNFROZEN_FULL01.stdout.log 2>paper_v4\results\20260911_R3_UNFROZEN_FULL01.stderr.log
echo %ERRORLEVEL%>paper_v4\results\20260911_R3_UNFROZEN_FULL01.exit_code.txt
