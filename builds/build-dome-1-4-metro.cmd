@echo off
rem Underwater dome stage 1, step 4 of 4: metro: Embankment station, track, rails
rem BEFORE START: stand (or fly) near the dome / island A so the server keeps these chunks loaded.
cd /d "%~dp0\.."
node index-cmd.js dome-1-metro.json -751 52 1850
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - run the next step - all done.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
