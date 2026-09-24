from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Asia/Shanghai")


def snapshot_needs_update(
    payload: dict[str, Any],
    event_name: str,
    now: datetime | None = None,
) -> bool:
    if event_name != "schedule":
        return True
    coverage = payload.get("coverage", {})
    available = int(coverage.get("available", 0))
    total = int(coverage.get("total", 0))
    today = (now or datetime.now(TZ)).astimezone(TZ).date().isoformat()
    return not (
        total > 0
        and available == total
        and payload.get("dataDate") == today
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="判断是否需要更新期货行情快照")
    parser.add_argument("--output", type=Path, default=Path("site/data/latest.json"))
    args = parser.parse_args()
    payload = (
        json.loads(args.output.read_text(encoding="utf-8"))
        if args.output.exists()
        else {}
    )
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    needs_update = snapshot_needs_update(payload, event_name)
    result = str(needs_update).lower()
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"needs_update={result}\n")
    coverage = payload.get("coverage", {})
    print(
        f"snapshot_date={payload.get('dataDate', 'missing')} "
        f"coverage={coverage.get('available', 0)}/{coverage.get('total', 0)} "
        f"needs_update={result}",
        flush=True,
    )


if __name__ == "__main__":
    main()
