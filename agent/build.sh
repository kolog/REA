#!/bin/bash
# Builds agent/rea-agent.jar (needs a JDK 17 on PATH or JAVA_HOME)
set -e
cd "$(dirname "$0")"
JBIN="${JAVA_HOME:+$JAVA_HOME/bin/}"
rm -rf build && mkdir build
"${JBIN}javac" --release 17 -d build src/rea/Agent.java
printf 'Premain-Class: rea.Agent\nAgent-Class: rea.Agent\nCan-Retransform-Classes: false\n' > build/MANIFEST.MF
"${JBIN}jar" cfm rea-agent.jar build/MANIFEST.MF -C build rea
echo "built agent/rea-agent.jar"
