import logging
import time
from typing import Dict

from coin_rising_short import client, config, upbit

logger = logging.getLogger(__name__)


def _is_old_enough_futures_symbol(s: dict) -> bool:
    try:
        onboard_ms = int(s.get("onboardDate", 0))
    except Exception:
        return False

    if onboard_ms <= 0:
        return False

    now_ms = int(time.time() * 1000)
    min_age_ms = config.MIN_FUTURES_LISTING_AGE_DAYS * 24 * 60 * 60 * 1000
    return now_ms - onboard_ms >= min_age_ms


def get_trading_symbols() -> Dict[str, dict]:
    """선물(TRADING & PERPETUAL) 중 스팟에도 존재하는 심볼만."""
    logger.info("심볼 정보 로딩 중...")

    fut_resp = client._http_get(f"{config.BASE_URL_FUTURES}/fapi/v1/exchangeInfo", timeout=10)
    fut_data = client.parse_json_response(fut_resp, "futures exchangeInfo")
    if not isinstance(fut_data, dict) or "symbols" not in fut_data:
        raise RuntimeError("선물 exchangeInfo 응답 형식이 올바르지 않습니다.")

    upbit_assets = None
    if config.FILTER_UPBIT_LISTED:
        upbit_assets = upbit.get_upbit_base_assets()
        logger.info("업비트 상장 필터 적용: ON")
    else:
        logger.info("업비트 상장 필터 적용: OFF")

    raw_futures_symbols = [
        s
        for s in fut_data["symbols"]
        if (
            s.get("status") == "TRADING"
            and s.get("quoteAsset") == "USDT"
            and s.get("contractType") == "PERPETUAL"
            and not bool(s.get("closeOnly"))
            and "LIMIT" in (s.get("orderTypes") or [])
            and (
                upbit_assets is None
                or str(s.get("baseAsset", "")).upper() in upbit_assets
            )
        )
    ]

    futures_symbols = {
        s["symbol"]: s
        for s in raw_futures_symbols
        if _is_old_enough_futures_symbol(s)
    }

    logger.info(
        "선물 상장 %s일 이상 필터 적용: %s개 -> %s개",
        config.MIN_FUTURES_LISTING_AGE_DAYS,
        len(raw_futures_symbols),
        len(futures_symbols),
    )

    spot_resp = client._http_get(f"{config.BASE_URL_SPOT}/api/v3/exchangeInfo", timeout=10)
    spot_data = client.parse_json_response(spot_resp, "spot exchangeInfo")
    if not isinstance(spot_data, dict) or "symbols" not in spot_data:
        raise RuntimeError("스팟 exchangeInfo 응답 형식이 올바르지 않습니다.")
    spot_symbols = {
        s["symbol"] for s in spot_data["symbols"] if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT"
    }

    both = {k: v for k, v in futures_symbols.items() if k in spot_symbols}
    logger.info("거래 가능 (선물+스팟 공존) 심볼: %s개", len(both))
    return both


TRADING_SYMBOLS: Dict[str, dict] = {}


def init_trading_symbols(max_retries: int = 3) -> None:
    global TRADING_SYMBOLS
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            TRADING_SYMBOLS = get_trading_symbols()
            if not TRADING_SYMBOLS:
                raise RuntimeError("로딩된 거래 심볼이 없습니다.")
            return
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                wait_sec = min(2**attempt, 8)
                logger.warning(
                    "심볼 로딩 실패 (%s/%s): %s. %ss 후 재시도",
                    attempt,
                    max_retries,
                    exc,
                    wait_sec,
                )
                time.sleep(wait_sec)
            else:
                logger.exception("심볼 로딩 최종 실패")
    raise RuntimeError(f"심볼 초기화 실패: {last_error}")
