@echo off
chcp 65001 >nul
echo ============================================================
echo Playwright-Omni 环境修复脚本
echo ============================================================
echo.

set VENV_PY=D:\OpenClaw\venv\Scripts\python.exe
set SAFE_PIP=D:\OpenClaw\tools\safe-pip.bat

echo [1/5] 安装 openai...
call %SAFE_PIP% install openai
echo.

echo [2/5] 安装 torch (CPU 版本，节省空间)...
call %SAFE_PIP% install torch --index-url https://download.pytorch.org/whl/cpu
echo.

echo [3/5] 安装 transformers + huggingface_hub...
call %SAFE_PIP% install transformers huggingface_hub
echo.

echo [4/5] 安装 PIL / Pillow...
call %SAFE_PIP% install pillow
echo.

echo [5/5] 安装 ultralytics (YOLO)...
call %SAFE_PIP% install ultralytics
echo.

echo ============================================================
echo 安装完成。运行诊断：
echo   D:\OpenClaw\venv\Scripts\python.exe -X utf8 D:\OpenClaw\workspace\skills\playwright-omni\scripts\env_diag.py
echo.
echo 然后运行预检：
echo   D:\OpenClaw\venv\Scripts\python.exe -X utf8 D:\OpenClaw\workspace\skills\playwright-omni\scripts\preflight_check.py
echo ============================================================
pause
