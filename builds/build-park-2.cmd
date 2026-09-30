@echo off
rem Park stage 2: zoo
cd /d "%~dp0\.."
node index-cmd.js park-2-zoo.json -655 60 1744
pause
