import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from generator import build
from generator.build import (
    assemble_payload,
    build_chart,
    parse_daily_payload,
    parse_jsonp,
    parse_minute_payload,
)
from generator.market import INSTRUMENTS


class ParsingTests(unittest.TestCase):
    def test_parse_jsonp_accepts_plain_json_and_callback(self):
        self.assertEqual([1, 2], parse_jsonp("[1,2]"))
        self.assertEqual({"ok": 1}, parse_jsonp("callback({\"ok\":1})"))

    def test_daily_payload_is_normalized_and_sorted(self):
        rows = parse_daily_payload([
            {"d": "2026-09-18", "o": "11", "h": "13", "l": "10", "c": "12", "v": "20"},
            {"d": "2026-09-17", "o": "10", "h": "12", "l": "9", "c": "11", "v": "10"},
        ])
        self.assertEqual("2026-09-17", rows[0]["date"])
        self.assertEqual(12.0, rows[-1]["close"])

    def test_minute_payload_supports_dict_rows(self):
        rows = parse_minute_payload([
            {"d": "2026-09-18 10:00:00", "o": "10", "h": "12", "l": "9", "c": "11", "v": "7"},
        ])
        self.assertEqual("2026-09-18 10:00:00", rows[0]["datetime"])
        self.assertEqual(7.0, rows[0]["volume"])

    def test_main_contract_excludes_only_continuous_symbol_and_ranks_open_interest(self):
        rows = [
            {"symbol": "MA0", "position": "900000", "volume": "500000"},
            {"symbol": "MA2610", "position": "200000", "volume": "100000"},
            {"symbol": "MA2701", "position": "200000", "volume": "120000"},
            {"symbol": "MA2705", "position": "not-a-number", "volume": "999999"},
        ]
        self.assertEqual("MA2701", build.select_main_contract("MA0", rows))


class PayloadTests(unittest.TestCase):
    def test_chart_contains_required_moving_averages(self):
        rows = [
            {"date": f"2026-09-{day:02d}", "open": day, "high": day + 1, "low": day - 1, "close": day, "volume": day * 10}
            for day in range(1, 13)
        ]
        chart = build_chart(rows, "date", (5, 10))
        self.assertEqual(12, len(chart))
        self.assertIsNone(chart[3]["ma5"])
        self.assertEqual(3.0, chart[4]["ma5"])
        self.assertEqual(5.5, chart[9]["ma10"])
        self.assertNotIn("ma60", chart[0])

    def test_payload_has_three_rising_and_three_falling_categories(self):
        rows = []
        for index, category in enumerate(["甲", "乙", "丙", "丁", "戊", "己", "庚"]):
            for member in range(3):
                rows.append({
                    "category": category,
                    "name": f"{category}{member}",
                    "symbol": f"{index}{member}",
                    "hasNight": False,
                    "price": 100 + index,
                    "return5": (index - 3) / 100 + member / 1000,
                    "dataDate": "2026-09-18",
                })
        payload = assemble_payload(
            rows,
            charts={},
            generated_at=datetime(2026, 9, 21, 15, 40),
            source_date="2026-09-18",
            coverage=(70, 78),
        )
        self.assertEqual(3, len(payload["rankings"]["rising"]))
        self.assertEqual(3, len(payload["rankings"]["falling"]))
        self.assertEqual("庚", payload["rankings"]["rising"][0]["category"])
        self.assertEqual("甲", payload["rankings"]["falling"][0]["category"])
        self.assertEqual("2026-09-18", payload["dataDate"])
        json.dumps(payload, ensure_ascii=False, allow_nan=False)

    @patch("generator.build._parallel_fetch_minutes")
    @patch("generator.build._parallel_fetch_daily")
    @patch("generator.build.resolve_main_contracts")
    def test_live_build_uses_same_concrete_contract_for_returns_and_charts(
        self,
        mock_resolve,
        mock_daily,
        mock_minutes,
    ):
        contracts = {
            item.symbol: f"{item.symbol[:-1]}2610"
            for item in INSTRUMENTS
        }
        histories = {}
        for index, item in enumerate(INSTRUMENTS):
            histories[item.symbol] = [
                {
                    "date": f"2026-09-{day:02d}",
                    "open": 100 + index + day,
                    "high": 102 + index + day,
                    "low": 99 + index + day,
                    "close": 101 + index + day,
                    "volume": 1000,
                }
                for day in range(14, 22)
            ]
        mock_resolve.return_value = contracts
        mock_daily.return_value = histories
        mock_minutes.return_value = {
            item.symbol: [
                {
                    "datetime": "2026-09-21 15:00:00",
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100,
                    "volume": 10,
                }
            ]
            for item in INSTRUMENTS
        }

        payload = build.build_live_payload(datetime(2026, 9, 21, 16, 0))

        mock_daily.assert_called_once_with(contracts)
        selected_items, minute_contracts = mock_minutes.call_args.args
        self.assertEqual(contracts, minute_contracts)
        members = [
            member
            for side in payload["rankings"].values()
            for category in side
            for member in category["members"]
        ]
        self.assertTrue(members)
        self.assertTrue(all(member["contract"] == contracts[member["symbol"]] for member in members))
        self.assertTrue(selected_items)
        self.assertTrue(all(
            payload["charts"][item.symbol]["contract"] == contracts[item.symbol]
            for item in selected_items
        ))
        self.assertIn("具体主力合约", payload["source"])


