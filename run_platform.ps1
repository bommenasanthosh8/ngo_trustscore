# SIH NGO Fund Utilization Transparency Platform - PowerShell Launcher

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  SIH NGO Fund Utilization Transparency Platform" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Cyan

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n[1/2] Starting Backend API Server (http://127.0.0.1:8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\backend'; .\ .venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

Start-Sleep -Seconds 2

Write-Host "[2/2] Starting Frontend Web App (http://localhost:5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$rootDir\frontend'; npm run dev"

Write-Host "`n================================================================" -ForegroundColor Cyan
Write-Host "  Platform is running in separate windows!" -ForegroundColor Green
Write-Host "  - Frontend Portal : http://localhost:5173/" -ForegroundColor White
Write-Host "  - Backend Docs    : http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "================================================================" -ForegroundColor Cyan
