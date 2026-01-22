# Build script for Vercel deployment
# This script prepares the public folder with all necessary files

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PDF Screenshot Tool - Build for Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Create public directory
$publicDir = "public"
if (Test-Path $publicDir) {
    Remove-Item -Recurse -Force $publicDir
}
New-Item -ItemType Directory -Path $publicDir | Out-Null
New-Item -ItemType Directory -Path "$publicDir/assets" | Out-Null

Write-Host "`n[1/4] Copying website files..." -ForegroundColor Yellow
Copy-Item "index.html" "$publicDir/"
Copy-Item "landing-page.html" "$publicDir/"

Write-Host "[2/4] Copying assets..." -ForegroundColor Yellow
if (Test-Path "assets/icon.ico") {
    Copy-Item "assets/icon.ico" "$publicDir/assets/"
}

Write-Host "[3/4] Copying application files..." -ForegroundColor Yellow
# Copy the latest built exe
if (Test-Path "dist/PDFScreenshotTool.exe") {
    Copy-Item "dist/PDFScreenshotTool.exe" "$publicDir/"
    Write-Host "  - Copied PDFScreenshotTool.exe from dist/" -ForegroundColor Green
} elseif (Test-Path "PDFScreenshotTool.exe") {
    Copy-Item "PDFScreenshotTool.exe" "$publicDir/"
    Write-Host "  - Copied PDFScreenshotTool.exe from root" -ForegroundColor Green
} else {
    Write-Host "  - WARNING: PDFScreenshotTool.exe not found!" -ForegroundColor Red
}

Write-Host "[4/4] Creating ZIP archive..." -ForegroundColor Yellow
# Create fresh zip file
$zipPath = "$publicDir/PDFScreenshotTool.zip"
if (Test-Path "$publicDir/PDFScreenshotTool.exe") {
    Compress-Archive -Path "$publicDir/PDFScreenshotTool.exe" -DestinationPath $zipPath -Force
    Write-Host "  - Created PDFScreenshotTool.zip" -ForegroundColor Green
} else {
    Write-Host "  - WARNING: Could not create ZIP - exe not found!" -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Build complete! Files in ./public/" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

# List files
Write-Host "`nDeployment files:"
Get-ChildItem -Recurse $publicDir | ForEach-Object {
    $relativePath = $_.FullName.Replace((Get-Location).Path + "\$publicDir\", "")
    if ($_.PSIsContainer) {
        Write-Host "  [DIR] $relativePath" -ForegroundColor Blue
    } else {
        $size = "{0:N2} KB" -f ($_.Length / 1KB)
        Write-Host "  $relativePath ($size)" -ForegroundColor White
    }
}


