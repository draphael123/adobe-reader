# PDF Screenshot Tool - Signing and Packaging Script
# This script signs the executable and installer, generates hashes, and prepares for distribution

param(
    [string]$CertPath = "",
    [string]$CertPassword = "",
    [switch]$SkipSigning = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PDF Screenshot Tool - Sign & Package" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$version = "2.1.0"
$exePath = "dist\PDFScreenshotTool.exe"
$installerPath = "installer_output\PDFScreenshotTool_Setup_$version.exe"
$timestampServer = "http://timestamp.digicert.com"

# Check if files exist
if (-not (Test-Path $exePath)) {
    Write-Host "ERROR: $exePath not found. Run build first!" -ForegroundColor Red
    exit 1
}

# ===== SIGNING =====
if (-not $SkipSigning) {
    if ($CertPath -eq "" -or -not (Test-Path $CertPath)) {
        Write-Host "`n[!] No certificate provided. Skipping signing." -ForegroundColor Yellow
        Write-Host "    To sign, run: .\sign-and-package.ps1 -CertPath 'cert.pfx' -CertPassword 'password'" -ForegroundColor Gray
    } else {
        Write-Host "`n[1/4] Signing executable..." -ForegroundColor Yellow
        
        # Check for signtool
        $signtool = Get-Command signtool -ErrorAction SilentlyContinue
        if (-not $signtool) {
            # Try to find signtool in Windows SDK
            $sdkPaths = @(
                "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe",
                "${env:ProgramFiles}\Windows Kits\10\bin\*\x64\signtool.exe"
            )
            foreach ($path in $sdkPaths) {
                $found = Get-ChildItem $path -ErrorAction SilentlyContinue | Sort-Object -Descending | Select-Object -First 1
                if ($found) {
                    $signtool = $found.FullName
                    break
                }
            }
        }
        
        if (-not $signtool) {
            Write-Host "ERROR: signtool.exe not found. Install Windows SDK." -ForegroundColor Red
            exit 1
        }
        
        # Sign the exe
        & $signtool sign /f $CertPath /p $CertPassword /tr $timestampServer /td sha256 /fd sha256 $exePath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to sign executable" -ForegroundColor Red
            exit 1
        }
        Write-Host "  ✓ Executable signed" -ForegroundColor Green
        
        # Sign the installer if it exists
        if (Test-Path $installerPath) {
            Write-Host "`n[2/4] Signing installer..." -ForegroundColor Yellow
            & $signtool sign /f $CertPath /p $CertPassword /tr $timestampServer /td sha256 /fd sha256 $installerPath
            if ($LASTEXITCODE -ne 0) {
                Write-Host "ERROR: Failed to sign installer" -ForegroundColor Red
                exit 1
            }
            Write-Host "  ✓ Installer signed" -ForegroundColor Green
        }
    }
} else {
    Write-Host "`n[!] Signing skipped (use -SkipSigning:$false to enable)" -ForegroundColor Yellow
}

# ===== GENERATE HASHES =====
Write-Host "`n[3/4] Generating verification hashes..." -ForegroundColor Yellow

$hashes = @()

# Hash the exe
$exeHash = (Get-FileHash $exePath -Algorithm SHA256).Hash
$exeSize = (Get-Item $exePath).Length
$hashes += [PSCustomObject]@{
    File = "PDFScreenshotTool.exe"
    SHA256 = $exeHash
    Size = $exeSize
    SizeFormatted = "{0:N2} MB" -f ($exeSize / 1MB)
}
Write-Host "  PDFScreenshotTool.exe: $exeHash" -ForegroundColor Gray

# Hash the installer if it exists
if (Test-Path $installerPath) {
    $installerHash = (Get-FileHash $installerPath -Algorithm SHA256).Hash
    $installerSize = (Get-Item $installerPath).Length
    $hashes += [PSCustomObject]@{
        File = "PDFScreenshotTool_Setup_$version.exe"
        SHA256 = $installerHash
        Size = $installerSize
        SizeFormatted = "{0:N2} MB" -f ($installerSize / 1MB)
    }
    Write-Host "  Installer: $installerHash" -ForegroundColor Gray
}

# ===== CREATE CHECKSUMS FILE =====
Write-Host "`n[4/4] Creating checksums file..." -ForegroundColor Yellow

$checksumContent = @"
# PDF Screenshot Tool v$version - File Checksums
# Generated: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss UTC" -AsUTC)
# 
# Verify downloads by comparing SHA-256 hashes:
# PowerShell: (Get-FileHash "filename.exe" -Algorithm SHA256).Hash

"@

foreach ($hash in $hashes) {
    $checksumContent += "`n$($hash.File)`n"
    $checksumContent += "  SHA-256: $($hash.SHA256)`n"
    $checksumContent += "  Size: $($hash.SizeFormatted) ($($hash.Size) bytes)`n"
}

$checksumContent | Out-File -FilePath "CHECKSUMS.txt" -Encoding UTF8
Write-Host "  ✓ Created CHECKSUMS.txt" -ForegroundColor Green

# ===== SUMMARY =====
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Packaging Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`nFiles ready for distribution:" -ForegroundColor White
foreach ($hash in $hashes) {
    Write-Host "  • $($hash.File) ($($hash.SizeFormatted))" -ForegroundColor Gray
}

Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "  1. Upload to GitHub Releases" -ForegroundColor Gray
Write-Host "  2. Include CHECKSUMS.txt in release" -ForegroundColor Gray
Write-Host "  3. Submit to VirusTotal: https://www.virustotal.com" -ForegroundColor Gray
Write-Host "  4. Submit to SmartScreen: https://www.microsoft.com/en-us/wdsi/filesubmission" -ForegroundColor Gray

Write-Host ""

