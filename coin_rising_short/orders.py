from decimal import Decimal
from typing import Optional, Tuple

from coin_rising_short import client, config, filters, runtime

_leverage_ready: set = set()


def ensure_leverage(symbol: str) -> bool:
    global _leverage_ready
    if symbol in _leverage_ready:
        return True
    r = client.signed_request(
        "POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": config.LEVERAGE}
    )
    if r.status_code == 200:
        _leverage_ready.add(symbol)
        print(f"⚙️ {symbol} 레버리지 {config.LEVERAGE}x 설정")
        return True
    print(f"⚠️ 레버리지 설정 실패 {symbol}: {r.status_code} {r.text}")
    return False


def get_dual_side_position() -> bool:
    r = client.signed_request("GET", "/fapi/v1/positionSide/dual", {})
    try:
        data = r.json()
        return bool(data.get("dualSidePosition"))
    except Exception:
        print("⚠️ 포지션 모드 조회 실패:", r.status_code, r.text)
        return False


def set_dual_side_position(enable: bool) -> bool:
    r = client.signed_request(
        "POST",
        "/fapi/v1/positionSide/dual",
        {"dualSidePosition": "true" if enable else "false"},
    )
    ok = r.status_code == 200
    print(f"set_dual_side_position({enable}) ->", r.status_code, r.text)
    return ok


def get_order_status(symbol: str, order_id: int) -> Optional[str]:
    try:
        r = client.signed_request(
            "GET", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}
        )
        data = r.json()
        if r.status_code == 200 and "status" in data:
            return data["status"]
        print(f"⚠️ 주문 조회 실패({r.status_code}): {symbol} / {data}")
        return None
    except Exception as e:
        print(f"🔥 주문 조회 예외 발생: {e}")
        return None


def get_order_detail(symbol: str, order_id: int) -> Optional[dict]:
    try:
        r = client.signed_request(
            "GET", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}
        )
        if r.status_code == 200:
            return r.json()
        print(f"⚠️ 주문 상세 조회 실패({r.status_code}): {symbol} / {r.text}")
        return None
    except Exception as e:
        print(f"🔥 주문 상세 조회 예외: {e}")
        return None


def place_limit_order(
    symbol: str, side: str, price: Decimal, qty: Decimal, position_side: Optional[str]
) -> Tuple[Optional[int], Optional[dict]]:
    try:
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": str(qty),
            "price": str(price),
        }
        if position_side:
            params["positionSide"] = position_side

        r = client.signed_request("POST", "/fapi/v1/order", params)
        try:
            data = r.json() if r.text else {}
        except Exception:
            data = {}
        if r.status_code == 200 and isinstance(data, dict) and "orderId" in data:
            order_id = int(data["orderId"])
            print(
                f"✅ {side} 주문 성공: {symbol} @ {price} (positionSide={position_side}, orderId={order_id})"
            )
            return order_id, None
        err = data if isinstance(data, dict) else {"msg": r.text}
        print(f"❌ 주문 실패({r.status_code}): {symbol} / {err}")
        return None, err
    except Exception as e:
        print(f"🔥 주문 예외 발생: {e}")
        return None, None


def place_take_profit_order(
    symbol: str, direction: str, entry_price: Decimal, qty: Decimal
) -> Optional[int]:
    try:
        price_step, qty_step, min_qty, min_notional = filters.get_price_step_and_qty_step(symbol)

        if direction.upper() == "SHORT":
            raw_tp_price = entry_price * (Decimal("1") - config.TAKE_PROFIT_PCT / Decimal("100"))
            side = "BUY"
            pos_side = "SHORT" if runtime.IS_HEDGE else None
        else:
            raw_tp_price = entry_price * (Decimal("1") + config.TAKE_PROFIT_PCT / Decimal("100"))
            side = "SELL"
            pos_side = "LONG" if runtime.IS_HEDGE else None

        tp_price = filters.round_step_floor(raw_tp_price, price_step)
        eff_qty = filters.round_step_floor(qty, qty_step)

        if eff_qty < min_qty:
            print(f"❌ TP 최소 수량 미달: {eff_qty} < {min_qty}")
            return None

        if min_notional > 0 and tp_price * eff_qty < min_notional:
            eff_qty = filters.adjust_qty_for_min_notional(
                tp_price, eff_qty, qty_step, min_qty, min_notional
            )
            if eff_qty is None or eff_qty > qty:
                print(f"❌ TP MIN_NOTIONAL 불가: tp={tp_price} qty={qty}")
                return None

        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": str(eff_qty),
            "price": str(tp_price),
        }

        if pos_side:
            params["positionSide"] = pos_side

        if not runtime.IS_HEDGE:
            params["reduceOnly"] = "true"

        r = client.signed_request("POST", "/fapi/v1/order", params)
        try:
            data = r.json() if r.text else {}
        except Exception:
            data = {}
        if r.status_code == 200 and isinstance(data, dict) and "orderId" in data:
            oid = int(data["orderId"])
            print(
                f"🎯 TP 주문 성공: {symbol} {direction} 익절 @ {tp_price} (qty={eff_qty}, tpOrderId={oid})"
            )
            return oid
        print(f"❌ TP 주문 실패({r.status_code}): {symbol} / {data}")
        return None
    except Exception as e:
        print(f"🔥 TP 주문 예외 발생: {e}")
        return None


