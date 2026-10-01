@echo off
rem Underwater dome stage 1: dry box (shells, stone fill), interiors and garden, metro. Strictly in this order.
cd /d "%~dp0\.."
node index-cmd.js dome-1-ground.json -783 36 1849
node index-cmd.js dome-1-build.json -782 52 1903
node index-cmd.js dome-1-metro.json -751 52 1850
pause
