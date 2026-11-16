@echo off
cd /d "%~dp0"
python autostart.py setup
"%LOCALAPPDATA%\BOT\venv\Scripts\python.exe" bot_agent.py
pause
