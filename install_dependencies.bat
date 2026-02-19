@echo off
echo ===================================================
echo   Manual Entry Engine - Installation Script
echo ===================================================
echo.
echo 1. Checking for Python...
python --version
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.8+ from python.org and try again.
    pause
    exit /b
)
echo [OK] Python found.
echo.

echo 2. Installing Python Libraries...
pip install -r manual_entry_app/requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install libraries.
    pause
    exit /b
)
echo [OK] Libraries installed.
echo.

echo 3. Installing Browsers (Playwright)...
playwright install
if errorlevel 1 (
    echo [ERROR] Failed to install browsers.
    pause
    exit /b
)
echo [OK] Browsers installed.
echo.

echo ===================================================
echo   SETUP COMPLETE!
echo   You can now run 'run_engine.bat' to start the app.
echo ===================================================
pause
