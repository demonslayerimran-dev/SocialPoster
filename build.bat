@echo off
REM ============================================================
REM  SocialPoster - build the Windows .exe
REM  Double-click this file. Needs Python 3.10+ (python.org)
REM  with "Add Python to PATH" checked during install.
REM ============================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo [X] Python is not installed or not in PATH.
  echo     Download it from https://www.python.org/downloads/
  echo     and tick "Add Python to PATH" during install.
  pause
  exit /b 1
)

echo [1/3] Creating virtual environment...
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat

echo [2/3] Installing libraries (first time takes a few minutes)...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 ( echo [X] Install failed. & pause & exit /b 1 )

echo [3/3] Building SocialPoster.exe ...
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name SocialPoster ^
  --icon assets\icon.ico ^
  --add-data "templates;templates" ^
  --collect-data googleapiclient ^
  --hidden-import waitress ^
  desktop.py
if errorlevel 1 ( echo [X] Build failed. & pause & exit /b 1 )

echo.
echo ============================================================
echo  DONE!  Your app is here:  dist\SocialPoster.exe
echo  You can copy it anywhere (Desktop...) and double-click it.
echo ============================================================
explorer dist
pause
