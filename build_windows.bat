@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_windows.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name "MechaCAD-CAE-Studio" --paths "src" --collect-all PySide6 --collect-all keyring --collect-all mysql.connector --collect-all numpy main.pyw
if errorlevel 1 goto failed
echo Build complete: dist\MechaCAD-CAE-Studio\MechaCAD-CAE-Studio.exe
pause
exit /b 0
:failed
echo Build failed. Review the message above and try again.
pause
exit /b 1
