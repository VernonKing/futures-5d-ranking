from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Instrument:
    name: str
    symbol: str
    category: str
    has_night: bool


def _items(category: str, has_night: bool, values: Iterable[tuple[str, str]]) -> list[Instrument]:
    return [Instrument(name, symbol, category, has_night) for name, symbol in values]


INSTRUMENTS = [
    *_items("贵金属", True, [("黄金", "AU0"), ("白银", "AG0")]),
    *_items("贵金属", False, [("铂", "PT0"), ("钯", "PD0")]),
    *_items("工业金属", True, [
        ("铜", "CU0"), ("国际铜", "BC0"), ("铝", "AL0"), ("锌", "ZN0"),
        ("铅", "PB0"), ("镍", "NI0"), ("锡", "SN0"), ("氧化铝", "AO0"),
        ("铸造铝合金", "AD0"),
    ]),
    *_items("黑色系", True, [
        ("螺纹钢", "RB0"), ("热轧卷板", "HC0"), ("不锈钢", "SS0"),
        ("焦炭", "J0"), ("焦煤", "JM0"), ("铁矿石", "I0"), ("玻璃", "FG0"),
        ("硅铁", "SF0"), ("锰硅", "SM0"),
    ]),
    *_items("新能源", False, [("工业硅", "SI0"), ("碳酸锂", "LC0"), ("多晶硅", "PS0")]),
    *_items("股指", False, [
        ("沪深300股指", "IF0"), ("上证50股指", "IH0"),
        ("中证500股指", "IC0"), ("中证1000股指", "IM0"),
    ]),
    *_items("利率债", False, [
        ("2年期国债", "TS0"), ("5年期国债", "TF0"),
        ("10年期国债", "T0"), ("30年期国债", "TL0"),
    ]),
    *_items("能源与油头化工", True, [
        ("原油", "SC0"), ("低硫燃料油", "LU0"), ("燃料油", "FU0"),
        ("沥青", "BU0"), ("液化石油气", "PG0"), ("聚乙烯", "L0"),
        ("PVC", "V0"), ("聚丙烯", "PP0"), ("乙二醇", "EG0"),
        ("苯乙烯", "EB0"), ("纯苯", "BZ0"), ("PTA", "TA0"),
        ("短纤", "PF0"), ("对二甲苯", "PX0"), ("瓶片", "PR0"),
        ("丙烯", "PL0"), ("合成橡胶", "BR0"),
    ]),
    *_items("基础化工", True, [("甲醇", "MA0"), ("纯碱", "SA0"), ("烧碱", "SH0")]),
    *_items("基础化工", False, [("尿素", "UR0")]),
    *_items("农业", True, [
        ("玉米", "C0"), ("玉米淀粉", "CS0"), ("豆一", "A0"), ("豆二", "B0"),
        ("豆粕", "M0"), ("豆油", "Y0"), ("棕榈油", "P0"), ("粳米", "RR0"),
        ("白糖", "SR0"), ("棉花", "CF0"), ("菜粕", "RM0"), ("菜油", "OI0"),
        ("棉纱", "CY0"), ("天然橡胶", "RU0"), ("20号胶", "NR0"),
        ("纸浆", "SP0"), ("胶版印刷纸", "OP0"),
    ]),
    *_items("农业", False, [
        ("鸡蛋", "JD0"), ("原木", "LG0"), ("苹果", "AP0"),
        ("红枣", "CJ0"), ("花生", "PK0"),
    ]),
    *_items("生猪", False, [("生猪", "LH0")]),
    *_items("航运", False, [("集运指数欧线", "EC0")]),
]


VALID_CATEGORIES = {
    "贵金属", "工业金属", "黑色系", "新能源", "股指", "利率债",
    "能源与油头化工", "基础化工", "农业", "生猪", "航运",
}


def validate_universe() -> list[str]:
    errors: list[str] = []
    symbols = [item.symbol for item in INSTRUMENTS]
    duplicates = sorted({symbol for symbol in symbols if symbols.count(symbol) > 1})
    if duplicates:
        errors.append(f"重复代码: {', '.join(duplicates)}")
    invalid = sorted({item.category for item in INSTRUMENTS} - VALID_CATEGORIES)
    if invalid:
        errors.append(f"未知分类: {', '.join(invalid)}")
    missing = sorted(VALID_CATEGORIES - {item.category for item in INSTRUMENTS})
    if missing:
        errors.append(f"空分类: {', '.join(missing)}")
    return errors


def five_day_return(closes: list[float]) -> float | None:
    if len(closes) < 6 or closes[-6] == 0:
        return None
    return closes[-1] / closes[-6] - 1.0


def rank_categories(
    rows: list[dict[str, Any]],
    category_limit: int = 3,
    member_limit: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = row.get("return5")
        if value is None:
            continue
        grouped.setdefault(row["category"], []).append(row)

    categories = []
    for category, members in grouped.items():
        median = statistics.median(float(item["return5"]) for item in members)
        categories.append({"category": category, "medianReturn": median, "allMembers": members})

    rising = sorted(categories, key=lambda item: (-item["medianReturn"], item["category"]))[:category_limit]
    falling = sorted(categories, key=lambda item: (item["medianReturn"], item["category"]))[:category_limit]

    def present(item: dict[str, Any], reverse: bool) -> dict[str, Any]:
        members = sorted(
            item["allMembers"],
            key=lambda member: ((-1 if reverse else 1) * float(member["return5"]), member["symbol"]),
        )[:member_limit]
        return {
            "category": item["category"],
            "medianReturn": item["medianReturn"],
            "memberCount": len(item["allMembers"]),
            "members": members,
        }

    return {
        "rising": [present(item, True) for item in rising],
        "falling": [present(item, False) for item in falling],
    }


def moving_average(values: list[float], period: int) -> list[float | None]:
    if period <= 0:
        raise ValueError("period must be positive")
    output: list[float | None] = []
    running = 0.0
    for index, value in enumerate(values):
        running += value
        if index >= period:
            running -= values[index - period]
        output.append(running / period if index + 1 >= period else None)
    return output


def aggregate_hourly(rows: list[dict[str, Any]], has_night: bool) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda item: item["datetime"])
    if not has_night:
        return ordered
    output = []
    for index in range(0, len(ordered) - 1, 2):
        first, second = ordered[index:index + 2]
        output.append({
            "datetime": second["datetime"],
            "open": first["open"],
            "high": max(first["high"], second["high"]),
            "low": min(first["low"], second["low"]),
            "close": second["close"],
            "volume": first.get("volume", 0) + second.get("volume", 0),
        })
    return output
