@echo off
echo === Building Outreach Hub ===
echo.

pip install pyinstaller --quiet 2>nul

echo [1/2] Running PyInstaller...
pyinstaller outreach_hub.spec --noconfirm

echo.
echo [2/2] Copying runtime files...
if not exist "dist\OutreachHub\secrets" mkdir "dist\OutreachHub\secrets"
if not exist "dist\OutreachHub\data" mkdir "dist\OutreachHub\data"
if exist ".env.example" copy /Y ".env.example" "dist\OutreachHub\.env.example" >nul

echo.
echo === Build complete! ===
echo Output: dist\OutreachHub\OutreachHub.exe
echo.
echo Next steps:
echo   1. Copy dist\OutreachHub\ folder to share
echo   2. Users run OutreachHub.exe directly
echo   3. Google Maps scraper requires: pip install playwright ^& playwright install chromium
echo.
pause
