@echo off
rem City: fountain fix (City fountain, DECOR 5.3) and stage 4 - tower T1 "Opener"
cd /d "%~dp0\.."
node index-cmd.js city-1-fix-1.json -741 68 1821
node index-cmd.js city-4-opener.json -766 60 1797
pause
