import unittest

from generator.market import (
    INSTRUMENTS,
    aggregate_hourly,
    five_day_return,
    moving_average,
    rank_categories,
    validate_universe,
)


class UniverseTests(unittest.TestCase):
    def test_symbols_are_unique_and_categories_are_valid(self):
        self.assertEqual([], validate_universe())
        self.assertEqual(78, len(INSTRUMENTS))
        self.assertEqual(78, len({item.symbol for item in INSTRUMENTS}))
        self.assertEqual(
            {
                "贵金属", "工业金属", "黑色系", "新能源", "股指", "利率债",
                "能源与油头化工", "基础化工", "农业", "生猪", "航运",
            },
            {item.category for item in INSTRUMENTS},
        )

    def test_singleton_categories_are_explicit(self):
        grouped = {}
        for item in INSTRUMENTS:
            grouped.setdefault(item.category, []).append(item.symbol)
        self.assertEqual(["LH0"], grouped["生猪"])
        self.assertEqual(["EC0"], grouped["航运"])


class RankingTests(unittest.TestCase):
    def test_five_day_return_uses_six_closes(self):
        self.assertAlmostEqual(0.10, five_day_return([100, 101, 102, 103, 104, 110]))
        self.assertIsNone(five_day_return([100, 101, 102, 103, 104]))

    def test_category_ranking_uses_median_and_directional_members(self):
        rows = [
            {"category": "甲", "symbol": "A", "return5": 0.30},
            {"category": "甲", "symbol": "B", "return5": 0.01},
            {"category": "甲", "symbol": "C", "return5": -0.20},
            {"category": "乙", "symbol": "D", "return5": 0.08},
            {"category": "乙", "symbol": "E", "return5": 0.07},
            {"category": "乙", "symbol": "F", "return5": 0.06},
            {"category": "丙", "symbol": "G", "return5": -0.01},
            {"category": "丙", "symbol": "H", "return5": -0.04},
            {"category": "丙", "symbol": "I", "return5": -0.07},
            {"category": "丁", "symbol": "J", "return5": -0.08},
            {"category": "丁", "symbol": "K", "return5": -0.09},
            {"category": "丁", "symbol": "L", "return5": -0.10},
        ]
        ranked = rank_categories(rows, category_limit=1, member_limit=2)
        self.assertEqual("乙", ranked["rising"][0]["category"])
        self.assertAlmostEqual(0.07, ranked["rising"][0]["medianReturn"])
        self.assertEqual(["D", "E"], [item["symbol"] for item in ranked["rising"][0]["members"]])
        self.assertEqual("丁", ranked["falling"][0]["category"])
        self.assertEqual(["L", "K"], [item["symbol"] for item in ranked["falling"][0]["members"]])

    def test_single_member_category_is_rankable_without_duplication(self):
        ranked = rank_categories(
            [{"category": "生猪", "symbol": "LH0", "return5": 0.12}],
            category_limit=3,
            member_limit=3,
        )
        self.assertEqual(1, len(ranked["rising"][0]["members"]))
        self.assertEqual("LH0", ranked["rising"][0]["members"][0]["symbol"])


class SeriesTests(unittest.TestCase):
    def test_night_market_pairs_adjacent_hour_bars_across_breaks(self):
        rows = [
            {"datetime": "2026-09-18 10:00:00", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 3},
            {"datetime": "2026-09-18 11:30:00", "open": 11, "high": 13, "low": 10, "close": 12, "volume": 4},
            {"datetime": "2026-09-18 14:00:00", "open": 12, "high": 14, "low": 11, "close": 13, "volume": 5},
            {"datetime": "2026-09-18 21:00:00", "open": 13, "high": 16, "low": 12, "close": 15, "volume": 6},
        ]
        result = aggregate_hourly(rows, has_night=True)
        self.assertEqual(2, len(result))
        self.assertEqual("2026-09-18 11:30:00", result[0]["datetime"])
        self.assertEqual(10, result[0]["open"])
        self.assertEqual(13, result[0]["high"])
        self.assertEqual(9, result[0]["low"])
        self.assertEqual(12, result[0]["close"])
        self.assertEqual(7, result[0]["volume"])
        self.assertEqual("2026-09-18 21:00:00", result[1]["datetime"])

    def test_day_market_stays_hourly(self):
        rows = [{"datetime": "2026-09-18 10:00:00", "close": 1}]
        self.assertEqual(rows, aggregate_hourly(rows, has_night=False))

    def test_moving_average_has_null_warmup(self):
        self.assertEqual([None, None, 2.0, 3.0, 4.0], moving_average([1, 2, 3, 4, 5], 3))


if __name__ == "__main__":
    unittest.main()
