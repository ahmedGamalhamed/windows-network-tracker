from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


APP_NAME = "NetSpeedTray"
APP_DATA_DIR = Path.home() / "AppData" / "Roaming" / APP_NAME
SETTINGS_PATH = APP_DATA_DIR / "settings.json"

VIRTUAL_ADAPTER_HINTS = (
    "loopback",
    "isatap",
    "teredo",
    "6to4",
    "vethernet",
    "hyper-v",
    "vmware",
    "virtualbox",
    "vbox",
    "virtual",
    "pseudo",
    "bluetooth",
    "wi-fi direct",
    "hosted network",
    "debug",
    "wsl",
    "docker",
    "npcap",
    "nordlynx",
    "wireguard",
    "tailscale",
    "zerotier",
    "hamachi",
    "tap-windows",
    "tap-win",
    "wintun",
    "kernel debug",
    "microsoft ip-https",
)

VPN_HINTS = (
    "vpn",
    "wireguard",
    "tailscale",
    "nordlynx",
    "zerotier",
    "hamachi",
    "openvpn",
    "wintun",
    "tap-windows",
    "tap-win",
    "cisco",
    "fortinet",
    "globalprotect",
    "anyconnect",
)


@dataclass
class Settings:
    start_with_windows: bool = False
    start_hidden: bool = True
    update_interval_ms: int = 1000
    adapter_mode: str = "auto"  # auto | all | specific
    adapter_name: str = ""
    ignore_virtual: bool = True
    include_vpn: bool = True

    show_tray: bool = True
    show_overlay: bool = True
    show_details_on_click: bool = True

    overlay_layout: str = "stacked"  # stacked | inline | compact
    overlay_dock: str = "taskbar-tray"  # taskbar-tray | taskbar-left | taskbar-center | taskbar-right | custom
    overlay_x: int = 0
    overlay_y: int = 0
    overlay_opacity: float = 1.0
    overlay_transparent_background: bool = True
    overlay_always_on_top: bool = False
    overlay_click_through: bool = False
    overlay_draggable: bool = True
    overlay_hide_fullscreen: bool = True
    overlay_lock_position: bool = False
    overlay_show_labels: bool = False
    overlay_show_arrows: bool = True
    overlay_show_adapter: bool = False
    overlay_show_totals: bool = False
    overlay_show_usage: bool = False
    overlay_show_ping: bool = False
    overlay_show_utilization: bool = False
    overlay_font_family: str = "Segoe UI"
    overlay_font_size: int = 11
    overlay_font_bold: bool = True
    overlay_padding_x: int = 10
    overlay_padding_y: int = 2
    overlay_gap: int = 6

    theme: str = "dark"  # dark | light | system
    color_download: str = "#3DDC97"
    color_upload: str = "#5B9DFF"
    color_background: str = "#151515"
    color_text: str = "#F4F4F4"
    color_muted: str = "#A0A0A0"
    color_border: str = "#2A2A2A"

    use_bits: bool = False
    unit_scale: str = "auto"  # auto | B | KB | MB | GB | TB
    binary_units: bool = True
    decimal_places: int = 1
    min_display_unit: str = "KB"

    tray_style: str = "arrows"  # text | arrows | bars | graph
    tray_show_units: bool = False

    graph_history_seconds: int = 60
    graph_fill: bool = True

    ping_enabled: bool = False
    ping_host: str = "1.1.1.1"
    ping_interval_ms: int = 3000

    alerts_enabled: bool = False
    alert_download_above_mbps: float = 0.0
    alert_upload_above_mbps: float = 0.0
    alert_download_below_kbps: float = 0.0
    alert_notify: bool = True

    persist_daily_totals: bool = True
    usage_retention_days: int = 365
    usage_daily_cap_gb: float = 0.0
    usage_cap_metric: str = "total"  # total | download | upload
    usage_cap_notify: bool = True
    daily_down_bytes: int = 0
    daily_up_bytes: int = 0
    daily_date: str = ""
    session_down_bytes: int = 0
    session_up_bytes: int = 0

    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("extra", None)
        return data

    @classmethod
    def from_dict(cls, data: dict | None) -> "Settings":
        if not data:
            return cls()
        known = {item.name for item in fields(cls)}
        kwargs = {key: value for key, value in data.items() if key in known and key != "extra"}
        settings = cls(**kwargs)
        return settings

    def copy(self) -> "Settings":
        return Settings.from_dict(deepcopy(self.to_dict()))

    def save(self) -> None:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "Settings":
        if not SETTINGS_PATH.exists():
            settings = cls()
            settings.save()
            return settings
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except Exception:
            return cls()


def is_virtual_adapter(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in VIRTUAL_ADAPTER_HINTS)


def is_vpn_adapter(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in VPN_HINTS)
