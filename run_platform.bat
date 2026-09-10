@echo off
title Launch SIH NGO Platform
echo ================================================================
echo   SIH NGO Fund Utilization Transparency Platform
echo ================================================================
echo.
echo [1/2] Launching Backend API Server (http://127.0.0.1:8000)...
start "SIH Platform - Backend (Port 8000)" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

timeout /t 2 >nul

echo [2/2] Launching Frontend Web App (http://localhost:5173)...
start "SIH Platform - Frontend (Port 5173)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ================================================================
echo   Platform is running!
echo   - Frontend Portal : http://localhost:5173/
echo   - Backend Docs    : http://127.0.0.1:8000/docs
echo ================================================================
echo.
echo To re-seed demonstration data anytime:
echo   Run: cd backend && .venv\Scripts\activate && python seed_sih_demo.py
echo.
pause
