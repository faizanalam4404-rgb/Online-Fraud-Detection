@echo off
echo =====================================================================
echo          🛡️  Starting FraudGuard - Online Payment Fraud Detection
echo =====================================================================
echo.

set PYTHON_CMD=

where python >nul 2>nul
if %ERRORLEVEL% equ 0 set PYTHON_CMD=python

if "%PYTHON_CMD%"=="" (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 set PYTHON_CMD=py
)

if "%PYTHON_CMD%"=="" (
    if exist "C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe" (
        set PYTHON_CMD="C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [WARNING] Python executable not found in PATH.
    echo Opening frontend/index.html directly in your default browser...
    start "" "frontend\index.html"
    pause
    exit /b 1
)

echo [INFO] Starting Flask Backend & ML Engine...
echo [INFO] Backend URL: http://127.0.0.1:5000
echo [INFO] Opening Browser...
start "" "http://127.0.0.1:5000"

%PYTHON_CMD% app.py
pause
