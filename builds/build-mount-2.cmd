@echo off
rem Mountain F stage 2: demolition of stage 1, ice track, start and stand
cd /d "%~dp0\.."
node index-cmd.js mount-2-demolish.json -626 60 1728
node index-cmd.js mount-2-track.json -662 62 1642
node index-cmd.js mount-2-start.json -610 77 1735
pause
