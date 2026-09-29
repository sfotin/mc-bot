@echo off
rem City stages 5-7 (without the hill): Gate, Exchange, Sail, Spiral, Three towers, Horseshoe
cd /d "%~dp0\.."
node index-cmd.js city-5-gate.json -756 60 1830
node index-cmd.js city-5-bridge.json -739 60 1795
node index-cmd.js city-6-sail.json -797 60 1821
node index-cmd.js city-7-spiral.json -785 60 1777
node index-cmd.js city-7-decks.json -766 63 1777
node index-cmd.js city-7-ring.json -766 60 1843
pause
