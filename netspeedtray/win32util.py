from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
_IS_64 = ctypes.sizeof(ctypes.c_void_p) == 8

GWL_EXSTYLE = -20
GWL_STYLE = -16
GWLP_HWNDPARENT = -8
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_CLIPSIBLINGS = 0x04000000
WS_VISIBLE = 0x10000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
HWND_TOP = 0
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
LWA_COLORKEY = 0x00000001
LWA_ALPHA = 0x00000002
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_DONOTROUND = 1
DWMWCP_ROUND = 2
GA_ROOT = 2
ERROR_ALREADY_EXISTS = 183
MONITOR_DEFAULTTONEAREST = 2
TRANSPARENT_KEY_RGB = (255, 0, 255)
TRANSPARENT_KEY = "#FF00FF"


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


user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
user32.SetParent.restype = wintypes.HWND
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wintypes.HWND
user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
user32.MoveWindow.restype = wintypes.BOOL
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
user32.ScreenToClient.restype = wintypes.BOOL
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowPos.restype = wintypes.BOOL
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.GetDpiForWindow.argtypes = [wintypes.HWND]
user32.GetDpiForWindow.restype = ctypes.c_uint
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.GetPixel.restype = wintypes.COLORREF


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
    hwnd: int = 0

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


def window_hwnd(widget) -> int:
    widget.update_idletasks()
    child = int(widget.winfo_id())
    parent = int(user32.GetParent(child) or 0)
    return parent or child


def win32_to_tk(widget, x: int, y: int) -> tuple[int, int]:
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    tk_w = max(1, int(widget.winfo_screenwidth()))
    tk_h = max(1, int(widget.winfo_screenheight()))
    if screen_w <= 0 or screen_h <= 0:
        return int(x), int(y)
    return int(x * tk_w / screen_w), int(y * tk_h / screen_h)


def hwnd_from_widget(widget) -> int:
    return window_hwnd(widget)


def get_style(hwnd: int) -> int:
    if _IS_64:
        return int(user32.GetWindowLongPtrW(hwnd, GWL_STYLE))
    return int(user32.GetWindowLongW(hwnd, GWL_STYLE))


def set_style(hwnd: int, style: int) -> None:
    if _IS_64:
        user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
    else:
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)


def get_exstyle(hwnd: int) -> int:
    if _IS_64:
        return int(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE))
    return int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))


def set_exstyle(hwnd: int, style: int) -> None:
    if _IS_64:
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style)
    else:
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def taskbar_hwnd() -> int:
    return taskbar_host_hwnd()


def taskbar_host_hwnd() -> int:
    tray = int(user32.FindWindowW("Shell_TrayWnd", None) or 0)
    if not tray:
        return 0
    for class_name in ("ReBarWindow32", "Windows.UI.Composition.DesktopWindowContentBridge"):
        child = user32.FindWindowExW(tray, None, class_name, None)
        if child:
            return int(child)
    return tray


def screen_to_client(hwnd: int, x: int, y: int) -> tuple[int, int]:
    point = POINT(int(x), int(y))
    user32.ScreenToClient(hwnd, ctypes.byref(point))
    return int(point.x), int(point.y)


def is_windows_11() -> bool:
    try:
        return sys.getwindowsversion().build >= 22000
    except Exception:
        return True


def apply_layered_style(hwnd: int, alpha: float = 1.0, transparent_background: bool = False, topmost: bool = True) -> None:
    style = get_exstyle(hwnd)
    style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    if topmost:
        style |= WS_EX_TOPMOST
    else:
        style &= ~WS_EX_TOPMOST
    set_exstyle(hwnd, style)
    byte_alpha = max(1, min(255, int(alpha * 255)))
    # Never use a color key: it punches out ClearType fringes and makes text look blurry.
    user32.SetLayeredWindowAttributes(hwnd, 0, byte_alpha, LWA_ALPHA)


