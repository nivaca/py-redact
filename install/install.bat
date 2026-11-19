@echo off
rem Installs py-redact for this user on Windows, to run with Python 3.14 or
rem later: runs install.ps1 (see there, or install.bat -Help). It can also be
rem started with a double click.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
set status=%errorlevel%
rem (a double click opens a window of its own, which would close at once)
echo %cmdcmdline% | find /i "%~0" >nul && pause
exit /b %status%
