@echo off
REM BioTime ERPNext Sync - Run via Task Scheduler
cd /d "%~dp0"

call venv\Scripts\activate.bat
python biotime_erpnext_sync.py --once
exit /b 0
