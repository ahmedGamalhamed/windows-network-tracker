from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
_IS_64 = ctypes.sizeof(ctypes.c_void_p) == 8
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
ERROR_ALREADY_EXISTS = 183
MONITOR_DEFAULTTONEAREST = 2


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


@dataclass
class TaskbarGeometry:
    left: int
    top: int
    right: int
    bottom: int
    notify_left: int
    notify_right: int
    orientation: str
    thickness: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def set_dpi_aware() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def hwnd_from_widget(widget) -> int:
    widget.update_idletasks()
    child = int(widget.winfo_id())
    parent = user32.GetParent(child)
    return int(parent or child)


def get_exstyle(hwnd: int) -> int:
    if _IS_64:
        return user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    return user32.GetWindowLongW(hwnd, GWL_EXSTYLE)


def set_exstyle(hwnd: int, style: int) -> None:
    if _IS_64:
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
    else:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def configure_overlay_window(hwnd: int, click_through: bool = False, topmost: bool = True) -> None:
    style = get_exstyle(hwnd)
    style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED
    if topmost:
        style |= WS_EX_TOPMOST
    if click_through:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    set_exstyle(hwnd, style)
    flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
    insert_after = HWND_TOPMOST if topmost else 0
    user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags)
    try:
        preference = ctypes.c_int(DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(preference), ctypes.sizeof(preference))
    except Exception:
        pass


def keep_topmost(hwnd: int) -> None:
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def _window_rect(class_name: str, parent: int | None = None) -> RECT | None:
    if parent:
        hwnd = user32.FindWindowExW(parent, None, class_name, None)
    else:
        hwnd = user32.FindWindowW(class_name, None)
    if not hwnd:
        return None
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return rect


def get_taskbar() -> TaskbarGeometry | None:
    tray = _window_rect("Shell_TrayWnd")
    if tray is None:
        return None
    notify = None
    tray_hwnd = user32.FindWindowW("Shell_TrayWnd", None)
    for class_name in ("TrayNotifyWnd", "SystemTray_Main"):
        notify = _window_rect(class_name, tray_hwnd)
        if notify:
            break
    width = tray.right - tray.left
    height = tray.bottom - tray.top
    if width >= height:
        orientation = "top" if tray.top <= 40 else "bottom"
        thickness = height
    else:
        orientation = "left" if tray.left <= 40 else "right"
        thickness = width
    notify_left = notify.left if notify else tray.right - 180
    notify_right = notify.right if notify else tray.right
    return TaskbarGeometry(
        left=tray.left,
        top=tray.top,
        right=tray.right,
        bottom=tray.bottom,
        notify_left=notify_left,
        notify_right=notify_right,
        orientation=orientation,
        thickness=thickness,
    )


def work_area() -> tuple[int, int, int, int]:
    rect = RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


def is_foreground_fullscreen() -> bool:
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    try:
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        if class_name.value in {"Progman", "WorkerW", "Shell_TrayWnd", "Windows.UI.Core.CoreWindow"}:
            return False
    except Exception:
        pass
    window = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(window)):
        return False
    monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    mon = info.rcMonitor
    return (
        window.left <= mon.left
        and window.top <= mon.top
        and window.right >= mon.right
        and window.bottom >= mon.bottom
        and (window.right - window.left) >= (mon.right - mon.left - 4)
        and (window.bottom - window.top) >= (mon.bottom - mon.top - 4)
    )


def single_instance(name: str = "NetSpeedTraySingletonMutex") -> bool:
    handle = kernel32.CreateMutexW(None, False, name)
    if not handle:
        return True
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def apps_use_light_theme() -> bool:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return bool(value)
    except OSError:
        return False
