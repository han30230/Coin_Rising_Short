@echo off
REM Cursor/IDE 종료와 무관하게 별도 창에서 봇 실행 (창을 닫으면 해당 계정만 종료)
cd /d "%~dp0"
start "Binance SH" cmd /k python run_binance_account.py sh
start "Binance JK" cmd /k python run_binance_account.py jk
start "Binance JK2" cmd /k python run_binance_account.py jk2
echo 3개 계정 봇을 별도 창에서 시작했습니다.
