@echo off
rem Hill E fix 1: benches, door frames, ladder, lights, glass pod, glass parapets
cd /d "%~dp0\.."
node index-cmd.js hill-1-fix-1.json -624 79 1777
pause
