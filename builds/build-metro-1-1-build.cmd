@echo off
rem Metro stage 1, step 1: Center interchange, common tunnel piece, collector, line 2 stations and tunnel, about 5-10 min
rem BEFORE START: stand (or fly) near Cathedral square (about -690 66 1800) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js metro-1-build.json -709 48 1747
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - done: send screenshots; run build-metro-1-2-rails.cmd only after the test stand worked.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
