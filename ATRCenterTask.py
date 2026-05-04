import sys
import os
import threading
import time
import winreg
import ctypes
import ctypes.wintypes as wintypes
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

APP_NAME = "ATRCenterTask"

SWP_NOSIZE         = 0x0001
SWP_NOZORDER       = 0x0004
SWP_NOACTIVATE     = 0x0010
SWP_NOSENDCHANGING = 0x0400
SWP_ASYNCWINDOWPOS = 0x4000

WINEVENT_OUTOFCONTEXT      = 0x0000
EVENT_SYSTEM_FOREGROUND    = 0x0003
EVENT_SYSTEM_MINIMIZESTART = 0x0016
EVENT_SYSTEM_MINIMIZEEND   = 0x0017
EVENT_OBJECT_DESTROY       = 0x8001
OBJID_WINDOW               = 0

_user32   = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_ole32    = ctypes.windll.ole32

_paused           = False
_running          = True
_reposition_event = threading.Event()
_hook_thread_id   = 0

_UIA_TreeScope_Children = 0x2


def _rect(hwnd):
    r = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

def _find(parent, cls):
    if parent is None:
        return _user32.FindWindowW(cls, None)
    return _user32.FindWindowExW(parent, None, cls, None)


def _single_instance():
    _kernel32.CreateMutexW(None, True, APP_NAME)
    if _kernel32.GetLastError() == 183:
        sys.exit(0)

def _set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            _user32.SetProcessDPIAware()
        except Exception:
            pass

def _hide_console():
    hwnd = _kernel32.GetConsoleWindow()
    if hwnd:
        _user32.ShowWindow(hwnd, 0)

def _add_to_startup():
    exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    value = f'"{exe}"'
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, value)
    except OSError:
        pass


def _get_uia():
    if hasattr(_get_uia, '_obj'):
        return _get_uia._obj
    try:
        import comtypes.client
        try:
            from comtypes.gen import UIAutomationClient as UIA
        except (ImportError, OSError):
            if not getattr(sys, 'frozen', False):
                comtypes.client.GetModule('UIAutomationCore.dll')
                from comtypes.gen import UIAutomationClient as UIA
            else:
                _get_uia._obj = None
                return None
        uia = comtypes.client.CreateObject(
            '{ff48dba4-60ef-4201-aa87-54103eef594e}',
            interface=UIA.IUIAutomation,
        )
        _get_uia._obj = uia
        _get_uia._UIA = UIA
        return uia
    except Exception:
        _get_uia._obj = None
        return None


def _measure_content_width(task_sw, task_sw_rect):
    base_left = task_sw_rect[0]

    try:
        uia = _get_uia()
        if uia is None:
            return 0
        UIA = _get_uia._UIA

        container = _find(task_sw, "MSTaskListWClass") or task_sw
        elem = uia.ElementFromHandle(container)
        if elem is None:
            return 0

        cond     = uia.CreateTrueCondition()
        children = elem.FindAll(UIA.TreeScope_Children, cond)
        if children is None or children.Length == 0:
            return 0

        total = children.Length
        valid = []

        for i in range(total):
            try:
                r  = children.GetElement(i).CurrentBoundingRectangle
                l  = int(r.left)  if hasattr(r, 'left')  else int(r[0])
                rt = int(r.right) if hasattr(r, 'right') else int(r[2])
                if rt > l >= 0:
                    valid.append((l, rt))
            except Exception:
                pass

        if not valid:
            return 0

        if len(valid) == total:
            return max(0, max(rt for _, rt in valid) - base_left)

        avg_w = sum(rt - l for l, rt in valid) / len(valid)
        return max(0, int(round(total * avg_w)))

    except Exception:
        return 0


def _animate_to(task_sw, from_x, to_x, y):
    delta = to_x - from_x
    if abs(delta) < 2:
        return
    steps = 12
    step_ms = 0.015
    for i in range(1, steps + 1):
        t = i / steps
        ease = t * (2 - t)
        x = int(round(from_x + delta * ease))
        _user32.SetWindowPos(
            task_sw, None, x, y, 0, 0,
            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOSENDCHANGING | SWP_ASYNCWINDOWPOS,
        )
        time.sleep(step_ms)


