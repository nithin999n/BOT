@echo off
cd /d "%~dp0"
echo Get a key at https://console.anthropic.com  (Settings - API Keys)
python autostart.py set-key
pause
