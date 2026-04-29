import logging
from typing import Set

from coin_rising_short import client

logger = logging.getLogger(__name__)


def get_upbit_base_assets() -> Set[str]:
    """
    업비트 전체 마켓(KRW/BTC/USDT 등)에서 베이스 자산 심볼 집합을 반환.
    예: "KRW-BTC" -> "BTC"
    """
    url = "https://api.upbit.com/v1/market/all"
    resp = client._http_get(url, params={"isDetails": "false"}, timeout=10)
    data = client.parse_json_response(resp, "upbit market/all")
    if not isinstance(data, list):
        raise RuntimeError(f"업비트 마켓 응답 형식 오류: {type(data)}")

    assets: Set[str] = set()
    for m in data:
        if not isinstance(m, dict):
            continue
        market = m.get("market")
        if not isinstance(market, str):
            continue
        # market format: "KRW-BTC", "BTC-ETH", "USDT-XRP" ...
        parts = market.split("-", 1)
        if len(parts) != 2:
            continue
        base = parts[1].strip().upper()
        if base:
            assets.add(base)

    logger.info("업비트 베이스 자산 로딩 완료: %s개", len(assets))
    return assets

