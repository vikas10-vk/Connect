@echo off
title ProConnect - Startup
color 0A

echo.
echo  ================================================
echo   ProConnect - Starting All Services
echo  ================================================
echo.

:: ── Step 1: Start Docker (Postgres + Redis) ──────────────────────────
echo [1/4] Starting Docker services (PostgreSQL + Redis)...
cd /d "%~dp0"
docker-compose up -d
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: Docker failed. Make sure Docker Desktop is running!
    pause
    exit /b 1
)
echo  Docker services started.
echo.

:: Wait for DB to be ready
echo  Waiting 3s for database to initialize...
timeout /t 3 /nobreak >nul

:: ── Step 2: Start Backend ─────────────────────────────────────────────
echo [2/4] Starting FastAPI Backend on http://localhost:8000 ...
cd /d "%~dp0backend"
start "ProConnect Backend" cmd /k "call venv\Scripts\activate && uvicorn main:app --reload --port 8000"
echo  Backend window opened.
echo.

:: Wait for backend to boot
timeout /t 4 /nobreak >nul

:: ── Step 3: Start Celery Worker ───────────────────────────────────────
echo [3/4] Starting Celery Worker...
cd /d "%~dp0backend"
start "ProConnect Celery" cmd /k "call venv\Scripts\activate && celery -A workers.celery_app worker --loglevel=info --pool=solo"
echo  Celery worker window opened.
echo.

:: ── Step 4: Start Frontend ────────────────────────────────────────────
echo [4/4] Starting Next.js Frontend on http://localhost:3000 ...
cd /d "%~dp0frontend"
start "ProConnect Frontend" cmd /k "npm run dev"
echo  Frontend window opened.
echo.

:: Wait for frontend to boot
timeout /t 5 /nobreak >nul

:: ── Open browser ──────────────────────────────────────────────────────
echo  Opening browser...
start "" "http://localhost:3000"

echo.
echo  ================================================
echo   All services are running!
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo  ================================================
echo.
echo  Press any key to close this launcher window.
echo  (Other service windows will keep running)
pause >nul
