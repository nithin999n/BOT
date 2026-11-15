@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python autostart.py on
pause
