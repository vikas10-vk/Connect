@echo off
title ProConnect - Stop All Services
color 0C

echo.
echo  Stopping all ProConnect services...
echo.

docker-compose down
echo  Docker services stopped.

taskkill /FI "WINDOWTITLE eq ProConnect Backend" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ProConnect Celery" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ProConnect Frontend" /F >nul 2>&1

echo  All services stopped.
echo.
pause
