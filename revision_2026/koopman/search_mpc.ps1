$root = 'D:\LEARNING\ZNN\ZNN\Adaptive-koopman\Adaptive-koopman-main'
Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.py' |
    Select-String -Pattern 'MPC|sequential.linear|S3.U1|46D' |
    Select-Object -First 300 Path, LineNumber, Line
