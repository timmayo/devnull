@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
rem Reads data\commands.yaml. Try:  .\tools\cmdtree.cmd --check --deep      .\tools\cmdtree.cmd --view gate -d
set "CMDS=%ROOT%\data\commands.yaml"

if not exist "%PY%" (
  echo .venv not found. Run .\play.cmd once first to create it.
  exit /b 1
)

if not exist "%CMDS%" (
  echo Not found: %CMDS%
  exit /b 1
)

"%PY%" -c "import yaml" 2>nul || "%PY%" -m pip install -q pyyaml

"%PY%" "%ROOT%\tools\cmdtree.py" -f "%CMDS%" %*
