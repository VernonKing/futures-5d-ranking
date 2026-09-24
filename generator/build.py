from __future__ import annotations

import argparse
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as clock_time
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

from generator.market import (
    INSTRUMENTS,
    SINA_NODE_BY_SYMBOL,
    Instrument,
    aggregate_hourly,
    five_day_return,
    moving_average,
    rank_categories,
    validate_universe,
)


TZ = ZoneInfo("Asia/Shanghai")
HEADERS = {"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"}
DAILY_URLS = (
    "https://stock2.finance.sina.com.cn/futures/api/json.php/InnerFuturesNewService.getDailyKLine?symbol={symbol}",
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_{symbol}_=/InnerFuturesNewService.getDailyKLine?symbol={symbol}",
)
MINUTE_URL = (
    "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
    "var%20_{symbol}_60_=/InnerFuturesNewService.getFewMinLine?symbol={symbol}&type=60"
)
MAIN_CONTRACT_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQFuturesData?page=1&num=50&sort=position&asc=0&"
    "node={node}&base=futures"
)


def parse_jsonp(text: str) -> Any:
    payload = text.strip()
    if payload.startswith("[") or payload.startswith("{"):
        return json.loads(payload)
    start, end = payload.find("("), payload.rfind(")")
    if start >= 0 and end > start:
        return json.loads(payload[start + 1:end])
    raise ValueError("无法识别行情响应")


