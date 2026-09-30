@echo off
rem Hill E stages 1-2: ground, TV tower
cd /d "%~dp0\.."
node index-cmd.js hill-1-ground.json -624 63 1773
node index-cmd.js hill-1-tower.json -617 60 1779
pause
