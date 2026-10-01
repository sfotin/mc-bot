@echo off
rem Underwater dome stage 1, step 3 of 4: garden, Dome station, gallery, pavilion, island plaza
rem BEFORE START: stand (or fly) near the dome / island A so the server keeps these chunks loaded.
cd /d "%~dp0\.."
node index-cmd.js dome-1-build.json -782 52 1903
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - run the next step: builds\build-dome-1-4-metro.cmd.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
