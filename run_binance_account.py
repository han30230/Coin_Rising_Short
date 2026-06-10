"""
계정별 Binance 봇 실행 (동시에 여러 터미널에서 각각 실행).

사용법:
  python run_binance_account.py sh
  python run_binance_account.py jk
  python run_binance_account.py jk2

.env 에 BINANCE_API_KEY_SH (또는 BINANCE_API_KEY), BINANCE_API_KEY_JK, BINANCE_API_KEY_JK_2 등이 있어야 합니다.
계정마다 state/<계정>/, logs/<계정>/ 파일이 분리됩니다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _resolve_credentials(account: str) -> tuple[str, str, str]:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    acc = account.strip().lower()
    alias = {"jk2": "JK_2", "jk_2": "JK_2"}
    acc_key = alias.get(acc, acc.upper())

    if acc_key in ("SH", "JK", "JK_2"):
        key = os.getenv(f"BINANCE_API_KEY_{acc_key}")
        secret = os.getenv(f"BINANCE_SECRET_{acc_key}")
        label = "jk2" if acc_key == "JK_2" else acc_key.lower()
        if acc_key == "SH" and (not key or not secret):
            key = os.getenv("BINANCE_API_KEY") or key
            secret = os.getenv("BINANCE_SECRET") or secret
    else:
        key = os.getenv("BINANCE_API_KEY") or os.getenv("BINANCE_API_KEY_SH")
        secret = os.getenv("BINANCE_SECRET") or os.getenv("BINANCE_SECRET_SH")
        label = acc or "default"

    if not key or not secret:
        raise SystemExit(
            f"❌ .env에 BINANCE_API_KEY_{acc_key} / BINANCE_SECRET_{acc_key} (또는 BINANCE_API_KEY) 가 없습니다."
        )
    return key, secret, label


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python run_binance_account.py <sh|jk|jk2>")
        print("  예: python run_binance_account.py sh")
        print("  예: python run_binance_account.py jk")
        raise SystemExit(1)

    api_key, api_secret, label = _resolve_credentials(sys.argv[1])

    state_dir = ROOT / "state" / label
    log_dir = ROOT / "logs" / label
    state_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    os.environ["BOT_API_KEY"] = api_key
    os.environ["BOT_API_SECRET"] = api_secret
    os.environ["BOT_ACCOUNT"] = label
    os.environ["POSITION_STATE_FILE"] = str(state_dir / "position_state.json")
    os.environ["SUPERTREND_WATCH_STATE_FILE"] = str(state_dir / "supertrend_watch.json")
    os.environ["TRADE_JOURNAL_FILE"] = str(log_dir / "trade_journal.csv")
    os.environ["BOT_LOG_FILE"] = str(log_dir / "bot.log")

    from coin_rising_short.main import run

    print(f"[{label}] Binance 봇 시작 (state={state_dir.name}, logs={log_dir.name})")
    run()


if __name__ == "__main__":
    main()
