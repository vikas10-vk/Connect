@echo off
title ProConnect - First Time Setup
color 0B

echo.
echo  ================================================
echo   ProConnect - First Time Setup
echo  ================================================
echo.
echo  This will install all dependencies.
echo  Make sure you have: Python 3.11+, Node.js 18+, Docker Desktop
echo.
pause

:: ── Backend Python setup ──────────────────────────────────────────────
echo.
echo [1/3] Setting up Python virtual environment...
cd /d "%~dp0backend"

if not exist venv (
    python -m venv venv
    echo  Virtual environment created.
) else (
    echo  Virtual environment already exists, skipping.
)

echo.
echo [2/3] Installing Python dependencies...
call venv\Scripts\activate
pip install -r requirements.txt
echo  Python dependencies installed.

:: ── Run DB migrations ─────────────────────────────────────────────────
echo.
echo [2b] Starting Docker and running database migrations...
cd /d "%~dp0"
docker-compose up -d
timeout /t 4 /nobreak >nul

cd /d "%~dp0backend"
call venv\Scripts\activate
alembic upgrade head
echo  Database migrations applied.

:: ── Frontend Node setup ───────────────────────────────────────────────
echo.
echo [3/3] Installing Node.js dependencies...
cd /d "%~dp0frontend"
npm install
echo  Node.js dependencies installed.

echo.
echo  ================================================
echo   Setup complete!
echo.
echo   Now run start.bat to launch the application.
echo  ================================================
echo.
pause
