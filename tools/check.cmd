@echo off
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
rem Everything GitHub runs on each push, in one go. Run it before you commit:  .\tools\check.cmd
if not exist "%PY%" (
  echo .venv not found. Run .\play.cmd once first to create it.
  exit /b 1
)
"%PY%" -c "import yaml, jsonschema" 2>nul || "%PY%" -m pip install -q pyyaml jsonschema
set "PYTHONPATH=%ROOT%\src"
set FAIL=0

echo == command files match the schema
"%PY%" "%ROOT%\tools\validate_schema.py" || set FAIL=1

echo == command table (conditions, handlers, rules)
"%PY%" "%ROOT%\tools\cmdtree.py" -f "%ROOT%\data\commands" --check --deep || set FAIL=1

echo == save and load
"%PY%" "%ROOT%\tools\test_save.py" > "%TEMP%\devnull_test_save.txt" 2>&1 && echo OK || (type "%TEMP%\devnull_test_save.txt" & set FAIL=1)

echo == a short run plays through
"%PY%" "%ROOT%\tools\run_slice.py" --seeds 2 --policy idle > nul && echo OK || set FAIL=1

echo == city status (a report: blockers must be zero to ship a city)
"%PY%" "%ROOT%\tools\citycheck.py" --quiet

echo == docs\command_tree.txt rebuilt (commit it if git shows a change)
"%PY%" "%ROOT%\tools\gen_docs.py" || set FAIL=1

echo.
if "%FAIL%"=="1" (echo SOMETHING FAILED - see above) else (echo ALL CHECKS PASSED)
exit /b %FAIL%
