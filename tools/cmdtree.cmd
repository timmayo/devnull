@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
rem Points at the NEW-format file for now. Switch to commands.yaml after migration.
set "CMDS=%ROOT%\data\commands2.yaml"

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
