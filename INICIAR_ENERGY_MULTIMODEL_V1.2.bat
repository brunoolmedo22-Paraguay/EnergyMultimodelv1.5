@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo       ENERGY MULTIMODEL V1.2 - SOLAR + EOLICA + TERMICA
echo ============================================================
echo.

python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Streamlit nao encontrado neste Python.
    echo Instale as dependencias com:
    echo     pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

python -m streamlit run app.py
endlocal
