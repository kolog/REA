# Play tomorrow: starts the game with the agent attached, then runs the bot in the foreground.
#   powershell -File tools/play.ps1                 # 100 s of the "auto" mission, repeat as many times as you like
#   powershell -File tools/play.ps1 -Mission train -Seconds 100
param([string]$Mission = "auto", [int]$Seconds = 100)
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
if (-not (Get-Process java -ErrorAction SilentlyContinue)) {
    $bash = (Get-Command bash -ErrorAction SilentlyContinue).Source
    if (-not $bash) { $bash = "C:\Program Files\Git\bin\bash.exe" }
    & $bash tools/restart.sh
}
python -u bot/run_brain.py $Seconds $Mission
