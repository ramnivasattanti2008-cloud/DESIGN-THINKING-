@echo off
setlocal
set ADB="C:\Users\Ram Nivas\mirror-toolchain\android-sdk\platform-tools\adb.exe"
set APK="%~dp0dist\mirror.apk"

echo ========================================================
echo   MIRROR Android Installer - Auto-Detect & Install
echo ========================================================
echo.
echo Check the following on your iQOO/Android phone:
echo 1. Settings ^> Developer Options ^> 'USB Debugging' is ON
echo 2. Settings ^> Developer Options ^> 'Install via USB' is ON
echo 3. When plugged in, select 'File Transfer / MTP' (not charging only)
echo 4. Check your phone screen and tap 'Always allow from this computer' ^> 'Allow'
echo.
echo Waiting for device...
%ADB% wait-for-device
echo Device detected!
echo.
echo Installing MIRROR APK (%APK%)...
%ADB% install -r -d %APK%
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo   SUCCESS! MIRROR is installed on your phone!
    echo ========================================================
    echo Launching MIRROR on your phone...
    %ADB% shell monkey -p com.mirror.app -c android.intent.category.LAUNCHER 1
) else (
    echo.
    echo Installation encountered an error.
    echo If your phone asked for permission 'Allow install via USB', tap ALLOW and run this script again.
)
echo.
pause
