@echo off
setlocal
cd /d "%~dp0"
title Energy MultiModel V1.5 - EMS Integrado

echo ================================================
echo   ENERGY MULTIMODEL V1.5 - EMS INTEGRADO
echo ================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no PATH.
    pause
    exit /b 1
)

python -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo [ERRO] A aplicacao foi encerrada com erro.
    pause
)
endlocal
