import logging
from decimal import Decimal
from typing import Dict

from coin_rising_short import client

logger = logging.getLogger(__name__)


def get_symbol_fundamentals() -> Dict[str, dict]:
    """
    CoinGecko markets 데이터를 심볼(예: BTC) 기준으로 매핑.
    심볼 중복이 있을 수 있어 market_cap이 가장 큰 항목을 우선 채택한다.
    """
    out: Dict[str, dict] = {}
    page = 1
    while True:
        resp = client._http_get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 250,
                "page": page,
                "sparkline": "false",
            },
            timeout=15,
        )
        data = client.parse_json_response(resp, f"coingecko markets page={page}")
        if not isinstance(data, list) or not data:
            break

        for row in data:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol", "")).upper()
            if not symbol:
                continue
            market_cap = row.get("market_cap")
            fdv = row.get("fully_diluted_valuation")
            mcap_d = Decimal(str(market_cap)) if market_cap is not None else Decimal("0")
            fdv_d = Decimal(str(fdv)) if fdv is not None else Decimal("0")
            ratio = Decimal("0")
            if fdv_d > 0:
                ratio = mcap_d / fdv_d

            existing = out.get(symbol)
            if existing is None or mcap_d > existing["market_cap"]:
                out[symbol] = {
                    "market_cap": mcap_d,
                    "fdv": fdv_d,
                    "mcap_fdv_ratio": ratio,
                }
        page += 1
        if page > 12:
            break

    logger.info("CoinGecko 펀더멘털 로딩 완료: %s symbols", len(out))
    return out

