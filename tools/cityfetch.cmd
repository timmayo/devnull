@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
rem Do a city's resource links still work?   .\tools\cityfetch.cmd      .\tools\cityfetch.cmd grand_rapids --update
if not exist "%PY%" (
  echo .venv not found. Run .\play.cmd once first to create it.
  exit /b 1
)
set "PYTHONPATH=%ROOT%\src"
"%PY%" "%ROOT%\tools\cityfetch.py" %*
