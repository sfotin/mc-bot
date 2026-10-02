@echo off
rem Industrial zone stage 3: basement under the greenhouse (slots under farmland, stairs from the main aisle), about 1 min
rem BEFORE START: stand (or fly) near the greenhouse (about -644 75 1836) so the chunks stay loaded.
cd /d "%~dp0\.."
node index-cmd.js industry-3-basement.json -656 61 1826
echo.
echo CHECK the last summary line above: the number of errors (N) must be 0.
echo If N is 0 - done: send screenshots and remarks to the chat.
echo If N is not 0 - run the retry command printed above (node index-cmd.js --retry logs\failed-...txt) until 0.
pause
