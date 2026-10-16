#!/bin/bash
# Kill game, rebuild agent, relaunch, wait for the control socket.
cd "$(dirname "$0")/.."
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Eclipse Adoptium/jdk-17.0.19.10-hotspot}"
taskkill //F //IM java.exe >/dev/null 2>&1; sleep 2
bash agent/build.sh || exit 1
powershell -NoProfile -Command "Start-Process powershell -ArgumentList '-NoProfile','-File','$(cygpath -w "$PWD/tools/launch_game.ps1")' -WindowStyle Minimized -RedirectStandardOutput '$(cygpath -w "$PWD/tools/game.log")' -RedirectStandardError '$(cygpath -w "$PWD/tools/game.err")'"
for i in $(seq 1 40); do grep -q "serving on" tools/game.log 2>/dev/null && break; sleep 1; done
sleep 3; grep REA tools/game.log
