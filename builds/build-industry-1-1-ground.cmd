@echo off
rem Industrial zone stage 1, step 1 of 3: void filling, platform, slopes, roads, lights (about 11 min)
rem BEFORE START: stand (or fly) in the middle of the industrial zone (about -625 70 1880) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js industry-1-ground.json -661 54 1821
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - run the next step: builds\build-industry-1-2-npp.cmd.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
