Set-Location "C:\Users\keenk\paper\FT"
# lme4 は Claude アプリ(MSIX)の仮想化された利用者ライブラリにある。アプリの外から起動するタスクはそこを見ないので明示する
$env:R_LIBS = "C:\Users\keenk\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\R\win-library\4.6"
New-Item -ItemType Directory -Force "results\power_sim\pb_timing" | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "results\power_sim\pb_timing\launch_$stamp.log"
"started $(Get-Date -Format o)" | Out-File $log -Encoding utf8
& python -X utf8 -m code.analysis.pb_timing --config configs/pb_timing.yaml *>> $log
$code = $LASTEXITCODE
"exit $code at $(Get-Date -Format o)" | Out-File $log -Append -Encoding utf8
exit $code
