"""Receive right clicks in a color-keyed window's transparent area on Windows."""
import ctypes
from ctypes import wintypes
import sys
from collections import deque


def enable_windows_dpi():
    """Use the same screen pixel space for native mouse and window geometry."""
    if sys.platform == "win32":
        try:
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
            user.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
            user.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            pass


class NativeDrag:
    def __init__(self, user, hwnd, focus):
        self.user, self.hwnd, self.focus = user, hwnd, focus
        self.origin = None

    def handle(self, kind, x, y):
        if kind == "start":
            rect = wintypes.RECT()
            if not self.user.GetWindowRect(self.hwnd, ctypes.byref(rect)):
                return
            width, height = rect.right - rect.left, rect.bottom - rect.top
            self.origin = (x, y, rect.left, rect.top, width, height,
                           x >= rect.right - 8 or y >= rect.bottom - 6)
            self.focus()
            return
        if self.origin is None:
            return
        sx, sy, left, top, width, height, resizing = self.origin
        dx, dy = x - sx, y - sy
        if resizing:
            width, height = max(160, width + dx), max(24, height + dy)
        else:
            left, top = left + dx, top + dy
        # Absolute position from the initial press, never from a Configure event.
        self.user.SetWindowPos(self.hwnd, None, left, top, width, height, 0x0014)
        if kind == "end":
            self.origin = None


class RightClickCapture:
    def __init__(self, root, on_click, on_drag=None):
        self.root = root
        self.on_click = on_click
        self.pending = None
        self.pressed = False
        self.left_pressed = False
        self.on_drag = on_drag
        self.drag_events = deque()
        self.hook = None
        self.job = None
        if sys.platform != "win32":
            return
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        user = self.user
        result = ctypes.c_ssize_t
        self.callback_type = ctypes.WINFUNCTYPE(result, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        class MouseData(ctypes.Structure):
            _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t)]

        self.mouse_data = MouseData
        user.SetWindowsHookExW.argtypes = [ctypes.c_int, self.callback_type, wintypes.HINSTANCE, wintypes.DWORD]
        user.SetWindowsHookExW.restype = wintypes.HANDLE
        user.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user.CallNextHookEx.restype = result
        user.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        user.UnhookWindowsHookEx.restype = wintypes.BOOL
        user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user.GetAncestor.restype = wintypes.HWND
        user.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        user.GetWindow.restype = wintypes.HWND
        user.IsWindowVisible.argtypes = [wintypes.HWND]
        user.IsWindowVisible.restype = wintypes.BOOL
        user.IsIconic.argtypes = [wintypes.HWND]
        user.IsIconic.restype = wintypes.BOOL
        user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user.GetWindowRect.restype = wintypes.BOOL
        user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user.SetWindowPos.restype = wintypes.BOOL
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel.GetModuleHandleW.restype = wintypes.HMODULE
        root.update_idletasks()
        self.hwnd = user.GetAncestor(root.winfo_id(), 2)  # GA_ROOT
        self.callback = self.callback_type(self._handle)
        self.hook = user.SetWindowsHookExW(14, self.callback, kernel.GetModuleHandleW(None), 0)
        if not self.hook:
            raise ctypes.WinError(ctypes.get_last_error())
        root.bind("<Destroy>", self._destroy, add="+")
        self.job = root.after(25, self._poll)

    def _contains(self, hwnd, x, y):
        rect = wintypes.RECT()
        return (self.user.IsWindowVisible(hwnd) and not self.user.IsIconic(hwnd)
                and self.user.GetWindowRect(hwnd, ctypes.byref(rect))
                and rect.left <= x < rect.right and rect.top <= y < rect.bottom)

    def _available(self, x, y):
        if not self._contains(self.hwnd, x, y):
            return False
        # Do not steal right clicks from menus, dialogs or other windows above us.
        window = self.user.GetWindow(self.hwnd, 3)  # GW_HWNDPREV
        while window:
            if self._contains(window, x, y):
                return False
            window = self.user.GetWindow(window, 3)
        return True

    def _handle(self, code, message, address):
        try:
            if code >= 0 and message in (0x200, 0x201, 0x202, 0x204, 0x205):
                point = ctypes.cast(address, ctypes.POINTER(self.mouse_data)).contents.pt
                if self.on_drag:
                    if message == 0x201 and self._available(point.x, point.y):
                        self.left_pressed = True
                        self.drag_events.append(("start", point.x, point.y))
                        return 1
                    if self.left_pressed and message in (0x200, 0x202):
                        kind = "end" if message == 0x202 else "move"
                        if kind == "move" and self.drag_events and self.drag_events[-1][0] == "move":
                            self.drag_events.pop()
                        self.drag_events.append((kind, point.x, point.y))
                        if kind == "end":
                            self.left_pressed = False
                            return 1
                        # Suppressing WM_MOUSEMOVE freezes the system cursor. The
                        # coordinates then oscillate near the press point. Observe
                        # movement, but let Windows update its cursor normally.
                if message == 0x204 and self._available(point.x, point.y):
                    self.pressed = True
                    return 1
                if message == 0x205 and self.pressed:
                    self.pressed = False
                    self.pending = (point.x, point.y)
                    return 1
        except Exception:
            # Never propagate a Python error across a native callback boundary.
            self.pressed = False
            self.left_pressed = False
        return self.user.CallNextHookEx(self.hook, code, message, address)

    def _poll(self):
        self.job = self.root.after(25, self._poll)
        while self.drag_events:
            self.on_drag(*self.drag_events.popleft())
        if self.pending is not None:
            point, self.pending = self.pending, None
            self.on_click(*point)

    def _destroy(self, event):
        if event.widget is self.root:
            self.close()

    def close(self):
        if self.hook:
            self.user.UnhookWindowsHookEx(self.hook)
            self.hook = None
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
