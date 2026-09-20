@echo off
setlocal EnableExtensions

REM Enterprise Life Health Platform one-click launcher.
set "ROOT=%~dp0"
for /f "usebackq tokens=*" %%I in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } ^| Select-Object -First 1 -ExpandProperty IPAddress)"`) do set "LAN_IP=%%I"
if not defined LAN_IP set "LAN_IP=localhost"

cd /d "%ROOT%"
title Enterprise Life Health Platform

echo [1/4] Building and starting PostgreSQL, Redis, Qdrant, MinIO and Backend...
docker compose -f "%ROOT%docker-compose.yml" up -d --build
if errorlevel 1 (
  echo Failed to start Docker infrastructure. Please make sure Docker Desktop is running.
  pause
  exit /b 1
)

echo [2/4] Waiting for the API to become ready...
timeout /t 5 /nobreak >nul

echo [3/4] Starting the LAN-enabled Vite and Electron client...
echo Local URL: http://127.0.0.1:5341/
echo LAN URL:   http://%LAN_IP%:5341/
echo Backend:   http://127.0.0.1:8002/
echo.
echo ========================================
echo Enterprise Life Health Platform started
echo Frontend: http://127.0.0.1:5341/
echo LAN:      http://%LAN_IP%:5341/
echo Backend:  http://127.0.0.1:8002/
echo ========================================
cd /d "%ROOT%frontend"
npm run desktop:dev

echo.
echo [ERROR] Platform startup failed or stopped.
pause
exit /b 1

endlocal
