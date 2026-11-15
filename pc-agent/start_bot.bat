@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python bot_agent.py
pause
