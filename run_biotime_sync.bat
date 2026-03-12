@echo off
REM BioTime ERPNext Sync - Run via Task Scheduler
REM Requires: venv already created (run setup_biotime_sync.bat first)
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo ERROR: venv not found. Run setup_biotime_sync.bat first.
    exit /b 1
)

call venv\Scripts\activate.bat
python biotime_erpnext_sync.py --once
exit /b %errorlevel%
