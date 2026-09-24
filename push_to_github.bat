@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo   GitHub Upload Tool
echo ========================================
echo.

echo [1/5] Checking Git status...
git status
if errorlevel 1 (
    echo Error: Not a valid Git repository
    pause
    exit /b 1
)
echo.

echo [2/5] Adding files...
git add .
echo.

echo [3/5] Creating commit...
git commit -m "feat: add PostgreSQL + Prometheus + Grafana monitoring stack"
echo.

echo [4/5] Pushing to GitHub...
git push origin main
if errorlevel 1 (
    echo.
    echo Trying master branch...
    git push origin master
    if errorlevel 1 (
        echo.
        echo Push failed. Please check:
        echo   1. Network connection
        echo   2. Remote repository exists
        echo   3. Push permission
        echo.
        pause
        exit /b 1
    )
)
echo.

echo [5/5] Done!
echo Successfully pushed to GitHub
echo.
pause
