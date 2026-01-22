# Code Signing & Trust Guide for PDF Screenshot Tool

This guide explains how to make your application appear trustworthy to Windows and antivirus software.

## Why Does Windows Show Warnings?

Windows SmartScreen and antivirus software flag executables that:
1. **Are not code-signed** - No verified publisher identity
2. **Are new/unknown** - Haven't built reputation yet
3. **Are packed/obfuscated** - PyInstaller bundles can trigger false positives
4. **Downloaded from internet** - Mark of the Web (MOTW) flag

---

## Level 1: Free Improvements (Already Applied)

✅ **Detailed Version Info** - Embedded in the .exe via `version_info.txt`
✅ **Professional Installer Metadata** - Publisher name, copyright, contact info
✅ **No Admin Required** - Installs to user folder (less suspicious)
✅ **Clean Installer UI** - Professional appearance

---

## Level 2: Code Signing Certificate ($70-500/year)

### Option A: Standard Code Signing (~$70-200/year)
- **Providers**: Sectigo, Comodo, DigiCert, GlobalSign
- **Effect**: Shows your name instead of "Unknown Publisher"
- **Downside**: Still needs to build SmartScreen reputation (1,000+ downloads)

### Option B: EV Code Signing (~$300-500/year) ⭐ RECOMMENDED
- **Providers**: Sectigo, DigiCert, GlobalSign
- **Effect**: INSTANT SmartScreen reputation - no warnings from day one
- **Requires**: Business verification (LLC, company registration)

### How to Sign Your Files

1. **Purchase certificate** from a trusted CA
2. **Install certificate** and signtool.exe (from Windows SDK)
3. **Sign the .exe**:
```powershell
signtool sign /f "your_certificate.pfx" /p "password" /tr http://timestamp.digicert.com /td sha256 /fd sha256 "dist\PDFScreenshotTool.exe"
```

4. **Sign the installer**:
```powershell
signtool sign /f "your_certificate.pfx" /p "password" /tr http://timestamp.digicert.com /td sha256 /fd sha256 "installer_output\PDFScreenshotTool_Setup_2.1.0.exe"
```

5. **Verify signature**:
```powershell
signtool verify /pa /v "dist\PDFScreenshotTool.exe"
```

---

## Level 3: Build SmartScreen Reputation

### Submit to Microsoft
1. Go to: https://www.microsoft.com/en-us/wdsi/filesubmission
2. Select "Software developer" 
3. Upload your signed .exe and installer
4. Provide your website URL and contact info
5. Wait 1-3 business days for review

### Submit to VirusTotal
1. Go to: https://www.virustotal.com
2. Upload your .exe file
3. If flagged as false positive, click "Request a re-analysis"
4. Contact specific AV vendors through their false positive forms:
   - Windows Defender: https://www.microsoft.com/en-us/wdsi/filesubmission
   - Avast/AVG: https://www.avast.com/false-positive-file-form.php
   - Kaspersky: https://opentip.kaspersky.com/
   - Norton: https://submit.norton.com/
   - Malwarebytes: https://www.malwarebytes.com/support/submit-a-file

---

## Level 4: Distribution Best Practices

### Use Trusted Download Sources
- ✅ GitHub Releases (shows as "github.com" source)
- ✅ Your own website with HTTPS
- ❌ Avoid file sharing sites, URL shorteners

### Provide Verification
Add to your download page:
```
SHA-256: abc123...
File Size: 12.5 MB
Signed by: Daniel Raphael
```

### Create a Verification Script
Users can verify the download:
```powershell
# Verify SHA-256 hash
$expectedHash = "YOUR_HASH_HERE"
$actualHash = (Get-FileHash "PDFScreenshotTool_Setup_2.1.0.exe" -Algorithm SHA256).Hash
if ($actualHash -eq $expectedHash) {
    Write-Host "✓ File integrity verified" -ForegroundColor Green
} else {
    Write-Host "✗ File may be corrupted or tampered" -ForegroundColor Red
}
```

---

## Quick Reference: Certificate Providers

| Provider | Standard OV | EV Code Signing | Notes |
|----------|-------------|-----------------|-------|
| [Sectigo](https://sectigo.com/ssl-certificates-tls/code-signing) | $75/yr | $319/yr | Most affordable |
| [DigiCert](https://www.digicert.com/signing/code-signing-certificates) | $474/yr | $559/yr | Premium, fast support |
| [GlobalSign](https://www.globalsign.com/en/code-signing-certificate) | $249/yr | $399/yr | Good middle ground |
| [SSL.com](https://www.ssl.com/certificates/ev-code-signing/) | $179/yr | $299/yr | Budget-friendly EV |

---

## Recommended Action Plan

### If you want ZERO warnings immediately:
1. Get an **EV Code Signing Certificate** (~$300/year)
2. Sign both .exe and installer
3. Users see your verified name, no SmartScreen warnings

### If you want to minimize cost:
1. Get a **Standard Code Signing Certificate** (~$75/year)
2. Sign both .exe and installer
3. Submit to Microsoft SmartScreen
4. Submit to VirusTotal
5. Build reputation over 1-2 weeks of downloads

### If you want FREE (current state):
1. Keep detailed metadata (✅ done)
2. Distribute via GitHub Releases
3. Provide SHA-256 hashes on download page
4. Submit to antivirus false positive forms
5. Accept that some users will see SmartScreen warnings

---

## Files Modified for Trust

- `version_info.txt` - Embedded Windows version info
- `PDFScreenshotTool.spec` - PyInstaller with version info
- `installer.iss` - Inno Setup with detailed publisher info

