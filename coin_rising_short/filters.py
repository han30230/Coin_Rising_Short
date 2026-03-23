from decimal import ROUND_CEILING, Decimal
from typing import Optional, Tuple

from coin_rising_short import symbols


def round_step_floor(value: Decimal, step: Decimal) -> Decimal:
    if step == 0:
        return value
    return (value // step) * step


def round_step_ceil(value: Decimal, step: Decimal) -> Decimal:
    if step == 0:
        return value
    n = (value / step).to_integral_value(rounding=ROUND_CEILING)
    return n * step


def parse_filters(info: dict) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    """(price_step, qty_step, min_qty, min_notional)"""
    price_step = qty_step = min_qty = None
    min_notional = Decimal("0")
    for f in info.get("filters", []):
        ftype = f.get("filterType")
        if ftype == "PRICE_FILTER":
            price_step = Decimal(f["tickSize"])
        elif ftype == "LOT_SIZE":
            qty_step = Decimal(f["stepSize"])
            min_qty = Decimal(f["minQty"])
        elif ftype == "MIN_NOTIONAL":
            min_notional = Decimal(f["notional"])
    if price_step is None or qty_step is None or min_qty is None:
        raise Exception(f"{info.get('symbol')} 필터 파싱 실패")
    return price_step, qty_step, min_qty, min_notional


def get_price_step_and_qty_step(symbol: str) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
    info = symbols.TRADING_SYMBOLS.get(symbol)
    if not info:
        raise Exception(f"{symbol} 거래 정보 없음")
    return parse_filters(info)


def adjust_qty_for_min_notional(
    limit_price: Decimal,
    qty: Decimal,
    qty_step: Decimal,
    min_qty: Decimal,
    min_notional: Decimal,
) -> Optional[Decimal]:
    q = round_step_floor(qty, qty_step)
    if q < min_qty:
        q = min_qty
    if min_notional <= 0:
        return q if q >= min_qty else None
    for _ in range(10000):
        if limit_price * q >= min_notional and q >= min_qty:
            return q
        q = q + qty_step
    return None
