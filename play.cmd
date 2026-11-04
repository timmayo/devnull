@echo off
rem Runs /dev/null. First run creates a private Python environment (.venv) and installs the game.
rem Usage:  .\play.cmd --city grand_rapids        (any devnull options work: --admin, --no-quotes, --no-intro)
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto run
set PYV=
for %%V in (3.14 3.13 3.12 3.11) do if not defined PYV py -%%V -c "import sys" >nul 2>&1 && set PYV=%%V
if not defined PYV (
  echo Python 3.11 to 3.14 is required. Install 3.14 from https://www.python.org/downloads/windows/ and run this again.
  exit /b 1
)
echo Setting up with Python %PYV% ^(one time^)...
py -%PYV% -m venv .venv || exit /b 1
".venv\Scripts\python" -m pip install -q -e . python-docx || exit /b 1
:run
".venv\Scripts\devnull" %*
