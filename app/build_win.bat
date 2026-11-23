@echo off
rem Build the Windows app -> dist\win\RP2xxx Updater.exe
cd /d "%~dp0"
if not exist .venv py -3 -m venv .venv
.venv\Scripts\pip install -q -r requirements.txt pyinstaller || exit /b 1
.venv\Scripts\pyinstaller --noconfirm --distpath dist\win --workpath build\win rp2updater.spec || exit /b 1
powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\win\RP2xxx Updater.exe' -DestinationPath dist\win\RP2xxx-Updater-windows.zip" || exit /b 1
echo -^> dist\win\RP2xxx Updater.exe / dist\win\RP2xxx-Updater-windows.zip
