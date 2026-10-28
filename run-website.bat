@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-thiqa.ps1" %*
set "THIQA_EXIT=%ERRORLEVEL%"
if "%THIQA_EXIT%"=="0" goto finish
echo %* | findstr /I /C:"-NonInteractive" >nul
if not errorlevel 1 goto finish
pause
:finish
endlocal & exit /b %THIQA_EXIT%
