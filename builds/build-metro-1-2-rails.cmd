@echo off
rem Metro stage 1, step 2: line 2 rails, boosters, redstone, buttons (ONLY after the test stand worked), about 2 min
rem BEFORE START: stand (or fly) near Cathedral square (about -690 66 1800) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js metro-1-rails.json -694 47 1748
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - done: ride line 2 and send remarks.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
