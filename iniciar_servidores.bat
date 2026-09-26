@echo off
title Servidores Finanzas DWH
set "ROOT=%~dp0"
set "UV=C:\Users\m.ortega\.local\bin\uv.exe"

echo ========================================================
echo  INICIANDO SISTEMA DE FINANZAS PERSONALES (PC Y MOVIL)
echo ========================================================
echo.
echo Abriendo servidor Backend (FastAPI - Puerto 8000)...
start "FastAPI Backend" powershell -NoExit -Command "Set-Location '%ROOT%app\backend'; & '%UV%' run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo Abriendo servidor Frontend (Next.js - Puerto 3000)...
start "Next.js Frontend" powershell -NoExit -Command "Set-Location '%ROOT%app\frontend'; npm run dev"

echo.
echo Servidores abiertos en ventanas independientes.
echo.
echo Accede en tu PC:
echo   http://localhost:3000
echo   o http://localhost:8000
echo.
echo Accede en tu telefono (mismo Wi-Fi):
echo   http://192.168.10.4:3000
echo ========================================================
