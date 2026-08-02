@echo off
setlocal
cd /d "%~dp0"
title Russian + Mandarin DLPT Hugging Face Repair

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PYTHON_CMD=python"
  ) else (
    echo.
    echo ERROR: Python was not found on this Windows computer.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
    echo During installation, select "Add Python to PATH", then run this file again.
    echo.
    pause
    exit /b 1
  )
)

echo Installing or updating the official Hugging Face upload client...
%PYTHON_CMD% -m pip install --upgrade huggingface_hub
if errorlevel 1 (
  echo.
  echo ERROR: Could not install huggingface_hub.
  echo Check the internet connection and run this file again.
  echo.
  pause
  exit /b 1
)

%PYTHON_CMD% "%~dp0upload_to_huggingface.py"
endlocal
