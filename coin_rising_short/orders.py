import logging
import time
from decimal import Decimal
from typing import Optional, Tuple

from coin_rising_short import client, config, filters, runtime

_leverage_ready: set = set()
logger = logging.getLogger(__name__)


def ensure_leverage(symbol: str) -> bool:
    global _leverage_ready
    if symbol in _leverage_ready:
        return True
    r = client.signed_request(
        "POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": config.LEVERAGE}
    )
    if r.status_code == 200:
        _leverage_ready.add(symbol)
        logger.info(
            "%s 레버리지 %sx 설정",
            symbol,
            config.LEVERAGE,
            extra={"event": "leverage_set", "symbol": symbol},
        )
        return True
    logger.warning(
        "레버리지 설정 실패 %s: %s %s",
        symbol,
        r.status_code,
        r.text,
        extra={"event": "leverage_set_failed", "symbol": symbol, "status_code": r.status_code},
    )
    return False


def get_dual_side_position() -> bool:
    r = client.signed_request("GET", "/fapi/v1/positionSide/dual", {})
    try:
        data = client.parse_json_response(r, "positionSide 조회")
        return bool(data.get("dualSidePosition"))
    except Exception:
        logger.warning("포지션 모드 조회 실패: %s %s", r.status_code, r.text)
        return False


def set_dual_side_position(enable: bool) -> bool:
    r = client.signed_request(
        "POST",
        "/fapi/v1/positionSide/dual",
        {"dualSidePosition": "true" if enable else "false"},
    )
    ok = r.status_code == 200
    logger.info("set_dual_side_position(%s) -> %s %s", enable, r.status_code, r.text)
    return ok


def get_order_status(symbol: str, order_id: int) -> Optional[str]:
    try:
        r = client.signed_request(
            "GET", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}
        )
        if r.status_code == 400:
            try:
                body = r.json()
            except Exception:
                body = {}
            if isinstance(body, dict) and body.get("code") == -2013:
                return "NOT_FOUND"
        data = client.parse_json_response(r, f"주문 조회 {symbol}/{order_id}")
        if r.status_code == 200 and "status" in data:
            return data["status"]
        logger.warning(
            "주문 조회 실패(%s): %s / %s",
            r.status_code,
            symbol,
            data,
            extra={"symbol": symbol, "order_id": order_id, "status_code": r.status_code},
        )
        return None
    except Exception as e:
        logger.exception("주문 조회 예외 발생: %s", e, extra={"symbol": symbol, "order_id": order_id})
        return None


def get_order_detail(symbol: str, order_id: int) -> Optional[dict]:
    try:
        r = client.signed_request(
            "GET", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}
        )
        if r.status_code == 200:
            data = client.parse_json_response(r, f"주문 상세 조회 {symbol}/{order_id}")
            if isinstance(data, dict):
                return data
            logger.warning("주문 상세 응답 형식 오류: %s / %s", symbol, data)
            return None
        if r.status_code == 400:
            try:
                body = r.json()
            except Exception:
                body = {}
            if isinstance(body, dict) and body.get("code") == -2013:
                return {"status": "NOT_FOUND"}
        logger.warning(
            "주문 상세 조회 실패(%s): %s / %s",
            r.status_code,
            symbol,
            r.text,
            extra={"symbol": symbol, "order_id": order_id, "status_code": r.status_code},
        )
        return None
    except Exception as e:
        logger.exception("주문 상세 조회 예외: %s", e, extra={"symbol": symbol, "order_id": order_id})
        return None


def cancel_order(symbol: str, order_id: int) -> bool:
    try:
        r = client.signed_request(
            "DELETE", "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}
        )
        if r.status_code == 200:
            logger.info(
                "주문 취소 성공: %s / %s",
                symbol,
                order_id,
                extra={"event": "order_canceled", "symbol": symbol, "order_id": order_id},
            )
            return True
        logger.warning(
            "주문 취소 실패(%s): %s / %s",
            r.status_code,
            symbol,
            order_id,
            extra={"event": "order_cancel_failed", "symbol": symbol, "order_id": order_id},
        )
        return False
    except Exception as e:
        logger.exception("주문 취소 예외: %s", e, extra={"symbol": symbol, "order_id": order_id})
        return False


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
            logger.info(
                "%s 주문 성공: %s @ %s (positionSide=%s, orderId=%s)",
                side,
                symbol,
                price,
                position_side,
                order_id,
                extra={
                    "event": "order_placed",
                    "symbol": symbol,
                    "order_id": order_id,
                    "side": side,
                    "price": str(price),
                    "qty": str(qty),
                    "position_side": position_side,
                },
            )
            return order_id, None
        err = data if isinstance(data, dict) else {"msg": r.text}
        if isinstance(err, dict) and err.get("code") == -4140:
            # "Invalid symbol status for opening position." 등: 오픈 금지(closeOnly) 케이스가 흔함
            runtime.SKIP_UNTIL[symbol] = int(time.time()) + 60 * 30
            logger.warning(
                "오픈 불가 심볼로 판단, 30분 스킵: %s",
                symbol,
                extra={"event": "symbol_skip_set", "symbol": symbol, "wait_sec": 1800},
            )
        logger.warning(
            "주문 실패(%s): %s / %s",
            r.status_code,
            symbol,
            err,
            extra={"event": "order_place_failed", "symbol": symbol, "side": side, "status_code": r.status_code},
        )
        return None, err
    except Exception as e:
        logger.exception("주문 예외 발생: %s", e)
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
            logger.warning("TP 최소 수량 미달: %s < %s", eff_qty, min_qty)
            return None

        if min_notional > 0 and tp_price * eff_qty < min_notional:
            eff_qty = filters.adjust_qty_for_min_notional(
                tp_price, eff_qty, qty_step, min_qty, min_notional
            )
            if eff_qty is None or eff_qty > qty:
                logger.warning("TP MIN_NOTIONAL 불가: tp=%s qty=%s", tp_price, qty)
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
            logger.info(
                "TP 주문 성공: %s %s 익절 @ %s (qty=%s, tpOrderId=%s)",
                symbol,
                direction,
                tp_price,
                eff_qty,
                oid,
                extra={
                    "event": "tp_order_placed",
                    "symbol": symbol,
                    "direction": direction,
                    "order_id": oid,
                    "tp_price": str(tp_price),
                    "qty": str(eff_qty),
                },
            )
            return oid
        logger.warning("TP 주문 실패(%s): %s / %s", r.status_code, symbol, data)
        return None
    except Exception as e:
        logger.exception("TP 주문 예외 발생: %s", e)
        return None


