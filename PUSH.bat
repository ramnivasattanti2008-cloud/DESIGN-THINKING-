@echo off
cd /d "%~dp0"
echo ============================================
echo  Pushing Bharat-Scam-X to GitHub
echo ============================================
echo.
git remote -v
echo.
echo If a browser window opens, sign in to GitHub. That is normal.
echo.
git push -u origin main
echo.
if %ERRORLEVEL%==0 (
  echo  DONE. Open: https://github.com/ramnivasattanti2008-cloud/DESIGN-THINKING-
) else (
  echo  Push failed. Most likely you are not signed in to git on this machine.
  echo  Fix: install Git for Windows ^(it bundles Credential Manager^), then run this again.
)
echo.
pause
