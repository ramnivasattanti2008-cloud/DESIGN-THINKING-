$adb = "C:\Users\Ram Nivas\mirror-toolchain\android-sdk\platform-tools\adb.exe"
$apk = Join-Path $PSScriptRoot "dist\mirror.apk"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   MIRROR Android Installer - Auto-Detect & Install" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Please ensure on your phone:" -ForegroundColor Yellow
Write-Host " 1. Settings > Developer Options > 'USB Debugging' is ON" -ForegroundColor Yellow
Write-Host " 2. Settings > Developer Options > 'Install via USB' is ON" -ForegroundColor Yellow
Write-Host " 3. Phone USB mode is set to 'File Transfer / Android Auto'" -ForegroundColor Yellow
Write-Host " 4. Check phone screen for 'Allow USB Debugging?' prompt and tap Allow" -ForegroundColor Yellow
Write-Host ""
Write-Host "Waiting for device to connect via ADB..." -ForegroundColor Green

& $adb wait-for-device
Write-Host "Device detected!" -ForegroundColor Green
Write-Host "Installing MIRROR APK ($apk)..." -ForegroundColor White

& $adb install -r -d $apk
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "SUCCESS! MIRROR is successfully installed on your phone!" -ForegroundColor Green
    Write-Host "Launching MIRROR..." -ForegroundColor Cyan
    & $adb shell monkey -p com.mirror.app -c android.intent.category.LAUNCHER 1
} else {
    Write-Host ""
    Write-Host "Installation failed. Check your phone screen to accept 'Install via USB'." -ForegroundColor Red
}
