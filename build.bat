@echo off
REM PDF Screenshot Tool - Build Script for Windows
REM This script builds the executable and creates the installer

echo ========================================
echo PDF Screenshot Tool - Build Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Create assets directory if it doesn't exist
if not exist "assets" mkdir assets

REM Check if icon exists, create placeholder if not
if not exist "assets\icon.ico" (
    echo NOTE: No icon.ico found in assets folder.
    echo The build will use a default icon.
    echo To add a custom icon, place icon.ico in the assets folder.
)

REM Build executable
echo.
echo Building executable with PyInstaller...
pyinstaller pdf_screenshot_tool.spec --clean

if errorlevel 1 (
    echo ERROR: PyInstaller build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build complete!
echo ========================================
echo.
echo Executable location: dist\PDFScreenshotTool.exe
echo.
echo Next steps:
echo 1. Test the executable by running dist\PDFScreenshotTool.exe
echo 2. Install Inno Setup from https://jrsoftware.org/isdl.php
echo 3. Open installer.iss in Inno Setup Compiler
echo 4. Click Build ^> Compile to create the installer
echo.
echo The installer will be created in: installer_output\
echo.

pause
