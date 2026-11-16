@echo off
cd /d "%~dp0"
python autostart.py setup
python autostart.py on
pause
