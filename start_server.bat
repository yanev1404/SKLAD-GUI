@echo off
echo Starting Warehouse API...
cd /d "%~dp0"

REM Activate virtual environment if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

pause
