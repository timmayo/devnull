@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
rem Is a city ready to ship? Lists what is still missing.   .\tools\citycheck.cmd      .\tools\citycheck.cmd --release
if not exist "%PY%" (
  echo .venv not found. Run .\play.cmd once first to create it.
  exit /b 1
)
set "PYTHONPATH=%ROOT%\src"
"%PY%" "%ROOT%\tools\citycheck.py" %*
