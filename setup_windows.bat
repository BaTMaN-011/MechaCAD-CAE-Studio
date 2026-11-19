@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10 or newer from python.org and enable the Python launcher.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Creating the private Python environment...
    py -3 -m venv .venv
    if errorlevel 1 goto failed
)
echo Installing MechaCAD and CAE Studio packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup is complete. Double-click launch_windows.vbs to open the app.
pause
exit /b 0
:failed
echo Setup did not finish. Check your internet connection and Python installation, then run this file again.
pause
exit /b 1
