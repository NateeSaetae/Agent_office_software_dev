@echo off
cd /d "%~dp0"
echo This prepares Codex's elevated Windows sandbox for this app.
echo Windows may request administrator approval for sandbox provisioning.
echo Close this window to cancel.
pause
if exist ".python-deps\codex_cli_bin\bin\codex.exe" (
  ".python-deps\codex_cli_bin\bin\codex.exe" sandbox setup --elevated --user "%USERDOMAIN%\%USERNAME%" --codex-home "%~dp0.data\codex-home"
) else if exist ".venv\Lib\site-packages\codex_cli_bin\bin\codex.exe" (
  ".venv\Lib\site-packages\codex_cli_bin\bin\codex.exe" sandbox setup --elevated --user "%USERDOMAIN%\%USERNAME%" --codex-home "%~dp0.data\codex-home"
) else (
  codex sandbox setup --elevated --user "%USERDOMAIN%\%USERNAME%" --codex-home "%~dp0.data\codex-home"
)
pause
