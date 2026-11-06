@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
rem Reads the data\commands folder. Try:  .\tools\cmdtree.cmd --check --deep      .\tools\cmdtree.cmd --view needs -d      .\tools\cmdtree.cmd -g hack
set "CMDS=%ROOT%\data\commands"

if not exist "%PY%" (
  echo .venv not found. Run .\play.cmd once first to create it.
  exit /b 1
)

if not exist "%CMDS%\groups.yaml" (
  echo Not found: %CMDS%\groups.yaml
  exit /b 1
)

"%PY%" -c "import yaml" 2>nul || "%PY%" -m pip install -q pyyaml

"%PY%" "%ROOT%\tools\cmdtree.py" -f "%CMDS%" %*
