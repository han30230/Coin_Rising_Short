from decimal import Decimal
from unittest.mock import patch

from coin_rising_short import positions, state


def test_repair_pending_entry_from_exchange():
    symbol = "TESTUSDT"
    st = {
        "entries": [
            {
                "direction": "SHORT",
                "entry_price": Decimal("10"),
                "qty": Decimal("1"),
                "order_id": 123,
                "filled": False,
                "closed": False,
            }
        ],
        "st_last_direction": None,
    }
    state.position_state[symbol] = st
    ex = {"size": Decimal("2"), "avg_price": Decimal("9.5"), "side": "SHORT"}

    with patch.object(positions, "st_last_direction_for_recovery", return_value=-1):
        assert positions.repair_short_tracking_from_exchange(symbol, st, ex) is True

    entry = st["entries"][0]
    assert entry["filled"] is True
    assert entry["qty"] == Decimal("2")
    assert entry["entry_price"] == Decimal("9.5")
    assert st["st_last_direction"] == -1
    state.position_state.clear()


def test_adopt_recovered_short_creates_managed_state():
    symbol = "ABCUSDT"
    ex = {"size": Decimal("3"), "avg_price": Decimal("1.5"), "side": "SHORT"}

    with patch.object(positions, "st_last_direction_for_recovery", return_value=-1):
        positions.adopt_recovered_short(symbol, ex)

    st = state.position_state[symbol]
    assert st.get("external") is None
    _, qty, _ = positions.get_filled_from_state(st)
    assert qty == Decimal("3")
    assert st["st_last_direction"] == -1
    state.position_state.clear()
