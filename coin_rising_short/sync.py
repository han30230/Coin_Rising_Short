import logging
from decimal import Decimal
from typing import List

from coin_rising_short import client, config, orders, state

logger = logging.getLogger(__name__)


def sync_state_with_exchange() -> None:
    state.load_position_state()
    if not state.position_state:
        logger.info(
            "저장된 상태 없음 (%s)",
            config.POSITION_STATE_PATH,
            extra={"event": "state_empty"},
        )
        return

    logger.info("거래소와 상태 동기화 중...", extra={"event": "sync_started"})
    r = client.signed_request("GET", "/fapi/v1/openOrders", {})
    if r.status_code != 200:
        logger.warning("openOrders 조회 실패: %s %s", r.status_code, r.text)
        orders_list: List[dict] = []
    else:
        raw = client.parse_json_response(r, "openOrders 조회")
        orders_list = raw if isinstance(raw, list) else []

    open_map = {(o["symbol"], int(o["orderId"])): o for o in orders_list}

    remove_symbols: List[str] = []
    dirty = False
    for symbol, st in list(state.position_state.items()):
        st.setdefault("reentry_count", 0)
        st.setdefault("last_reentry_price", st.get("entry_price", Decimal("0")))
        st.setdefault("tp_order_id", None)
        st.setdefault("tp_entry_price", Decimal("0"))
        st.setdefault("tp_qty", Decimal("0"))
        st.setdefault("tp_exit_logged", False)
        for entry in st.get("entries", []):
            entry.setdefault("filled", False)
            entry.setdefault("closed", False)
            entry.setdefault("entry_logged", False)
            oid = int(entry["order_id"])
            key = (symbol, oid)
            if key in open_map:
                o = open_map[key]
                st_ord = o.get("status", "")
                if st_ord == "PARTIALLY_FILLED":
                    ex = Decimal(str(o.get("executedQty", "0")))
                    if ex > 0:
                        entry["qty"] = ex
                        dirty = True
                entry["filled"] = False
                entry["closed"] = False
                continue

            detail = orders.get_order_detail(symbol, oid)
            if not detail:
                logger.warning("주문 상세 없음(스킵): %s orderId=%s", symbol, oid)
                continue
            st_detail = detail.get("status")
            if st_detail == "FILLED":
                ap = Decimal(str(detail.get("avgPrice", "0")))
                eq = Decimal(str(detail.get("executedQty", "0")))
                if ap > 0:
                    entry["entry_price"] = ap
                if eq > 0:
                    entry["qty"] = eq
                entry["filled"] = True
                entry["closed"] = False
                dirty = True
            elif st_detail in ("CANCELED", "REJECTED", "EXPIRED", "NEW"):
                entry["filled"] = False
                entry["closed"] = True
                dirty = True
            elif st_detail == "PARTIALLY_FILLED":
                ex = Decimal(str(detail.get("executedQty", "0")))
                if ex > 0:
                    entry["qty"] = ex
                    dirty = True

        tp_oid = st.get("tp_order_id")
        if tp_oid:
            tp_detail = orders.get_order_detail(symbol, int(tp_oid))
            if tp_detail:
                tp_status = tp_detail.get("status")
                if tp_status == "FILLED":
                    st["tp_exit_logged"] = True
                    for entry in st.get("entries", []):
                        if entry.get("filled"):
                            entry["filled"] = False
                            entry["closed"] = True
                    remove_symbols.append(symbol)
                    dirty = True
                elif tp_status in ("CANCELED", "REJECTED", "EXPIRED"):
                    st["tp_order_id"] = None
                    dirty = True

    rp = client.signed_request("GET", "/fapi/v1/positionRisk", {})
    if rp.status_code == 200:
        positions = client.parse_json_response(rp, "positionRisk 조회")
        if not isinstance(positions, list):
            positions = []
        for p in positions:
            amt = Decimal(str(p.get("positionAmt", "0")))
            if amt != 0:
                sym = p.get("symbol")
                logger.info("거래소 포지션: %s positionAmt=%s", sym, amt)

    for symbol in remove_symbols:
        state.position_state.pop(symbol, None)
        dirty = True
        logger.info(
            "동기화 중 종료 심볼 상태 정리: %s",
            symbol,
            extra={"event": "sync_symbol_state_cleared", "symbol": symbol},
        )

    if dirty:
        state.save_position_state()
    logger.info(
        "동기화 완료, 추적 중 심볼 %s개 -> %s",
        len(state.position_state),
        config.POSITION_STATE_PATH,
        extra={"event": "sync_completed", "tracked_symbols": len(state.position_state)},
    )
