import logging
import time
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from coin_rising_short import config
from coin_rising_short.market_cap import normalize_binance_symbol

logger = logging.getLogger(__name__)

_COINGECKO_TIMEOUT_SEC = 15
_COINGECKO_CACHE_TTL_SEC = 30 * 60
_COINGECKO_IDS_CHUNK = 100

_coin_list_cache: Optional[Tuple[float, List[Dict[str, Any]]]] = None
_mcap_fdv_map_cache: Dict[Tuple[str, ...], Tuple[float, Dict[str, Dict[str, Decimal]]]] = {}


def clear_coingecko_cache_for_tests() -> None:
    global _coin_list_cache
    _coin_list_cache = None
    _mcap_fdv_map_cache.clear()


def _fetch_coin_list() -> List[Dict[str, Any]]:
    global _coin_list_cache
    now = time.time()
    if _coin_list_cache is not None and now - _coin_list_cache[0] < _COINGECKO_CACHE_TTL_SEC:
        return _coin_list_cache[1]

    url = f"{config.COINGECKO_API_BASE.rstrip('/')}/coins/list"
    try:
        resp = requests.get(url, params={"include_platform": "false"}, timeout=_COINGECKO_TIMEOUT_SEC)
    except requests.RequestException as exc:
        logger.warning(
            "CoinGecko coins/list 요청 실패: %s",
            exc,
            extra={"event": "coingecko_coin_list_error"},
        )
        return []

    if resp.status_code >= 400:
        logger.warning(
            "CoinGecko coins/list HTTP %s: %s",
            resp.status_code,
            (resp.text or "")[:200],
            extra={"event": "coingecko_coin_list_http_error"},
        )
        return []

    try:
        data = resp.json()
    except Exception as exc:
        logger.warning(
            "CoinGecko coins/list JSON 파싱 실패: %s",
            exc,
            extra={"event": "coingecko_coin_list_json_error"},
        )
        return []

    if not isinstance(data, list):
        logger.warning(
            "CoinGecko coins/list 응답 형식 오류: %s",
            type(data),
            extra={"event": "coingecko_coin_list_bad_type"},
        )
        return []

    _coin_list_cache = (now, data)
    return data


def _fetch_markets_for_ids(coin_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    base = config.COINGECKO_API_BASE.rstrip("/")
    for i in range(0, len(coin_ids), _COINGECKO_IDS_CHUNK):
        chunk = coin_ids[i : i + _COINGECKO_IDS_CHUNK]
        ids_param = ",".join(chunk)
        url = f"{base}/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ids_param,
            "order": "market_cap_desc",
            "per_page": str(len(chunk)),
            "page": "1",
            "sparkline": "false",
        }
        try:
            resp = requests.get(url, params=params, timeout=_COINGECKO_TIMEOUT_SEC)
        except requests.RequestException as exc:
            logger.warning(
                "CoinGecko coins/markets 요청 실패: %s",
                exc,
                extra={"event": "coingecko_markets_error"},
            )
            return {}

        if resp.status_code >= 400:
            logger.warning(
                "CoinGecko coins/markets HTTP %s: %s",
                resp.status_code,
                (resp.text or "")[:200],
                extra={"event": "coingecko_markets_http_error"},
            )
            return {}

        try:
            rows = resp.json()
        except Exception as exc:
            logger.warning(
                "CoinGecko coins/markets JSON 파싱 실패: %s",
                exc,
                extra={"event": "coingecko_markets_json_error"},
            )
            return {}

        if not isinstance(rows, list):
            logger.warning(
                "CoinGecko coins/markets 응답 형식 오류: %s",
                type(rows),
                extra={"event": "coingecko_markets_bad_type"},
            )
            return {}

        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = row.get("id")
            if isinstance(cid, str) and cid:
                out[cid] = row

    return out


def _candidate_ids_for_base(coin_list: List[Dict[str, Any]], base: str) -> List[str]:
    b = base.upper()
    ids: List[str] = []
    for entry in coin_list:
        if not isinstance(entry, dict):
            continue
        sym = entry.get("symbol")
        cid = entry.get("id")
        if not isinstance(sym, str) or not isinstance(cid, str):
            continue
        if sym.upper() == b:
            ids.append(cid)
    return ids


