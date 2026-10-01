@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Создаю виртуальное окружение...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Не удалось создать .venv. Проверьте, что Python установлен и команда py доступна.
    pause
    exit /b 1
  )
  echo Устанавливаю зависимости...
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Не удалось установить зависимости.
    pause
    exit /b 1
  )
)
"%PY%" app.py
pause
