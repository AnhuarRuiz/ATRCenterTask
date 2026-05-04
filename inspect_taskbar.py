import ctypes, ctypes.wintypes as wt

ctypes.windll.ole32.CoInitialize(None)

user32 = ctypes.windll.user32
taskbar  = user32.FindWindowW("Shell_TrayWnd", None)
rebar    = user32.FindWindowExW(taskbar, None, "ReBarWindow32", None)
task_sw  = user32.FindWindowExW(rebar,   None, "MSTaskSwWClass", None)
task_lst = user32.FindWindowExW(task_sw, None, "MSTaskListWClass", None)

def getrect(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

print("=" * 60)
r = getrect(task_sw)
print(f"taskbar  width : {getrect(taskbar)[2] - getrect(taskbar)[0]}")
print(f"task_sw  width : {r[2]-r[0]}  left={r[0]}")

try:
    import comtypes.client
    try:
        from comtypes.gen import UIAutomationClient as UIA
    except (ImportError, OSError):
        print("Generating UIAutomation bindings (first run only)...")
        comtypes.client.GetModule('UIAutomationCore.dll')
        from comtypes.gen import UIAutomationClient as UIA

    uia = comtypes.client.CreateObject(
        '{ff48dba4-60ef-4201-aa87-54103eef594e}',
        interface=UIA.IUIAutomation,
    )

    for label, hwnd in [("MSTaskListWClass", task_lst),
                        ("MSTaskSwWClass",   task_sw)]:
        print(f"\n--- UIA children of {label} ---")
        elem     = uia.ElementFromHandle(hwnd)
        cond     = uia.CreateTrueCondition()
        children = elem.FindAll(UIA.TreeScope_Children, cond)
        print(f"  count = {children.Length}")
        max_right = getrect(task_sw)[0]
        for i in range(children.Length):
            ch = children.GetElement(i)
            try:
                rect = ch.CurrentBoundingRectangle
                right = rect.right if hasattr(rect,'right') else rect[2]
                left  = rect.left  if hasattr(rect,'left')  else rect[0]
                name  = ch.CurrentName or ''
                print(f"    [{i}] {name!r:30s}  left={left}  right={right}  w={right-left}")
                if right > max_right:
                    max_right = right
            except Exception as e:
                print(f"    [{i}] rect error: {e}")
        content_w = max_right - getrect(task_sw)[0]
        print(f"  => content_width = {content_w}")

except ImportError:
    print("ERROR: comtypes not installed. Run: pip install comtypes")
except Exception as e:
    import traceback; traceback.print_exc()
