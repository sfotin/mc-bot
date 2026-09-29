@echo off
rem City (Siti), stages 1-3: streets, then plaza/parks
cd /d "%~dp0\.."
node index-cmd.js city-1-streets.json -800 64 1776
node index-cmd.js city-1-parks.json -799 52 1778
pause