class ResilienceTests(unittest.TestCase):
    def test_daily_coverage_requires_full_universe(self):
        coverage_is_acceptable = getattr(build, "daily_coverage_is_acceptable", None)
        self.assertIsNotNone(coverage_is_acceptable)
        self.assertFalse(coverage_is_acceptable(77, 78))
        self.assertTrue(coverage_is_acceptable(78, 78))

    def test_daily_gap_details_identify_missing_and_stale_products(self):
        describe_daily_gaps = getattr(build, "describe_daily_gaps", None)
        self.assertIsNotNone(describe_daily_gaps)
        current, stale, missing = INSTRUMENTS[:3]
        histories = {
            current.symbol: [{"date": "2026-09-23", "close": 100.0}],
            stale.symbol: [{"date": "2026-09-22", "close": 99.0}],
        }

        details = describe_daily_gaps(histories, "2026-09-23", [current, stale, missing])

        self.assertEqual([
            f"{stale.name}/{stale.symbol}:2026-09-22",
            f"{missing.name}/{missing.symbol}:无数据",
        ], details)

    @patch("generator.build.time.sleep", return_value=None)
    @patch("generator.build.fetch_daily")
    def test_daily_fetch_retries_missing_and_stale_symbols(self, mock_fetch_daily, _mock_sleep):
        attempts = {}
        missing_once = INSTRUMENTS[0].symbol
        stale_once = INSTRUMENTS[1].symbol
        contracts = {
            item.symbol: f"{item.symbol[:-1]}2610"
            for item in INSTRUMENTS
        }
        products = {contract: product for product, contract in contracts.items()}

        def fake_fetch(contract):
            product = products[contract]
            attempts[product] = attempts.get(product, 0) + 1
            if product == missing_once and attempts[product] == 1:
                return []
            if product == stale_once and attempts[product] == 1:
                return [{"date": "2026-09-18", "close": 99.0}]
            return [{"date": "2026-09-21", "close": 100.0}]

        mock_fetch_daily.side_effect = fake_fetch
        result = build._parallel_fetch_daily(contracts)

        self.assertEqual(len(INSTRUMENTS), len(result))
        self.assertEqual(2, attempts[missing_once])
        self.assertEqual(2, attempts[stale_once])
        self.assertEqual("2026-09-21", result[stale_once][-1]["date"])
        self.assertTrue(all(attempts[item.symbol] == 1 for item in INSTRUMENTS[2:]))

    def test_build_reuses_existing_snapshot_when_live_fetch_is_incomplete(self):
        previous = {
            "schemaVersion": 1,
            "generatedAt": "2026-09-21T15:40:00+08:00",
            "dataDate": "2026-09-18",
            "coverage": {"available": 78, "total": 78},
            "rankings": {"rising": [], "falling": []},
            "categoryTable": [],
            "selectedSymbols": [],
            "charts": {},
        }
        output = Path("tests/.tmp_latest.json")
        try:
            output.write_text(json.dumps(previous), encoding="utf-8")

            def incomplete_builder():
                raise RuntimeError("日线覆盖不足: 34/78")

            build_or_reuse_payload = getattr(build, "build_or_reuse_payload", None)
            self.assertIsNotNone(build_or_reuse_payload)
            payload, reused = build_or_reuse_payload(output, incomplete_builder)
        finally:
            output.unlink(missing_ok=True)

        self.assertTrue(reused)
        self.assertEqual(previous, payload)


if __name__ == "__main__":
    unittest.main()
