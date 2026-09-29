@echo off
rem Old town: fixes to build (oldtown-7-fix-1, oldtown-8-fix-1)
cd /d "%~dp0\.."
node index-cmd.js oldtown-7-fix-1.json -707 65 1827
node index-cmd.js oldtown-8-fix-1.json -722 64 1818
pause
