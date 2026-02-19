@echo off
echo Starting Manual Entry Engine...
echo.
echo 1. Launching Backend Server...
start "" python manual_entry_app/app.py
echo.
echo 2. Waiting for server to start...
timeout /t 3 /nobreak >nul
echo.
echo 3. Opening Browser...
start http://127.0.0.1:8001
echo.
echo App is running! Do not close this window.
pause
