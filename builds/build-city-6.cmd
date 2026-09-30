@echo off
rem City, hill: Pebbles x3, summit platform and balloon
cd /d "%~dp0\.."
node index-cmd.js city-6-pebbles.json -800 60 1793
node index-cmd.js city-6-summit.json -800 69 1782
pause
