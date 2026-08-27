"""
Windows Input Controller using Win32 SendInput API (ctypes)
Supports:
- Relative mouse movement (for Pointer Lock API)
- Absolute mouse positioning
- Mouse buttons: Left, Right, Middle, Side Buttons (XBUTTON1=Back, XBUTTON2=Forward for Logitech M650)
- Vertical & Horizontal Mouse Wheel (discrete & smooth scrolling)
- Full Keyboard input with Virtual Key, ScanCode, and Unicode typing support
- Five-layer safety fail-safes (F12 Kill Switch, Disconnect Auto-Release, Bounds Clamping)
"""

import ctypes
from ctypes import wintypes
import time

# Win32 Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

# Mouse flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

# XButton flags (for M650 side buttons)
XBUTTON1 = 0x0001  # Browser Back
XBUTTON2 = 0x0002  # Browser Forward

# Keyboard flags
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

WHEEL_DELTA = 120

# Common Virtual Key Codes
VK_MAP = {
    'backspace': 0x08,
    'tab': 0x09,
    'enter': 0x0D,
    'shift': 0x10,
    'ctrl': 0x11,
    'control': 0x11,
    'alt': 0x12,
    'pause': 0x13,
    'capslock': 0x14,
    'esc': 0x1B,
    'escape': 0x1B,
    'space': 0x20,
    'pageup': 0x21,
    'pagedown': 0x22,
    'end': 0x23,
    'home': 0x24,
    'left': 0x25,
    'up': 0x26,
    'right': 0x27,
    'down': 0x28,
    'insert': 0x2D,
    'delete': 0x2E,
    'win': 0x5B,
    'meta': 0x5B,
    'f1': 0x70,
    'f2': 0x71,
    'f3': 0x72,
    'f4': 0x73,
    'f5': 0x74,
    'f6': 0x75,
    'f7': 0x76,
    'f8': 0x77,
    'f9': 0x78,
    'f10': 0x79,
    'f11': 0x7A,
    'f12': 0x7B,
}

# Win32 Structures
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION)
    ]

# Win32 Functions
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
shcore = ctypes.windll.shcore

try:
    shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

try:
    user32.SetProcessDpiAwarenessContext(-4)
except Exception:
    pass

SendInput = user32.SendInput
SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
SendInput.restype = wintypes.UINT

GetSystemMetrics = user32.GetSystemMetrics
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

