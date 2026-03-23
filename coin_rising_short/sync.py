from decimal import Decimal
from typing import List

from coin_rising_short import client, config, orders, state


def sync_state_with_exchange() -> None:
    state.load_position_state()
    if not state.position_state:
        print(f"📂 저장된 상태 없음 ({config.POSITION_STATE_PATH})")
        return

    print("🔄 거래소와 상태 동기화 중...")
    r = client.signed_request("GET", "/fapi/v1/openOrders", {})
    if r.status_code != 200:
        print(f"⚠️ openOrders 조회 실패: {r.status_code} {r.text}")
        orders_list: List[dict] = []
    else:
        raw = r.json()
        orders_list = raw if isinstance(raw, list) else []

    open_map = {(o["symbol"], int(o["orderId"])): o for o in orders_list}

    for symbol, st in list(state.position_state.items()):
        for entry in st.get("entries", []):
            oid = int(entry["order_id"])
            key = (symbol, oid)
            if key in open_map:
                o = open_map[key]
                st_ord = o.get("status", "")
                if st_ord == "PARTIALLY_FILLED":
                    ex = Decimal(str(o.get("executedQty", "0")))
                    if ex > 0:
                        entry["qty"] = ex
                continue

            detail = orders.get_order_detail(symbol, oid)
            if not detail:
                print(f"⚠️ 주문 상세 없음(스킵): {symbol} orderId={oid}")
                continue
            st_detail = detail.get("status")
            if st_detail == "FILLED":
                ap = Decimal(str(detail.get("avgPrice", "0")))
                eq = Decimal(str(detail.get("executedQty", "0")))
                if ap > 0:
                    entry["entry_price"] = ap
                if eq > 0:
                    entry["qty"] = eq
            elif st_detail in ("CANCELED", "REJECTED", "EXPIRED"):
                entry["tp_done"] = True
            elif st_detail == "PARTIALLY_FILLED":
                ex = Decimal(str(detail.get("executedQty", "0")))
                if ex > 0:
                    entry["qty"] = ex

    rp = client.signed_request("GET", "/fapi/v1/positionRisk", {})
    if rp.status_code == 200:
        for p in rp.json():
            amt = Decimal(str(p.get("positionAmt", "0")))
            if amt != 0:
                sym = p.get("symbol")
                print(f"📊 거래소 포지션: {sym} positionAmt={amt}")

    state.save_position_state()
    print(
        f"✅ 동기화 완료, 추적 중 심볼 {len(state.position_state)}개 → {config.POSITION_STATE_PATH}"
    )
