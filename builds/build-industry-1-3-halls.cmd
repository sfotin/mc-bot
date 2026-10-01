@echo off
rem Industrial zone stage 1, step 3 of 3: ore processing hall, production hall, central warehouse
rem BEFORE START: stand (or fly) near the halls (about -635 80 1860) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js industry-1-halls.json -656 59 1830
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - stage 1 is done: send screenshots and remarks to the chat.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
