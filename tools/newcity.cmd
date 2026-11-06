@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
rem Start a new city.   .\tools\newcity.cmd rochester_ny --name "Rochester" --state "New York"
if not exist "%PY%" (
  echo .venv not found. Run .\play.cmd once first to create it.
  exit /b 1
)
set "PYTHONPATH=%ROOT%\src"
"%PY%" "%ROOT%\tools\newcity.py" %*
