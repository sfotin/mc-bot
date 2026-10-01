@echo off
rem Industrial zone stage 2, step 3 of 3: greenhouse and three wind masts (about 2 min)
rem BEFORE START: stand (or fly) near (-630 80 1840) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js industry-2-green.json -656 59 1826
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - stage 2 is done: send screenshots and remarks to the chat.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