def _center_taskbar():
    taskbar = _find(None, "Shell_TrayWnd")
    if not taskbar:
        return

    tb = _rect(taskbar)
    taskbar_width = tb[2] - tb[0]

    rebar = _find(taskbar, "ReBarWindow32")
    if not rebar:
        return
    rb = _rect(rebar)

    task_sw = _find(rebar, "MSTaskSwWClass")
    if not task_sw:
        return
    tsw = _rect(task_sw)

    toolbar_w = _measure_content_width(task_sw, tsw)
    if toolbar_w <= 0:
        return

    left_margin = int((taskbar_width - toolbar_w) / 2)

    target_x = left_margin - (rb[0] - tb[0])
    current_x = tsw[0] - rb[0]
    y = tsw[1] - rb[1]

    _animate_to(task_sw, current_x, target_x, y)


_WinEventProc = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
    wintypes.LONG,   wintypes.LONG,  wintypes.DWORD, wintypes.DWORD,
)

def _on_win_event(hHook, event, hwnd, idObject, idChild, tid, evt_time):
    if event == EVENT_OBJECT_DESTROY and idObject != OBJID_WINDOW:
        return
    _reposition_event.set()

_win_event_proc = _WinEventProc(_on_win_event)


def _hook_thread_func():
    global _hook_thread_id
    _hook_thread_id = _kernel32.GetCurrentThreadId()

    hooks = []
    for evmin, evmax in [
        (EVENT_SYSTEM_FOREGROUND,    EVENT_SYSTEM_FOREGROUND),
        (EVENT_SYSTEM_MINIMIZESTART, EVENT_SYSTEM_MINIMIZEEND),
        (EVENT_OBJECT_DESTROY,       EVENT_OBJECT_DESTROY),
    ]:
        h = _user32.SetWinEventHook(
            evmin, evmax, None, _win_event_proc, 0, 0, WINEVENT_OUTOFCONTEXT,
        )
        if h:
            hooks.append(h)

    msg = wintypes.MSG()
    while _running:
        ret = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret <= 0:
            break
        _user32.TranslateMessage(ctypes.byref(msg))
        _user32.DispatchMessageW(ctypes.byref(msg))

    for h in hooks:
        _user32.UnhookWinEvent(h)


def _worker_func():
    _ole32.CoInitialize(None)
    while _running:
        _reposition_event.wait(timeout=2.0)
        if not _running:
            break
        time.sleep(0.05)
        _reposition_event.clear()
        if not _paused:
            try:
                _center_taskbar()
            except Exception:
                pass
    _ole32.CoUninitialize()


def _make_icon():
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base, "logo", "logo.png")
    if os.path.exists(icon_path):
        return Image.open(icon_path).convert("RGBA").resize((64, 64))
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 63, 63], radius=8, fill=(20, 20, 28, 240))
    blue  = (0, 140, 255, 255)
    bar_h, gap, y0 = 7, 6, 11
    for i, w in enumerate([48, 36, 24]):
        x = (size - w) // 2
        y = y0 + i * (bar_h + gap)
        draw.rectangle([x, y, x + w - 1, y + bar_h - 1], fill=blue)
    return img

def _toggle_label(menu_item):
    return "Reanudar" if _paused else "Pausar"

def _on_toggle(icon, menu_item):
    global _paused
    _paused = not _paused
    icon.title = f"{APP_NAME} — {'Pausado' if _paused else 'Activo'}"
    icon.update_menu()

def _on_exit(icon, menu_item):
    global _running
    _running = False
    _reposition_event.set()
    tid = _hook_thread_id
    if tid:
        _user32.PostThreadMessageW(tid, 0x0012, 0, 0)
    icon.stop()


def main():
    _single_instance()
    _set_dpi_aware()
    _hide_console()
    _add_to_startup()

    _reposition_event.set()
    threading.Thread(target=_hook_thread_func, daemon=True).start()
    threading.Thread(target=_worker_func,      daemon=True).start()

    pystray.Icon(
        APP_NAME,
        _make_icon(),
        f"{APP_NAME} — Activo",
        pystray.Menu(
            item(_toggle_label, _on_toggle),
            item("Exit",        _on_exit),
        ),
    ).run()


if __name__ == "__main__":
    main()
