@echo off
setlocal
title 8-bit Heightmap Fixer

if "%~1"=="" (
  echo Drag one or more heightmap images onto this file.
  echo.
  pause
  exit /b 2
)

set "SCRIPT=%~dp0fix_heightmaps.py"
set "PYTHON="
set "PYARGS="

rem Prefer a normal Python install, then fall back to Codex's bundled runtime.
py -3 -c "import sys" >nul 2>nul && set "PYTHON=py" && set "PYARGS=-3"
if not defined PYTHON python -c "import sys" >nul 2>nul && set "PYTHON=python"
if not defined PYTHON if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not defined PYTHON (
  echo ERROR: Python 3 was not found. Install it from https://www.python.org/
  pause
  exit /b 1
)

"%PYTHON%" %PYARGS% -c "import numpy, PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing the required Pillow and NumPy packages for this user...
  "%PYTHON%" %PYARGS% -m pip install --user Pillow numpy
  if errorlevel 1 (
    echo ERROR: Could not install the required packages.
    pause
    exit /b 1
  )
)

"%PYTHON%" %PYARGS% "%SCRIPT%" %*
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" echo Finished successfully. Originals were not changed.
if not "%RESULT%"=="0" echo Finished with one or more errors.
pause
exit /b %RESULT%