def _float(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("非有限数字")
    return number


def parse_daily_payload(data: Any) -> list[dict[str, Any]]:
    rows = []
    for row in data or []:
        try:
            rows.append({
                "date": str(row["d"]),
                "open": _float(row["o"]),
                "high": _float(row["h"]),
                "low": _float(row["l"]),
                "close": _float(row["c"]),
                "volume": _float(row.get("v", 0)),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(rows, key=lambda item: item["date"])


def parse_minute_payload(data: Any) -> list[dict[str, Any]]:
    rows = []
    for row in data or []:
        try:
            if isinstance(row, dict):
                normalized = {
                    "datetime": str(row.get("d") or row.get("date")),
                    "open": _float(row["o"]),
                    "high": _float(row["h"]),
                    "low": _float(row["l"]),
                    "close": _float(row["c"]),
                    "volume": _float(row.get("v", 0)),
                }
            else:
                normalized = {
                    "datetime": str(row[0]), "open": _float(row[1]),
                    "high": _float(row[2]), "low": _float(row[3]),
                    "close": _float(row[4]), "volume": _float(row[5]),
                }
            if normalized["datetime"]:
                rows.append(normalized)
        except (IndexError, KeyError, TypeError, ValueError):
            continue
    return sorted(rows, key=lambda item: item["datetime"])


def _get_json(urls: list[str], attempts: int = 3) -> Any:
    session = requests.Session()
    session.trust_env = False
    try:
        for url in urls:
            for attempt in range(attempts):
                try:
                    response = session.get(url, headers=HEADERS, timeout=20)
                    if response.ok and response.text.strip():
                        data = parse_jsonp(response.text)
                        if data:
                            return data
                except (requests.RequestException, ValueError, json.JSONDecodeError):
                    pass
                if attempt + 1 < attempts:
                    time.sleep(0.2 * (attempt + 1))
    finally:
        session.close()
    return None


def fetch_daily(symbol: str) -> list[dict[str, Any]]:
    urls = [template.format(symbol=symbol) for template in DAILY_URLS]
    return parse_daily_payload(_get_json(urls))


def fetch_minute(symbol: str) -> list[dict[str, Any]]:
    return parse_minute_payload(_get_json([MINUTE_URL.format(symbol=symbol)]))


def select_main_contract(product_symbol: str, rows: Any) -> str | None:
    product = product_symbol.upper()
    root = product[:-1]
    candidates: list[tuple[float, float, str]] = []
    for row in rows or []:
        try:
            symbol = str(row["symbol"]).strip().upper()
            suffix = symbol[len(root):]
            if symbol == product or not symbol.startswith(root) or not suffix.isdigit():
                continue
            position = _float(row["position"])
            volume = _float(row.get("volume", 0))
            candidates.append((position, volume, symbol))
        except (KeyError, TypeError, ValueError):
            continue
    if not candidates:
        return None
    return max(candidates)[2]


def fetch_main_contract(instrument: Instrument) -> str | None:
    node = SINA_NODE_BY_SYMBOL[instrument.symbol]
    rows = _get_json([MAIN_CONTRACT_URL.format(node=node)])
    return select_main_contract(instrument.symbol, rows)


def resolve_main_contracts() -> dict[str, str]:
    contracts: dict[str, str] = {}
    retry_delays = (0.0, 1.5, 4.0)
    for delay in retry_delays:
        pending_instruments = [
            item for item in INSTRUMENTS
            if item.symbol not in contracts
        ]
        if not pending_instruments:
            break
        if delay:
            time.sleep(delay)
        with ThreadPoolExecutor(max_workers=min(4, len(pending_instruments))) as executor:
            pending = {
                executor.submit(fetch_main_contract, item): item.symbol
                for item in pending_instruments
            }
            for future in as_completed(pending):
                product_symbol = pending[future]
                try:
                    contract = future.result()
                    if contract:
                        contracts[product_symbol] = contract
                except Exception:
                    continue
    if not daily_coverage_is_acceptable(len(contracts), len(INSTRUMENTS)):
        raise RuntimeError(f"主力合约识别不足: {len(contracts)}/{len(INSTRUMENTS)}")
    return contracts


def completed_daily_rows(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    today = now.date().isoformat()
    include_today = now.weekday() < 5 and now.time() >= clock_time(15, 35)
    return [row for row in rows if row["date"] < today or (include_today and row["date"] == today)]


def build_chart(
    rows: list[dict[str, Any]],
    time_key: str,
    periods: tuple[int, ...],
    limit: int = 140,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    closes = [float(row["close"]) for row in rows]
    averages = {period: moving_average(closes, period) for period in periods}
    start = max(0, len(rows) - limit)
    output = []
    for index in range(start, len(rows)):
        row = rows[index]
        point = {
            "time": row[time_key],
            "open": row["open"], "high": row["high"],
            "low": row["low"], "close": row["close"],
            "volume": row.get("volume", 0),
        }
        for period in periods:
            value = averages[period][index]
            point[f"ma{period}"] = round(value, 6) if value is not None else None
        output.append(point)
    return output


def assemble_payload(
    rows: list[dict[str, Any]],
    charts: dict[str, dict[str, Any]],
    generated_at: datetime,
    source_date: str,
    coverage: tuple[int, int],
) -> dict[str, Any]:
    rankings = rank_categories(rows)
    selected = list(dict.fromkeys(
        member["symbol"]
        for side in ("rising", "falling")
        for category in rankings[side]
        for member in category["members"]
    ))
    category_table = []
    grouped = rank_categories(rows, category_limit=len({row["category"] for row in rows}), member_limit=0)
    seen = set()
    for item in grouped["rising"]:
        if item["category"] in seen:
            continue
        seen.add(item["category"])
        category_table.append({key: item[key] for key in ("category", "medianReturn", "memberCount")})
    return {
        "schemaVersion": 2,
        "generatedAt": generated_at.replace(microsecond=0).isoformat(),
        "dataDate": source_date,
        "coverage": {"available": coverage[0], "total": coverage[1]},
        "method": {
            "return": "最新完整日K收盘价 / 5个交易日前收盘价 - 1",
            "category": "品类全部有效品种近5日收益率中位数",
            "mainContract": "运行时按持仓量优先、成交量次优识别具体主力合约，同一合约用于收益、价格和图表",
            "nightIntraday": "2小时K（60分钟K按时间顺序每两根聚合）",
            "dayIntraday": "1小时K",
        },
        "rankings": rankings,
        "categoryTable": category_table,
        "selectedSymbols": selected,
        "charts": charts,
        "source": "新浪财经国内期货具体主力合约公开行情接口",
    }


def _parallel_fetch_daily(contract_by_product: dict[str, str]) -> dict[str, list[dict[str, Any]]]:
    histories: dict[str, list[dict[str, Any]]] = {}
    retry_delays = (0.0, 1.5, 4.0, 8.0, 15.0)
    for delay in retry_delays:
        newest_date = max(
            (rows[-1]["date"] for rows in histories.values() if rows),
            default="",
        )
        pending_instruments = [
            item for item in INSTRUMENTS
            if item.symbol in contract_by_product
            and (item.symbol not in histories
            or (newest_date and histories[item.symbol][-1]["date"] < newest_date)
            )
        ]
        if not pending_instruments:
            break
        if delay:
            time.sleep(delay)
        with ThreadPoolExecutor(max_workers=min(4, len(pending_instruments))) as executor:
            pending = {
                executor.submit(fetch_daily, contract_by_product[item.symbol]): item.symbol
                for item in pending_instruments
            }
            for future in as_completed(pending):
                symbol = pending[future]
                try:
                    rows = future.result()
                    current = histories.get(symbol)
                    if rows and (not current or rows[-1]["date"] >= current[-1]["date"]):
                        histories[symbol] = rows
                except Exception:
                    continue
    return histories


def _parallel_fetch_minutes(
    instruments: list[Instrument],
    contract_by_product: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    histories: dict[str, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        pending = {
            executor.submit(fetch_minute, contract_by_product[item.symbol]): item.symbol
            for item in instruments
            if item.symbol in contract_by_product
        }
        for future in as_completed(pending):
            symbol = pending[future]
            try:
                rows = future.result()
                if rows:
                    histories[symbol] = rows
            except Exception:
                continue
    return histories


def daily_coverage_is_acceptable(available: int, total: int) -> bool:
    return total > 0 and available >= max(total - 3, 1)


def describe_daily_gaps(
    histories: dict[str, list[dict[str, Any]]],
    source_date: str,
    instruments: list[Instrument] = INSTRUMENTS,
) -> list[str]:
    gaps = []
    for instrument in instruments:
        rows = histories.get(instrument.symbol, [])
        latest_date = rows[-1]["date"] if rows else "无数据"
        if latest_date != source_date:
            gaps.append(f"{instrument.name}/{instrument.symbol}:{latest_date}")
    return gaps


def build_live_payload(now: datetime | None = None) -> dict[str, Any]:
    errors = validate_universe()
    if errors:
        raise RuntimeError("; ".join(errors))
    now = now or datetime.now(TZ)
    contract_by_product = resolve_main_contracts()
    fetched = _parallel_fetch_daily(contract_by_product)
    complete = {symbol: completed_daily_rows(rows, now) for symbol, rows in fetched.items()}
    source_date = max((rows[-1]["date"] for rows in complete.values() if rows), default="")
    if not source_date:
        raise RuntimeError("未获取到完整日K")
    current = {symbol: rows for symbol, rows in complete.items() if rows and rows[-1]["date"] == source_date}
    if not daily_coverage_is_acceptable(len(current), len(INSTRUMENTS)):
        gaps = describe_daily_gaps(complete, source_date)
        raise RuntimeError(
            f"日线覆盖不足: {len(current)}/{len(INSTRUMENTS)}; "
            f"缺失或滞后: {', '.join(gaps)}"
        )

    ranked_rows = []
    for instrument in INSTRUMENTS:
        rows = current.get(instrument.symbol, [])
        value = five_day_return([row["close"] for row in rows])
        if value is None:
            continue
        ranked_rows.append({
            "category": instrument.category,
            "name": instrument.name,
            "symbol": instrument.symbol,
            "contract": contract_by_product[instrument.symbol],
            "hasNight": instrument.has_night,
            "price": rows[-1]["close"],
            "return5": value,
            "dataDate": source_date,
        })

    provisional = assemble_payload(
        ranked_rows, {}, now, source_date, (len(current), len(INSTRUMENTS)),
    )
    selected = set(provisional["selectedSymbols"])
    selected_instruments = [item for item in INSTRUMENTS if item.symbol in selected]
    minute_histories = _parallel_fetch_minutes(selected_instruments, contract_by_product)
    charts = {}
    for instrument in selected_instruments:
        daily = current.get(instrument.symbol, [])
        hourly = aggregate_hourly(minute_histories.get(instrument.symbol, []), instrument.has_night)
        charts[instrument.symbol] = {
            "contract": contract_by_product[instrument.symbol],
            "intradayPeriod": "2h" if instrument.has_night else "1h",
            "intraday": build_chart(hourly, "datetime", (5, 10, 60), limit=140),
            "daily": build_chart(daily, "date", (5, 10), limit=140),
        }
    return assemble_payload(
        ranked_rows, charts, now, source_date, (len(current), len(INSTRUMENTS)),
    )


def write_payload(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temporary, output)


def build_or_reuse_payload(
    output: Path,
    builder: Callable[[], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], bool]:
    builder = builder or build_live_payload
    try:
        return builder(), False
    except RuntimeError as error:
        if not output.exists():
            raise
        previous = json.loads(output.read_text(encoding="utf-8"))
        coverage = previous.get("coverage", {})
        if not daily_coverage_is_acceptable(
            int(coverage.get("available", 0)),
            int(coverage.get("total", 0)),
        ):
            raise error
        print(f"live snapshot unavailable; reusing {output}: {error}", flush=True)
        return previous, True


def main() -> None:
    parser = argparse.ArgumentParser(description="生成期货近5日收益分类榜静态数据")
    parser.add_argument("--output", type=Path, default=Path("site/data/latest.json"))
    args = parser.parse_args()
    payload, reused = build_or_reuse_payload(args.output)
    if not reused:
        write_payload(payload, args.output)
    print(
        f"status={'reused' if reused else 'generated'} "
        f"generated={payload['generatedAt']} data={payload['dataDate']} "
        f"coverage={payload['coverage']['available']}/{payload['coverage']['total']} "
        f"selected={len(payload['selectedSymbols'])}",
        flush=True,
    )


if __name__ == "__main__":
    main()
