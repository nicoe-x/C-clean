@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -c "import tkinter" >nul 2>&1
if errorlevel 1 (
  echo 请安装带有 Tkinter 的 Python 3.10 或更新版本，然后重新启动。
  pause
  exit /b 1
)
py -3 cleaner.py
if errorlevel 1 pause
