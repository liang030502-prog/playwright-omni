@echo off
REM run.bat — Playwright-Omni 快速启动器
REM 用法: run.bat "https://github.com/login" "登录 GitHub，用户名 myuser，密码 mypass"
REM
REM 参数说明:
REM   %1 = 目标 URL
REM   %2 = 任务目标
REM   %3 = 最大步数（可选，默认 20）
REM   %4 = 有头模式（可选，0=无头，1=有头，默认 1）
REM
REM 示例:
REM   run.bat "https://github.com/login" "登录 GitHub，用户名 myuser，密码 mypass"
REM   run.bat "https://example.com" "填表" 30 1

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PYTHON=%USERPROFILE%\miniconda3\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo ========================================================
echo  Playwright-Omni Launcher
echo ========================================================
echo.

if "%~1"=="" (
    echo 用法:
    echo   run.bat "https://github.com/login" "登录 GitHub"
    echo   run.bat "https://example.com" "填表" 30 1
    echo.
    echo 参数:
    echo   %%1 = 目标 URL
    echo   %%2 = 任务目标
    echo   %%3 = 最大步数^(可选，默认 20^)
    echo   %%4 = 有头模式^(可选，0=无头，1=有头，默认 1^)
    exit /b 1
)

set "URL=%~1"
set "GOAL=%~2"
set "MAX_STEPS=%~3"
if "%MAX_STEPS%"=="" set "MAX_STEPS=20"
set "HEADFUL=%~4"
if "%HEADFUL%"=="" set "HEADFUL=1"

set "HEADLESS_FLAG="
if "%HEADFUL%"=="0" set "HEADLESS_FLAG=--headless"

echo  URL:        %URL%
echo  Goal:       %GOAL%
echo  Max steps:  %MAX_STEPS%
echo  Headless:   %HEADFUL%
echo.

cd /d "%SCRIPT_DIR%scripts"
"%PYTHON%" -X utf8 cli.py --url "%URL%" --goal "%GOAL%" --max-steps %MAX_STEPS% %HEADLESS_FLAG% --verbose

endlocal
