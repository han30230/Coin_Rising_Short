from typing import Dict

from coin_rising_short import client, config


def get_trading_symbols() -> Dict[str, dict]:
    """선물(TRADING & PERPETUAL) 중 스팟에도 존재하는 심볼만."""
    print("🔍 심볼 정보 로딩 중...")

    fut_data = client._http_get(f"{config.BASE_URL_FUTURES}/fapi/v1/exchangeInfo", timeout=10).json()
    futures_symbols = {
        s["symbol"]: s
        for s in fut_data["symbols"]
        if (
            s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
            and s.get("contractType") == "PERPETUAL"
        )
    }

    spot_data = client._http_get(f"{config.BASE_URL_SPOT}/api/v3/exchangeInfo", timeout=10).json()
    spot_symbols = {
        s["symbol"] for s in spot_data["symbols"] if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
    }

    both = {k: v for k, v in futures_symbols.items() if k in spot_symbols}
    print(f"✅ 거래 가능 (선물+스팟 공존) 심볼: {len(both)}개")
    return both


TRADING_SYMBOLS = get_trading_symbols()
