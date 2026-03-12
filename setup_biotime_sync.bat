@echo off
REM BioTime ERPNext Sync - ONE-TIME SETUP
REM Run this once before creating the Task Scheduler job
cd /d "%~dp0"

echo Creating Python virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create venv. Ensure Python is installed and in PATH.
    pause
    exit /b 1
)

echo Activating venv and installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements-biotime.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Setup complete. You can now:
echo 1. Edit biotime_config.py with your credentials
echo 2. Create Task Scheduler job using run_biotime_sync.bat
echo 3. Test: run_biotime_sync.bat
echo.
pause
