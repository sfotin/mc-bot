@echo off
rem Mountain F fix 1: forecourt at the stairs to the start, stairs 3 wide
cd /d "%~dp0\.."
node index-cmd.js mount-2-fix-1.json -593 78 1746
pause
