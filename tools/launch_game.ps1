# Starts PokeWilds with the REA agent attached (control socket on 127.0.0.1:7777).
param([string]$Game = "$env:USERPROFILE\Desktop\pokewilds-v0.8.11-windows-64", [int]$Port = 7777)
$java = (Get-ChildItem "C:\Program Files\Eclipse Adoptium\jdk-17*\bin\java.exe" | Select-Object -First 1).FullName
if (-not $java) { $java = "java" }
$agent = Join-Path $PSScriptRoot "..\agent\rea-agent.jar" | Resolve-Path
Set-Location $Game   # saves/settings are read relative to this folder
& $java "-javaagent:$agent=$Port" -cp "$Game\app\pokewilds.jar" com.pkmngen.game.desktop.DesktopLauncher
