# PDF Screenshot Tool - Installer Build Script
# This script builds the application and creates a professional installer

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PDF Screenshot Tool - Build Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Inno Setup is installed
$InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$InnoSetupPathAlt = "C:\Program Files\Inno Setup 6\ISCC.exe"

if (Test-Path $InnoSetupPath) {
    $ISCC = $InnoSetupPath
} elseif (Test-Path $InnoSetupPathAlt) {
    $ISCC = $InnoSetupPathAlt
} else {
    Write-Host "ERROR: Inno Setup 6 not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Inno Setup 6 from:" -ForegroundColor Yellow
    Write-Host "https://jrsoftware.org/isdl.php" -ForegroundColor Blue
    Write-Host ""
    Write-Host "After installing, run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host "Found Inno Setup at: $ISCC" -ForegroundColor Green
Write-Host ""

# Step 1: Build the Python application
Write-Host "[1/3] Building Python application..." -ForegroundColor Yellow
pyinstaller --onefile --noconsole --icon=assets/icon.ico --name=PDFScreenshotTool --add-data "assets;assets" src/main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Application built successfully!" -ForegroundColor Green
Write-Host ""

# Step 2: Create installer output directory
Write-Host "[2/3] Preparing installer..." -ForegroundColor Yellow
if (-not (Test-Path "installer_output")) {
    New-Item -ItemType Directory -Path "installer_output" | Out-Null
}

# Step 3: Build the installer
Write-Host "[3/3] Building installer with Inno Setup..." -ForegroundColor Yellow
& $ISCC "installer.iss"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Installer build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Installer created at:" -ForegroundColor Cyan
Write-Host "  installer_output\PDFScreenshotTool_Setup.exe" -ForegroundColor White
Write-Host ""

# Copy to root for easy access
Copy-Item "installer_output\PDFScreenshotTool_Setup.exe" ".\PDFScreenshotTool_Setup.exe" -Force
Write-Host "Also copied to: PDFScreenshotTool_Setup.exe" -ForegroundColor Cyan


