@echo off
cd /d "%~dp0"
set NATEE_PORT=8010
echo Natee's Software House
echo Open http://127.0.0.1:8010 after the server starts.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py
) else (
  py run.py
)
pause
