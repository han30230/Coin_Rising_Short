import time
from decimal import Decimal
from typing import Any, Dict, List

from coin_rising_short import client, config, orders, state, symbols


def get_futures_top_gainers() -> List[Dict[str, Any]]:
    url = f"{config.BASE_URL_FUTURES}/fapi/v1/ticker/24hr"
    data = client._http_get(url, timeout=10).json()

    result: List[Dict[str, Any]] = []
    for t in data:
        symbol = t.get("symbol")
        if symbol not in symbols.TRADING_SYMBOLS:
            continue
        try:
            change_pct = Decimal(t["priceChangePercent"])
            turnover_24h = Decimal(t["quoteVolume"])
            last_price = Decimal(t["lastPrice"])

            if change_pct >= config.GAINER_THRESHOLD_PCT and turnover_24h >= config.MIN_VOLUME_USDT:
                result.append(
                    {
                        "symbol": symbol,
                        "change_pct": float(change_pct),
                        "last_price": float(last_price),
                    }
                )
        except Exception:
            continue

    result.sort(key=lambda x: x["change_pct"], reverse=True)
    return result


def check_filled_and_place_tp() -> None:
    dirty = False
    for symbol, st in state.position_state.items():
        entries = st.get("entries", [])
        for entry in entries:
            if entry.get("tp_done"):
                continue

            order_id = entry["order_id"]
            direction = entry["direction"]
            entry_price = entry["entry_price"]
            qty = entry["qty"]

            status = orders.get_order_status(symbol, order_id)
            if status is None:
                continue

            if status == "FILLED":
                print(
                    f"✅ 진입 체결 확인: {symbol} {direction} (orderId={order_id}) → TP 주문 생성 시도"
                )
                tp_oid = orders.place_take_profit_order(symbol, direction, entry_price, qty)
                if tp_oid is not None:
                    entry["tp_order_id"] = tp_oid
                    entry["tp_done"] = True
                else:
                    entry["tp_done"] = False
                dirty = True
            elif status == "PARTIALLY_FILLED":
                d = orders.get_order_detail(symbol, order_id)
                if d:
                    ex = Decimal(str(d.get("executedQty", "0")))
                    ap = Decimal(str(d.get("avgPrice", "0")))
                    if ex > 0:
                        entry["qty"] = ex
                    if ap > 0:
                        entry["entry_price"] = ap
                    dirty = True
            elif status in ("CANCELED", "REJECTED", "EXPIRED"):
                print(
                    f"⚠️ 진입 주문 종료 상태({status}): {symbol} (orderId={order_id}) → TP 생성 스킵"
                )
                entry["tp_done"] = True
                dirty = True
    if dirty:
        state.save_position_state()


def monitor_loop() -> None:
    print("🚀 Binance 선물 급등 종목 감시 시작 (스팟+선물 공존 필터 적용)...")
    while True:
        try:
            gainers = get_futures_top_gainers()
            now_str = time.strftime("%H:%M:%S")

            print("\n" + "─" * 20 + f" [{now_str}] 감시 중 " + "─" * 20)
            if not gainers:
                print("⏳ 조건에 맞는 종목 없음")
            else:
                for i, g in enumerate(gainers[:10], start=1):
                    symbol = g["symbol"]
                    current_price = Decimal(str(g["last_price"]))
                    change_pct = Decimal(str(g["change_pct"]))

                    print(f"{i}. {symbol} | price: {current_price:.4f} | change: {change_pct:.2f}%")

                    if symbol not in state.position_state:
                        entry = orders.place_short_order(symbol)
                        if entry is not None:
                            entry_price, qty, order_id = entry
                            state.position_state[symbol] = {
                                "entry_price": entry_price,
                                "reentered": False,
                                "entries": [
                                    {
                                        "direction": "SHORT",
                                        "entry_price": entry_price,
                                        "qty": qty,
                                        "order_id": order_id,
                                        "tp_done": False,
                                        "tp_order_id": None,
                                    }
                                ],
                            }
                            print(
                                f"📝 {symbol} 첫 진입 기록: entry_price={entry_price}, orderId={order_id}, qty={qty}"
                            )
                            state.save_position_state()
                        continue

                    st = state.position_state[symbol]
                    if not st.get("reentered"):
                        target_price = st["entry_price"] * (
                            Decimal("1") + config.REENTRY_RISE_PCT / Decimal("100")
                        )
                        if current_price >= target_price:
                            print(
                                f"🚨 {symbol} 첫 진입가 대비 +{config.REENTRY_RISE_PCT}% 이상! 추가 숏 재진입 시도..."
                            )
                            short_entry = orders.place_short_order(symbol)
                            if short_entry:
                                se_price, se_qty, se_id = short_entry
                                st.setdefault("entries", []).append(
                                    {
                                        "direction": "SHORT",
                                        "entry_price": se_price,
                                        "qty": se_qty,
                                        "order_id": se_id,
                                        "tp_done": False,
                                        "tp_order_id": None,
                                    }
                                )
                                st["reentered"] = True
                                print(
                                    f"📝 {symbol} 재진입 숏 기록: price={se_price}, orderId={se_id}, qty={se_qty}"
                                )
                                state.save_position_state()

            check_filled_and_place_tp()

        except KeyboardInterrupt:
            print("\n🛑 사용자 중단 (Ctrl+C). 종료.")
            break
        except Exception as e:
            print(f"🔥 루프 오류: {e}")
        time.sleep(config.POLL_INTERVAL_SEC)
