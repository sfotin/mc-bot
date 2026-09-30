@echo off
rem Mountain F stage 1: ground, spiral tower, buildings
cd /d "%~dp0\.."
node index-cmd.js mount-1-ground.json -624 70 1728
node index-cmd.js mount-1-tower.json -624 63 1758
node index-cmd.js mount-1-build.json -624 60 1735
pause
