@echo off
rem Metro stage 0 fix 2: 3-block stop dips, fewer flat boosters on the test stand, under 1 min
rem BEFORE START: stand (or fly) near the test stand (about -835 72 1858) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js metro-0-fix-2.json -845 67 1844
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - done: ride a minecart on the stand and report: rails as designed, the cart stops in each dip, the button starts it.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
