@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   ENERGY MULTIMODEL V1.3.1 - SOLAR + EOLICA + TERMICA
echo                  + BATERIA + H2 / PEMFC
echo ============================================================
echo.

python -c "import streamlit, numpy, pandas, scipy, plotly" >nul 2>&1
if errorlevel 1 (
    echo Dependencias incompletas neste Python.
    echo Instale com:
    echo     pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

python -m streamlit run app.py
endlocal
