from __future__ import annotations

import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import psutil

from .settings import Settings, is_virtual_adapter, is_vpn_adapter
from .usage import UsageStore


@dataclass
class SpeedSample:
    download: float = 0.0
    upload: float = 0.0
    adapter: str = "All"
    ip_address: str = ""
    link_mbps: float = 0.0
    down_util: float = 0.0
    up_util: float = 0.0
    ping_ms: float | None = None
    timestamp: float = field(default_factory=time.time)


class NetworkMonitor:
    def __init__(self, settings: Settings, usage: UsageStore | None = None) -> None:
        self.settings = settings
        self.usage = usage or UsageStore()
        self.latest = SpeedSample()
        self.history: deque[SpeedSample] = deque(maxlen=600)
        self._prev: dict[str, tuple[int, int]] = {}
        self._prev_time = time.perf_counter()
        self._lock = threading.Lock()
        self._ping_ms: float | None = None
        self._ping_thread_started = False
        self._stop = threading.Event()
        self.session_down = 0
        self.session_up = 0
        self.usage.migrate_from_settings(settings.daily_date, settings.daily_down_bytes, settings.daily_up_bytes)
        self._sync_daily_from_store()

    def update_settings(self, settings: Settings) -> None:
        self.settings = settings
        self._sync_daily_from_store()
        self._resize_history()

    def _resize_history(self) -> None:
        interval = max(0.2, self.settings.update_interval_ms / 1000)
        maxlen = max(30, int(self.settings.graph_history_seconds / interval) + 5)
        old = list(self.history)
        self.history = deque(old[-maxlen:], maxlen=maxlen)

    def _sync_daily_from_store(self) -> None:
        today = self.usage.today()
        self.settings.daily_date = today.day
        self.settings.daily_down_bytes = today.down
        self.settings.daily_up_bytes = today.up
        self.usage.prune(self.settings.usage_retention_days)

    def list_adapters(self) -> list[str]:
        stats = psutil.net_if_stats()
        names = []
        for name, info in stats.items():
            if not info.isup:
                continue
            if not self._include_adapter(name):
                continue
            names.append(name)
        return sorted(names)

    def _include_adapter(self, name: str) -> bool:
        if self.settings.ignore_virtual and is_virtual_adapter(name):
            if self.settings.include_vpn and is_vpn_adapter(name):
                return True
            return False
        return True

    def _selected_adapters(self) -> list[str]:
        pernic = psutil.net_io_counters(pernic=True)
        available = [name for name in pernic if self._include_adapter(name)]
        if self.settings.adapter_mode == "specific" and self.settings.adapter_name in pernic:
            return [self.settings.adapter_name]
        if self.settings.adapter_mode == "all":
            return available
        return available

    def _adapter_ip(self, name: str) -> str:
        try:
            addrs = psutil.net_if_addrs().get(name, [])
        except Exception:
            return ""
        for addr in addrs:
            if addr.family.name == "AF_INET" and not addr.address.startswith("127."):
                return addr.address
        return ""

    def _link_speed(self, name: str) -> float:
        try:
            stats = psutil.net_if_stats().get(name)
            return float(stats.speed) if stats and stats.speed else 0.0
        except Exception:
            return 0.0

    def poll(self) -> SpeedSample:
        now = time.perf_counter()
        elapsed = max(0.05, now - self._prev_time)
        counters = psutil.net_io_counters(pernic=True)
        adapters = self._selected_adapters()

        deltas: list[tuple[str, int, int]] = []
        for name in adapters:
            current = counters.get(name)
            if current is None:
                continue
            recv, sent = int(current.bytes_recv), int(current.bytes_sent)
            prev = self._prev.get(name)
            self._prev[name] = (recv, sent)
            if prev is None:
                continue
            down = max(0, recv - prev[0])
            up = max(0, sent - prev[1])
            deltas.append((name, down, up))

        self._prev_time = now
        if not deltas:
            sample = SpeedSample(adapter="Waiting...", ping_ms=self._ping_ms)
            with self._lock:
                self.latest = sample
            self._maybe_start_ping()
            return sample

        if self.settings.adapter_mode == "auto":
            name, down, up = max(deltas, key=lambda item: item[1] + item[2])
            total_down, total_up = down, up
            adapter = name
        else:
            total_down = sum(item[1] for item in deltas)
            total_up = sum(item[2] for item in deltas)
            adapter = "All adapters" if self.settings.adapter_mode == "all" else adapters[0]

        down_bps = total_down / elapsed
        up_bps = total_up / elapsed
        self.session_down += total_down
        self.session_up += total_up
        self.settings.session_down_bytes = self.session_down
        self.settings.session_up_bytes = self.session_up
        if self.settings.persist_daily_totals:
            today = self.usage.add(total_down, total_up)
            self.settings.daily_date = today.day
            self.settings.daily_down_bytes = today.down
            self.settings.daily_up_bytes = today.up

        link = self._link_speed(adapter) if adapter not in {"All adapters", "Waiting…"} else 0.0
        capacity = (link * 1_000_000 / 8) if link else 0.0
        sample = SpeedSample(
            download=down_bps,
            upload=up_bps,
            adapter=adapter,
            ip_address=self._adapter_ip(adapter) if adapter not in {"All adapters", "Waiting…"} else "",
            link_mbps=link,
            down_util=(down_bps / capacity * 100) if capacity else 0.0,
            up_util=(up_bps / capacity * 100) if capacity else 0.0,
            ping_ms=self._ping_ms,
        )
        with self._lock:
            self.latest = sample
            self.history.append(sample)
        self._maybe_start_ping()
        return sample

    def history_points(self) -> list[SpeedSample]:
        with self._lock:
            return list(self.history)

    def _maybe_start_ping(self) -> None:
        if self._ping_thread_started or not (self.settings.ping_enabled or self.settings.overlay_show_ping):
            return
        self._ping_thread_started = True
        thread = threading.Thread(target=self._ping_loop, daemon=True)
        thread.start()

    def _ping_loop(self) -> None:
        while not self._stop.is_set():
            if self.settings.ping_enabled or self.settings.overlay_show_ping:
                self._ping_ms = _ping_host(self.settings.ping_host, timeout_ms=1000)
            time.sleep(max(1.0, self.settings.ping_interval_ms / 1000))

    def stop(self) -> None:
        self._stop.set()
        self.usage.save(force=True)

    def reset_session(self) -> None:
        self.session_down = 0
        self.session_up = 0
        self.settings.session_down_bytes = 0
        self.settings.session_up_bytes = 0

    def reset_today_usage(self) -> None:
        self.usage.reset_today()
        self._sync_daily_from_store()


def _ping_host(host: str, timeout_ms: int = 1000) -> float | None:
    if not host.strip():
        return None
    try:
        completed = subprocess.run(
            ["ping", "-n", "1", "-w", str(timeout_ms), host.strip()],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=max(2.0, timeout_ms / 1000 + 1),
        )
        match = re.search(r"time[=<]\s*(\d+)\s*ms", completed.stdout, re.IGNORECASE)
        if match:
            return float(match.group(1))
    except Exception:
        return None
    return None
