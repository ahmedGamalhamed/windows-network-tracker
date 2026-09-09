from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .formatting import today_iso
from .settings import APP_DATA_DIR


USAGE_PATH = APP_DATA_DIR / "usage.json"


@dataclass
class DayUsage:
    day: str
    down: int = 0
    up: int = 0

    @property
    def total(self) -> int:
        return self.down + self.up


class UsageStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or USAGE_PATH
        self.days: dict[str, dict[str, int]] = {}
        self.quota_notified_on: str = ""
        self._dirty = False
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        days = data.get("days", {})
        cleaned: dict[str, dict[str, int]] = {}
        if isinstance(days, dict):
            for key, value in days.items():
                if not isinstance(value, dict):
                    continue
                cleaned[str(key)] = {
                    "down": int(value.get("down", 0) or 0),
                    "up": int(value.get("up", 0) or 0),
                }
        self.days = cleaned
        self.quota_notified_on = str(data.get("quota_notified_on", "") or "")

    def migrate_from_settings(self, day: str, down: int, up: int) -> None:
        if not day or (down <= 0 and up <= 0):
            return
        current = self.days.get(day, {"down": 0, "up": 0})
        if current["down"] < down or current["up"] < up:
            self.days[day] = {
                "down": max(current["down"], int(down)),
                "up": max(current["up"], int(up)),
            }
            self._dirty = True
            self.save(force=True)

    def add(self, down: int, up: int) -> DayUsage:
        today = today_iso()
        entry = self.days.setdefault(today, {"down": 0, "up": 0})
        entry["down"] += max(0, int(down))
        entry["up"] += max(0, int(up))
        self._dirty = True
        return DayUsage(today, entry["down"], entry["up"])

    def today(self) -> DayUsage:
        today = today_iso()
        entry = self.days.get(today, {"down": 0, "up": 0})
        return DayUsage(today, entry["down"], entry["up"])

    def get(self, day: str) -> DayUsage:
        entry = self.days.get(day, {"down": 0, "up": 0})
        return DayUsage(day, entry["down"], entry["up"])

    def range_days(self, start: date, end: date) -> list[DayUsage]:
        rows = []
        cursor = start
        while cursor <= end:
            iso = cursor.isoformat()
            rows.append(self.get(iso))
            cursor += timedelta(days=1)
        return rows

    def last_n_days(self, count: int, include_empty: bool = True) -> list[DayUsage]:
        end = date.today()
        start = end - timedelta(days=max(1, count) - 1)
        if include_empty:
            return self.range_days(start, end)
        rows = []
        for iso, entry in sorted(self.days.items()):
            try:
                day = date.fromisoformat(iso)
            except ValueError:
                continue
            if start <= day <= end:
                rows.append(DayUsage(iso, entry["down"], entry["up"]))
        return rows

    def month_days(self, year: int | None = None, month: int | None = None) -> list[DayUsage]:
        today = date.today()
        year = year or today.year
        month = month or today.month
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        end = min(end, today)
        return self.range_days(start, end)

    def all_days(self) -> list[DayUsage]:
        rows = []
        for iso in sorted(self.days):
            entry = self.days[iso]
            if entry["down"] or entry["up"]:
                rows.append(DayUsage(iso, entry["down"], entry["up"]))
        return rows

    def summarize(self, rows: list[DayUsage]) -> DayUsage:
        return DayUsage(
            day=rows[0].day if rows else today_iso(),
            down=sum(row.down for row in rows),
            up=sum(row.up for row in rows),
        )

    def prune(self, retention_days: int) -> None:
        if retention_days <= 0:
            return
        cutoff = (date.today() - timedelta(days=retention_days)).isoformat()
        keep = {day: value for day, value in self.days.items() if day >= cutoff}
        if len(keep) != len(self.days):
            self.days = keep
            self._dirty = True

    def reset_today(self) -> None:
        today = today_iso()
        self.days[today] = {"down": 0, "up": 0}
        self._dirty = True
        self.save(force=True)

    def clear_all(self) -> None:
        self.days = {}
        self.quota_notified_on = ""
        self._dirty = True
        self.save(force=True)

    def save(self, force: bool = False, min_interval: float = 10.0) -> None:
        if not self._dirty and not force:
            return
        now = datetime.now().timestamp()
        last = getattr(self, "_last_save", 0.0)
        if not force and now - last < min_interval:
            return
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "days": self.days,
            "quota_notified_on": self.quota_notified_on,
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self._last_save = now
        self._dirty = False

    def export_csv(self, path: str | Path) -> None:
        target = Path(path)
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "download_bytes", "upload_bytes", "total_bytes"])
            for row in self.all_days() or [self.today()]:
                writer.writerow([row.day, row.down, row.up, row.total])

    def cap_value(self, today: DayUsage, metric: str) -> int:
        if metric == "download":
            return today.down
        if metric == "upload":
            return today.up
        return today.total
