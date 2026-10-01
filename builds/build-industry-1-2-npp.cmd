@echo off
rem Industrial zone stage 1, step 2 of 3: nuclear plant building (4 reactor halls, domes, stack) and two cooling towers
rem BEFORE START: stand (or fly) near the nuclear plant (about -607 90 1905) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js industry-1-npp.json -622 59 1891
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - run the next step: builds\build-industry-1-3-halls.cmd.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