class WindowsInputController:
    def __init__(self):
        hdc = user32.GetDC(0)
        DESKTOPHORZRES = 118
        DESKTOPVERTRES = 117
        self.screen_w = gdi32.GetDeviceCaps(hdc, DESKTOPHORZRES) or user32.GetSystemMetrics(0) or 2560
        self.screen_h = gdi32.GetDeviceCaps(hdc, DESKTOPVERTRES) or user32.GetSystemMetrics(1) or 1440
        user32.ReleaseDC(0, hdc)
        self.virt_w = self.screen_w
        self.virt_h = self.screen_h
        
        self.is_emergency_stopped = False
        self.pressed_mouse_buttons = set()
        self.pressed_keys = set()

    def emergency_stop(self):
        """Emergency Kill Switch: instantly release all inputs and block further input"""
        self.is_emergency_stopped = True
        self.release_all_inputs()
        print("\n[SAFETY ALERT] Emergency Stop triggered (F12)! Remote input is now LOCKED.")

    def resume_input(self):
        """Resume input after safety check"""
        self.is_emergency_stopped = False
        print("[SAFETY] Remote input resumed (F11).")

    def release_all_inputs(self):
        """Fail-Safe: Release all pressed mouse buttons and keys to prevent stuck inputs"""
        for btn in list(self.pressed_mouse_buttons):
            self.mouse_up(btn)
        self.pressed_mouse_buttons.clear()
        
        for vk in list(self.pressed_keys):
            self.key_up(vk)
        self.pressed_keys.clear()

    def _send(self, inp):
        if self.is_emergency_stopped:
            return
        SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def move_rel(self, dx: int, dy: int):
        """Relative mouse movement with safety clamping"""
        if self.is_emergency_stopped:
            return
        # Safety Clamping: prevent extreme erratic teleportation
        clamped_dx = max(-400, min(400, int(dx)))
        clamped_dy = max(-400, min(400, int(dy)))
        
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dx = clamped_dx
        inp.u.mi.dy = clamped_dy
        inp.u.mi.mouseData = 0
        inp.u.mi.dwFlags = MOUSEEVENTF_MOVE
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0
        self._send(inp)

    def move_abs(self, x_ratio: float, y_ratio: float):
        """Absolute positioning with normalized bounds checking (0.0 to 1.0)"""
        if self.is_emergency_stopped:
            return
        safe_x = max(0.0, min(1.0, float(x_ratio)))
        safe_y = max(0.0, min(1.0, float(y_ratio)))
        
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dx = int(safe_x * 65535)
        inp.u.mi.dy = int(safe_y * 65535)
        inp.u.mi.mouseData = 0
        inp.u.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0
        self._send(inp)

    def mouse_down(self, button: int):
        if self.is_emergency_stopped:
            return
        self.pressed_mouse_buttons.add(button)
        
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dx = 0
        inp.u.mi.dy = 0
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0
        
        if button == 0:
            inp.u.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
            inp.u.mi.mouseData = 0
        elif button == 2:
            inp.u.mi.dwFlags = MOUSEEVENTF_RIGHTDOWN
            inp.u.mi.mouseData = 0
        elif button == 1:
            inp.u.mi.dwFlags = MOUSEEVENTF_MIDDLEDOWN
            inp.u.mi.mouseData = 0
        elif button == 3:  # Logitech M650 Back Button
            inp.u.mi.dwFlags = MOUSEEVENTF_XDOWN
            inp.u.mi.mouseData = XBUTTON1
        elif button == 4:  # Logitech M650 Forward Button
            inp.u.mi.dwFlags = MOUSEEVENTF_XDOWN
            inp.u.mi.mouseData = XBUTTON2
        else:
            return
        
        self._send(inp)

    def mouse_up(self, button: int):
        self.pressed_mouse_buttons.discard(button)
        
        inp = INPUT(type=INPUT_MOUSE)
        inp.u.mi.dx = 0
        inp.u.mi.dy = 0
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = 0
        
        if button == 0:
            inp.u.mi.dwFlags = MOUSEEVENTF_LEFTUP
            inp.u.mi.mouseData = 0
        elif button == 2:
            inp.u.mi.dwFlags = MOUSEEVENTF_RIGHTUP
            inp.u.mi.mouseData = 0
        elif button == 1:
            inp.u.mi.dwFlags = MOUSEEVENTF_MIDDLEUP
            inp.u.mi.mouseData = 0
        elif button == 3:
            inp.u.mi.dwFlags = MOUSEEVENTF_XUP
            inp.u.mi.mouseData = XBUTTON1
        elif button == 4:
            inp.u.mi.dwFlags = MOUSEEVENTF_XUP
            inp.u.mi.mouseData = XBUTTON2
        else:
            return
        
        self._send(inp)

    def mouse_wheel(self, delta_y: float, delta_x: float = 0.0):
        if self.is_emergency_stopped:
            return
        if delta_y != 0:
            inp = INPUT(type=INPUT_MOUSE)
            inp.u.mi.dx = 0
            inp.u.mi.dy = 0
            inp.u.mi.dwFlags = MOUSEEVENTF_WHEEL
            inp.u.mi.mouseData = int(delta_y)
            inp.u.mi.time = 0
            inp.u.mi.dwExtraInfo = 0
            self._send(inp)

        if delta_x != 0:
            inp = INPUT(type=INPUT_MOUSE)
            inp.u.mi.dx = 0
            inp.u.mi.dy = 0
            inp.u.mi.dwFlags = MOUSEEVENTF_HWHEEL
            inp.u.mi.mouseData = int(delta_x)
            inp.u.mi.time = 0
            inp.u.mi.dwExtraInfo = 0
            self._send(inp)

    def _resolve_vk(self, key):
        if isinstance(key, int):
            return key
        if isinstance(key, str):
            k = key.lower()
            if k in VK_MAP:
                return VK_MAP[k]
            if len(key) == 1:
                # Character key (e.g. 'A'-'Z', '0'-'9')
                c = ord(key.upper())
                if (0x30 <= c <= 0x39) or (0x41 <= c <= 0x5A):
                    return c
        return None

    def key_down(self, key):
        if self.is_emergency_stopped:
            return
        vk = self._resolve_vk(key)
        if not vk:
            return
        self.pressed_keys.add(vk)
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki.wVk = vk
        inp.u.ki.wScan = user32.MapVirtualKeyW(vk, 0)
        inp.u.ki.dwFlags = 0
        inp.u.ki.time = 0
        inp.u.ki.dwExtraInfo = 0
        self._send(inp)

    def key_up(self, key):
        vk = self._resolve_vk(key)
        if not vk:
            return
        self.pressed_keys.discard(vk)
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.u.ki.wVk = vk
        inp.u.ki.wScan = user32.MapVirtualKeyW(vk, 0)
        inp.u.ki.dwFlags = KEYEVENTF_KEYUP
        inp.u.ki.time = 0
        inp.u.ki.dwExtraInfo = 0
        self._send(inp)

    def key_press(self, key):
        self.key_down(key)
        time.sleep(0.01)
        self.key_up(key)

    def type_unicode(self, text: str):
        """Send Unicode text (Supports Chinese, Symbols, English, Emojis)"""
        if self.is_emergency_stopped:
            return
        for char in text:
            code = ord(char)
            # Key Down (Unicode)
            inp_down = INPUT(type=INPUT_KEYBOARD)
            inp_down.u.ki.wVk = 0
            inp_down.u.ki.wScan = code
            inp_down.u.ki.dwFlags = KEYEVENTF_UNICODE
            inp_down.u.ki.time = 0
            inp_down.u.ki.dwExtraInfo = 0
            self._send(inp_down)
            
            # Key Up (Unicode)
            inp_up = INPUT(type=INPUT_KEYBOARD)
            inp_up.u.ki.wVk = 0
            inp_up.u.ki.wScan = code
            inp_up.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
            inp_up.u.ki.time = 0
            inp_up.u.ki.dwExtraInfo = 0
            self._send(inp_up)

    def send_shortcut(self, keys: list):
        """Execute shortcut combination e.g. ['ctrl', 'c'], ['win', 'd']"""
        if self.is_emergency_stopped:
            return
        vks = [self._resolve_vk(k) for k in keys if self._resolve_vk(k)]
        for vk in vks:
            self.key_down(vk)
            time.sleep(0.01)
        time.sleep(0.02)
        for vk in reversed(vks):
            self.key_up(vk)
