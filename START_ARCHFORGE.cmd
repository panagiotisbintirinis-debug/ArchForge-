@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=%CD%
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -m archforge.ui.app
) else (
  python -m archforge.ui.app
)
if errorlevel 1 pause
