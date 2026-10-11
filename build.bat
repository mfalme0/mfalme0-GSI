@echo off
setlocal
cd /d "%~dp0"

echo Installing build and application dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    exit /b 1
)

echo Building FH Sensor Studio...
python -m PyInstaller --noconfirm --clean --windowed --onefile --name "FHSensorStudio" --icon "assets\fhsensor.ico" --add-data "assets\fhsensor.ico;assets" --collect-all customtkinter --hidden-import serial.tools.list_ports app.py
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Build complete: dist\FHSensorStudio.exe
endlocal