def place_short_order(
    symbol: str, notional_usdt: Optional[Decimal] = None
) -> Optional[Tuple[Decimal, Decimal, int]]:
    logger.info("숏 주문 시도: %s", symbol)
    try:
        ensure_leverage(symbol)
        resp = client._http_get(
            f"{config.BASE_URL_FUTURES}/fapi/v1/ticker/price",
            params={"symbol": symbol},
            timeout=10,
        )
        resp_data = client.parse_json_response(resp, f"{symbol} 가격 조회")
        if not isinstance(resp_data, dict) or "price" not in resp_data:
            raise RuntimeError(f"{symbol} 가격 응답 형식 오류: {resp_data}")
        price = Decimal(str(resp_data["price"]))
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
                logger.warning("MIN_NOTIONAL 충족 불가: %s", symbol)
                return None
            qty = adj

            pos_side = "SHORT" if runtime.IS_HEDGE else None
            order_id, err = place_limit_order(symbol, "SELL", limit_price, qty, pos_side)
            if order_id is not None:
                return limit_price, qty, order_id

            if err and err.get("code") == -2027:
                logger.warning(
                    "%s 포지션 한도 초과(-2027), 명목 %s USDT → 50%% 축소 후 재시도 (%s/10)",
                    symbol,
                    target_notional,
                    attempt + 1,
                )
                target_notional = target_notional / Decimal("2")
                q_try = filters.round_step_floor(target_notional / limit_price, qty_step)
                if q_try < min_qty:
                    logger.warning("명목 축소 후 최소 수량 미만: %s", symbol)
                    return None
                continue
            return None

        logger.warning("%s 숏 주문 -2027 재시도 한도 초과", symbol)
        return None
    except Exception as e:
        logger.exception("숏 주문 예외 발생: %s", e)
        return None


def place_long_order(
    symbol: str, notional_usdt: Optional[Decimal] = None
) -> Optional[Tuple[Decimal, Decimal, int]]:
    logger.info("롱 주문 시도: %s", symbol)
    try:
        ensure_leverage(symbol)
        resp = client._http_get(
            f"{config.BASE_URL_FUTURES}/fapi/v1/ticker/price",
            params={"symbol": symbol},
            timeout=10,
        )
        resp_data = client.parse_json_response(resp, f"{symbol} 가격 조회")
        if not isinstance(resp_data, dict) or "price" not in resp_data:
            raise RuntimeError(f"{symbol} 가격 응답 형식 오류: {resp_data}")
        price = Decimal(str(resp_data["price"]))
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
                logger.warning("MIN_NOTIONAL 충족 불가: %s", symbol)
                return None
            qty = adj

            pos_side = "LONG" if runtime.IS_HEDGE else None
            order_id, err = place_limit_order(symbol, "BUY", limit_price, qty, pos_side)
            if order_id is not None:
                return limit_price, qty, order_id

            if err and err.get("code") == -2027:
                logger.warning(
                    "%s 포지션 한도 초과(-2027), 명목 %s USDT → 50%% 축소 (%s/10)",
                    symbol,
                    target_notional,
                    attempt + 1,
                )
                target_notional = target_notional / Decimal("2")
                q_try = filters.round_step_floor(target_notional / limit_price, qty_step)
                if q_try < min_qty:
                    logger.warning("명목 축소 후 최소 수량 미만: %s", symbol)
                    return None
                continue
            return None

        logger.warning("%s 롱 주문 -2027 재시도 한도 초과", symbol)
        return None
    except Exception as e:
        logger.exception("롱 주문 예외 발생: %s", e)
        return None
