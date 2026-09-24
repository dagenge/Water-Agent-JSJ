@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo   Water Agent Startup Tool
echo ========================================
echo.

echo [1/3] Activating Python environment...
call E:\Anaconda\Anaconda3\Scripts\activate.bat jsj_research
if errorlevel 1 (
    echo Error: Failed to activate environment
    pause
    exit /b 1
)
echo Environment activated: jsj_research
echo.

echo [2/3] Starting services...
echo Starting Prometheus Metrics Exporter and Streamlit...
echo.

echo [3/3] Launching Streamlit UI...
echo.
echo ========================================
echo   Agent is starting...
echo   Streamlit UI: http://localhost:8501
echo   Metrics API: http://localhost:8000/metrics
echo ========================================
echo.

python scripts/start_services.py

pause
