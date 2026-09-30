@echo off
rem Park stage 1: streets, lake, alleys, lawns, lamps, trees; then park objects
cd /d "%~dp0\.."
node index-cmd.js park-1-ground.json -662 47 1745
node index-cmd.js park-1-build.json -655 60 1775
pause
