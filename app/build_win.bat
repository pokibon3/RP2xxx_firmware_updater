@echo off
rem Build the Windows app -> dist\RP2xxx Updater.exe
cd /d "%~dp0"
if not exist .venv py -3 -m venv .venv
.venv\Scripts\pip install -q -r requirements.txt pyinstaller || exit /b 1
.venv\Scripts\pyinstaller --noconfirm rp2updater.spec || exit /b 1
echo -^> dist\RP2xxx Updater.exe
