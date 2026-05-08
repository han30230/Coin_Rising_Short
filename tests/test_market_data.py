import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from coin_rising_short import config, market_data
from coin_rising_short.market_data import clear_coingecko_cache_for_tests, filter_by_mcap_fdv


class TestFilterByMcapFdv(unittest.TestCase):
    def setUp(self) -> None:
        clear_coingecko_cache_for_tests()

    def tearDown(self) -> None:
        clear_coingecko_cache_for_tests()

    def test_filter_off_passes_through(self) -> None:
        rows = [{"symbol": "BTCUSDT", "change_pct": Decimal("25")}]
        with patch.object(config, "FILTER_MCAP_FDV", False):
            out = filter_by_mcap_fdv(rows)
        self.assertIs(out, rows)
        self.assertEqual(len(out), 1)

    @patch.object(market_data, "get_mcap_fdv_map")
    def test_ratio_below_min_excluded(self, mock_map: MagicMock) -> None:
        mock_map.return_value = {
            "BTCUSDT": {
                "market_cap": Decimal("100"),
                "fully_diluted_valuation": Decimal("1000"),
                "mcap_fdv_ratio": Decimal("0.1"),
            }
        }
        rows = [{"symbol": "BTCUSDT"}]
        with patch.object(config, "FILTER_MCAP_FDV", True), patch.object(
            config, "MIN_MCAP_FDV_RATIO", Decimal("0.4")
        ):
            out = filter_by_mcap_fdv(rows)
        self.assertEqual(out, [])

    @patch.object(market_data, "get_mcap_fdv_map")
    def test_ratio_meets_min_keeps_and_enriches(self, mock_map: MagicMock) -> None:
        mock_map.return_value = {
            "BTCUSDT": {
                "market_cap": Decimal("800"),
                "fully_diluted_valuation": Decimal("1000"),
                "mcap_fdv_ratio": Decimal("0.8"),
            }
        }
        rows = [{"symbol": "BTCUSDT", "change_pct": Decimal("30")}]
        with patch.object(config, "FILTER_MCAP_FDV", True), patch.object(
            config, "MIN_MCAP_FDV_RATIO", Decimal("0.4")
        ):
            out = filter_by_mcap_fdv(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["mcap_fdv_ratio"], Decimal("0.8"))
        self.assertEqual(out[0]["coingecko_market_cap"], Decimal("800"))
        self.assertEqual(out[0]["coingecko_fdv"], Decimal("1000"))

    @patch.object(market_data, "get_mcap_fdv_map", return_value={})
    def test_empty_map_drops_all(self, _mock: MagicMock) -> None:
        rows = [{"symbol": "BTCUSDT"}]
        with patch.object(config, "FILTER_MCAP_FDV", True):
            out = filter_by_mcap_fdv(rows)
        self.assertEqual(out, [])


if __name__ == "__main__":
    unittest.main()
