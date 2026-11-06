@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
rem Builds docs\command_viewer.html from data\ and opens it in your browser. Run it again after you change data.

if not exist "%PY%" (
  echo .venv not found. Run .\play.cmd once first to create it.
  exit /b 1
)

"%PY%" -c "import yaml" 2>nul || "%PY%" -m pip install -q pyyaml

"%PY%" "%ROOT%\tools\cmdview.py" --open %*