def configure_taskbar_item(hwnd: int, click_through: bool = False, transparent_background: bool = False, alpha: float = 1.0, topmost: bool = True) -> None:
    style = get_exstyle(hwnd)
    style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED
    if topmost:
        style |= WS_EX_TOPMOST
    else:
        style &= ~WS_EX_TOPMOST
    if click_through:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    set_exstyle(hwnd, style)
    apply_layered_style(hwnd, alpha=alpha, transparent_background=transparent_background, topmost=topmost)
    try:
        preference = ctypes.c_int(DWMWCP_DONOTROUND)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(preference), ctypes.sizeof(preference))
    except Exception:
        pass


def detach_from_taskbar(hwnd: int) -> None:
    if not hwnd or not user32.IsWindow(hwnd):
        return
    parent = int(user32.GetParent(hwnd) or 0)
    if parent:
        user32.SetParent(hwnd, 0)
    style = get_style(hwnd)
    style &= ~WS_CHILD
    style |= WS_POPUP | WS_VISIBLE
    set_style(hwnd, style)
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
    )


def place_on_screen(hwnd: int, x: int, y: int, width: int, height: int) -> None:
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        int(x),
        int(y),
        int(width),
        int(height),
        SWP_SHOWWINDOW | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )


def keep_topmost(hwnd: int) -> None:
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def embed_in_taskbar(hwnd: int, parent: int | None = None) -> bool:
    parent = int(parent or taskbar_hwnd())
    if not hwnd or not parent or not user32.IsWindow(hwnd) or not user32.IsWindow(parent):
        return False
    if int(user32.GetParent(hwnd)) == parent:
        return True
    if _IS_64:
        user32.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, 0)
    else:
        user32.SetWindowLongW(hwnd, GWLP_HWNDPARENT, 0)
    style = get_style(hwnd)
    style |= WS_CHILD | WS_CLIPSIBLINGS | WS_VISIBLE
    style &= ~WS_POPUP
    set_style(hwnd, style)
    user32.SetParent(hwnd, parent)
    user32.SetWindowPos(
        hwnd,
        HWND_TOP,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
    )
    return int(user32.GetParent(hwnd)) == parent


def place_in_parent(hwnd: int, x: int, y: int, width: int, height: int) -> None:
    user32.MoveWindow(hwnd, int(x), int(y), int(width), int(height), True)
    user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)


def configure_overlay_window(hwnd: int, click_through: bool = False, topmost: bool = True) -> None:
    configure_taskbar_item(hwnd, click_through=click_through, transparent_background=False, alpha=1.0, topmost=topmost)


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
    notify_left = notify.left if notify else tray.right - 380
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
        hwnd=int(tray_hwnd or 0),
    )


def sample_taskbar_color() -> str:
    fallback = "#F3F3F3" if apps_use_light_theme() else "#202020"
    tray = user32.FindWindowW("Shell_TrayWnd", None)
    if not tray:
        return fallback
    rect = RECT()
    if not user32.GetWindowRect(tray, ctypes.byref(rect)):
        return fallback
    width = max(1, rect.right - rect.left)
    height = max(1, rect.bottom - rect.top)
    hdc = user32.GetDC(tray)
    if not hdc:
        return fallback
    try:
        samples = [
            gdi32.GetPixel(hdc, max(8, width - 420), height // 2),
            gdi32.GetPixel(hdc, max(8, width // 2), height // 2),
            gdi32.GetPixel(hdc, 24, height // 2),
        ]
    finally:
        user32.ReleaseDC(tray, hdc)
    valid = [color for color in samples if color not in (-1, 0xFFFFFFFF)]
    if not valid:
        return fallback
    color = valid[0]
    red, green, blue = color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF
    if red < 8 and green < 8 and blue < 8 and not apps_use_light_theme():
        return "#202020"
    return f"#{red:02x}{green:02x}{blue:02x}"


def pixel_font_size(point_size: int, hwnd: int | None = None) -> int:
    dpi = 96
    try:
        if hwnd:
            dpi = int(user32.GetDpiForWindow(hwnd) or 96)
        else:
            dpi = int(ctypes.windll.user32.GetDpiForSystem())
    except Exception:
        dpi = 96
    return max(12, int(round(max(8, point_size) * dpi / 72.0)))


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
