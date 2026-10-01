@echo off
rem Industrial zone stage 2, step 2 of 3: dispatch tower, substation with stairs to the galleries, autocraft hall, matter lab, turbine hall, pump house (about 5 min)
rem BEFORE START: stand (or fly) near (-625 85 1885) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js industry-2-build.json -656 59 1859
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - run the next step: builds\build-industry-2-3-green.cmd.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
