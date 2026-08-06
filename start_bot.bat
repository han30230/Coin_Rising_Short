@echo off
REM 사용법: start_bot.bat sh   또는  jk  /  jk2
cd /d "%~dp0"
if "%~1"=="" (
  echo 사용법: start_bot.bat ^<sh^|jk^|jk2^>
  exit /b 1
)
start "Binance %~1" cmd /k python run_binance_account.py %~1