def place_short_order(
    symbol: str, notional_usdt: Optional[Decimal] = None
) -> Optional[Tuple[Decimal, Decimal, int]]:
    print(f"🧾 숏 주문 시도: {symbol}")
    try:
        ensure_leverage(symbol)
        resp = client._http_get(
            f"{config.BASE_URL_FUTURES}/fapi/v1/ticker/price",
            params={"symbol": symbol},
            timeout=10,
        ).json()
        price = Decimal(resp["price"])
        price_step, qty_step, min_qty, min_notional = filters.get_price_step_and_qty_step(symbol)

        raw_price = price * (Decimal("1") + config.PREMIUM_PCT)
        limit_price = filters.round_step_floor(raw_price, price_step)

        target_notional = notional_usdt if notional_usdt is not None else config.POSITION_USDT

        for attempt in range(10):
            qty = filters.round_step_floor(target_notional / limit_price, qty_step)
            adj = filters.adjust_qty_for_min_notional(
                limit_price, qty, qty_step, min_qty, min_notional
            )
            if adj is None:
                print(f"❌ MIN_NOTIONAL 충족 불가: {symbol}")
                return None
            qty = adj

            pos_side = "SHORT" if runtime.IS_HEDGE else None
            order_id, err = place_limit_order(symbol, "SELL", limit_price, qty, pos_side)
            if order_id is not None:
                return limit_price, qty, order_id

            if err and err.get("code") == -2027:
                print(
                    f"⚠️ {symbol} 포지션 한도 초과(-2027), 명목 {target_notional} USDT → 50% 축소 후 재시도 "
                    f"({attempt + 1}/10)"
                )
                target_notional = target_notional / Decimal("2")
                q_try = filters.round_step_floor(target_notional / limit_price, qty_step)
                if q_try < min_qty:
                    print(f"❌ 명목 축소 후 최소 수량 미만: {symbol}")
                    return None
                continue
            return None

        print(f"❌ {symbol} 숏 주문 -2027 재시도 한도 초과")
        return None
    except Exception as e:
        print(f"🔥 숏 주문 예외 발생: {e}")
        return None


def place_long_order(
    symbol: str, notional_usdt: Optional[Decimal] = None
) -> Optional[Tuple[Decimal, Decimal, int]]:
    print(f"🧾 롱 주문 시도: {symbol}")
    try:
        ensure_leverage(symbol)
        resp = client._http_get(
            f"{config.BASE_URL_FUTURES}/fapi/v1/ticker/price",
            params={"symbol": symbol},
            timeout=10,
        ).json()
        price = Decimal(resp["price"])
        price_step, qty_step, min_qty, min_notional = filters.get_price_step_and_qty_step(symbol)

        raw_price = price * (Decimal("1") - config.DISCOUNT_PCT)
        limit_price = filters.round_step_floor(raw_price, price_step)

        target_notional = notional_usdt if notional_usdt is not None else config.POSITION_USDT

        for attempt in range(10):
            qty = filters.round_step_floor(target_notional / limit_price, qty_step)
            adj = filters.adjust_qty_for_min_notional(
                limit_price, qty, qty_step, min_qty, min_notional
            )
            if adj is None:
                print(f"❌ MIN_NOTIONAL 충족 불가: {symbol}")
                return None
            qty = adj

            pos_side = "LONG" if runtime.IS_HEDGE else None
            order_id, err = place_limit_order(symbol, "BUY", limit_price, qty, pos_side)
            if order_id is not None:
                return limit_price, qty, order_id

            if err and err.get("code") == -2027:
                print(
                    f"⚠️ {symbol} 포지션 한도 초과(-2027), 명목 {target_notional} USDT → 50% 축소 "
                    f"({attempt + 1}/10)"
                )
                target_notional = target_notional / Decimal("2")
                q_try = filters.round_step_floor(target_notional / limit_price, qty_step)
                if q_try < min_qty:
                    print(f"❌ 명목 축소 후 최소 수량 미만: {symbol}")
                    return None
                continue
            return None

        print(f"❌ {symbol} 롱 주문 -2027 재시도 한도 초과")
        return None
    except Exception as e:
        print(f"🔥 롱 주문 예외 발생: {e}")
        return None
