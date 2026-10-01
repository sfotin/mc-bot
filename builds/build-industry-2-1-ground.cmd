@echo off
rem Industrial zone stage 2, step 1 of 3: tech galleries under the roads, cobblestone hall under the warehouse, access shaft, approaches (about 2 min)
rem BEFORE START: stand (or fly) near (-615 40 1860) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js industry-2-ground.json -657 14 1821
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - run the next step: builds\build-industry-2-2-build.cmd.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
