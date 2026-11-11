@echo off
REM Start the DSA coverage app and open it in the browser.
REM   Double-click this file, or run:  coverage_app\start.bat  [--port 8800]
REM   To use a specific Python (e.g. an Anaconda env):  set PYTHON=C:\path\to\python.exe  before running.
REM Stop with Ctrl+C (or close the window).
setlocal

REM Run from the project folder, so relative paths in the code resolve
cd /d "%~dp0.."

if defined PYTHON goto have_python
where python >nul 2>nul && (set "PYTHON=python" & goto have_python)
where py >nul 2>nul && (set "PYTHON=py -3" & goto have_python)
echo Python not found. Install it, or set PYTHON=C:\path\to\python.exe and run this file again.
pause
exit /b 1

:have_python
%PYTHON% -c "import pandas, openpyxl" >nul 2>nul
if errorlevel 1 (
  echo This Python is missing pandas or openpyxl. Install them with:
  echo   %PYTHON% -m pip install pandas openpyxl
  pause
  exit /b 1
)

%PYTHON% coverage_app\server.py %*
if errorlevel 1 pause
endlocal
