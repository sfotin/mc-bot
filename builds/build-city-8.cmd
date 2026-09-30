@echo off
rem City stage 8: remove old balloon and helicopter, bigger helicopter; four balloons
cd /d "%~dp0\.."
node index-cmd.js city-8-fix-1.json -800 158 1782
node index-cmd.js city-8-balloons.json -762 78 1793
pause
