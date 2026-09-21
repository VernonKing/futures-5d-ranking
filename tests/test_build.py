import json
import unittest
from datetime import datetime

from generator.build import (
    assemble_payload,
    build_chart,
    parse_daily_payload,
    parse_jsonp,
    parse_minute_payload,
)


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


if __name__ == "__main__":
    unittest.main()