def _pick_best_id_for_base(
    candidate_ids: List[str],
    id_to_row: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    best_id: Optional[str] = None
    best_mcap: Optional[Decimal] = None
    for cid in candidate_ids:
        row = id_to_row.get(cid)
        if not row:
            continue
        m = row.get("market_cap")
        if m is None:
            continue
        try:
            m_d = Decimal(str(m))
        except Exception:
            continue
        if best_mcap is None or m_d > best_mcap:
            best_mcap = m_d
            best_id = cid
    return best_id


def get_mcap_fdv_map(symbols: Iterable[str]) -> Dict[str, Dict[str, Decimal]]:
    """
    Binance 선물 심볼(예: BTCUSDT) -> CoinGecko market_cap, FDV, mcap/fdv ratio.
    조회 실패 시 빈 dict.
    """
    sym_list = sorted({str(s) for s in symbols if s})
    if not sym_list:
        return {}

    now = time.time()
    cache_key = tuple(sym_list)
    cached = _mcap_fdv_map_cache.get(cache_key)
    if cached is not None and now - cached[0] < _COINGECKO_CACHE_TTL_SEC:
        return dict(cached[1])

    coin_list = _fetch_coin_list()
    if not coin_list:
        logger.warning(
            "CoinGecko coin list 없음, mcap/fdv 맵 빈 결과",
            extra={"event": "coingecko_mcap_fdv_map_empty_list"},
        )
        return {}

    bases = {normalize_binance_symbol(s) for s in sym_list}
    base_to_candidates: Dict[str, List[str]] = {}
    all_candidate_ids: List[str] = []
    seen: set[str] = set()
    for base in bases:
        cands = _candidate_ids_for_base(coin_list, base)
        base_to_candidates[base] = cands
        for cid in cands:
            if cid not in seen:
                seen.add(cid)
                all_candidate_ids.append(cid)

    if not all_candidate_ids:
        logger.warning(
            "CoinGecko 후보 id 없음: bases=%s",
            sorted(bases),
            extra={"event": "coingecko_no_candidate_ids"},
        )
        return {}

    id_to_row = _fetch_markets_for_ids(all_candidate_ids)
    if not id_to_row:
        logger.warning(
            "CoinGecko markets 응답 없음, mcap/fdv 맵 빈 결과",
            extra={"event": "coingecko_markets_empty"},
        )
        return {}

    result: Dict[str, Dict[str, Decimal]] = {}
    for fut_sym in sym_list:
        base = normalize_binance_symbol(fut_sym)
        cands = base_to_candidates.get(base) or []
        best_id = _pick_best_id_for_base(cands, id_to_row)
        if not best_id:
            continue
        row = id_to_row[best_id]
        try:
            mcap = row.get("market_cap")
            fdv = row.get("fully_diluted_valuation")
            if mcap is None or fdv is None:
                continue
            mcap_d = Decimal(str(mcap))
            fdv_d = Decimal(str(fdv))
        except Exception:
            continue
        if fdv_d <= 0:
            continue
        ratio = mcap_d / fdv_d
        result[fut_sym] = {
            "market_cap": mcap_d,
            "fully_diluted_valuation": fdv_d,
            "mcap_fdv_ratio": ratio,
        }

    _mcap_fdv_map_cache[cache_key] = (now, result)
    return result


def filter_by_mcap_fdv(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not config.FILTER_MCAP_FDV:
        return rows

    if not rows:
        return rows

    symbols = [str(r.get("symbol", "")) for r in rows if r.get("symbol")]
    data = get_mcap_fdv_map(symbols)
    if not data:
        logger.warning(
            "CoinGecko mcap/fdv 데이터 없음, 후보 전부 제외 (%s개)",
            len(rows),
            extra={"event": "coingecko_filter_all_dropped_no_data"},
        )
        return []

    out: List[Dict[str, Any]] = []
    for r in rows:
        sym = r.get("symbol")
        if not isinstance(sym, str):
            continue
        info = data.get(sym)
        if not info:
            logger.info(
                "CoinGecko mcap/fdv 없음으로 제외: symbol=%s",
                sym,
                extra={"event": "coingecko_skip_no_row", "symbol": sym},
            )
            continue
        ratio = info["mcap_fdv_ratio"]
        if ratio < config.MIN_MCAP_FDV_RATIO:
            logger.info(
                "mcap/fdv 미달로 제외: symbol=%s ratio=%s min=%s",
                sym,
                ratio,
                config.MIN_MCAP_FDV_RATIO,
                extra={
                    "event": "coingecko_skip_ratio",
                    "symbol": sym,
                    "mcap_fdv_ratio": str(ratio),
                },
            )
            continue
        r["coingecko_market_cap"] = info["market_cap"]
        r["coingecko_fdv"] = info["fully_diluted_valuation"]
        r["mcap_fdv_ratio"] = ratio
        logger.info(
            "%s | mcap: %s | fdv: %s | ratio: %s",
            sym,
            info["market_cap"],
            info["fully_diluted_valuation"],
            ratio,
            extra={
                "event": "coingecko_mcap_fdv_pass",
                "symbol": sym,
                "mcap": str(info["market_cap"]),
                "fdv": str(info["fully_diluted_valuation"]),
                "ratio": str(ratio),
            },
        )
        out.append(r)

    return out
