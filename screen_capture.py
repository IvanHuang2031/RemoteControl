"""
High Performance DPI-Aware Screen Capture with Hardware Cursor Overlay for WebRTC
"""

import ctypes
from ctypes import wintypes
import time
import threading
import numpy as np
import cv2
import av
from fractions import Fraction

# Set DPI Awareness to Per-Monitor V2 before any Win32 calls
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

class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('hCursor', ctypes.c_void_p),
        ('ptScreenPos', POINT)
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
    ]

class ScreenCaptureEngine:
    def __init__(self, target_fps=60, scale=1.0):
        self.target_fps = target_fps
        self.scale = scale
        self.running = False
        
        # Get true physical screen dimensions
        hdc = user32.GetDC(0)
        DESKTOPHORZRES = 118
        DESKTOPVERTRES = 117
        self.orig_w = gdi32.GetDeviceCaps(hdc, DESKTOPHORZRES) or user32.GetSystemMetrics(0) or 2560
        self.orig_h = gdi32.GetDeviceCaps(hdc, DESKTOPVERTRES) or user32.GetSystemMetrics(1) or 1440
        user32.ReleaseDC(0, hdc)
        
        # Ensure dimensions are even numbers (required for H.264 YUV420P)
        self.orig_w = (self.orig_w // 2) * 2
        self.orig_h = (self.orig_h // 2) * 2
        
        print(f"[ScreenCapture] Detected True Physical Resolution: {self.orig_w} x {self.orig_h}")
        
        self._lock = threading.Lock()
        self._latest_frame = None
        self._capture_thread = None
        
        self.capture_fps = 0.0
        self.capture_latency_ms = 0.0

    def start(self):
        if self.running:
            return
        self.running = True
        self._capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
        self._capture_thread.start()

    def stop(self):
        self.running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=1.0)

    def get_latest_frame(self):
        with self._lock:
            return self._latest_frame

    def _capture_worker(self):
        w = self.orig_w
        h = self.orig_h
        
        h_desktop = user32.GetDesktopWindow()
        h_dc = user32.GetDC(0)
        h_mem_dc = gdi32.CreateCompatibleDC(h_dc)
        h_bmp = gdi32.CreateCompatibleBitmap(h_dc, w, h)
        gdi32.SelectObject(h_mem_dc, h_bmp)
        
        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # top-down DIB
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0
        
        raw_buffer = np.zeros((h, w, 4), dtype=np.uint8)
        buf_ptr = raw_buffer.ctypes.data_as(ctypes.c_void_p)
        bmi_byref = ctypes.byref(bmi)
        
        ci = CURSORINFO()
        ci.cbSize = ctypes.sizeof(CURSORINFO)
        ci_byref = ctypes.byref(ci)
        
        frame_counter = 0
        fps_timer = time.perf_counter()
        
        try:
            while self.running:
                loop_start = time.perf_counter()
                target_interval = 1.0 / self.target_fps
                
                # 1. Capture screen bitmap
                t_cap_start = time.perf_counter()
                gdi32.BitBlt(h_mem_dc, 0, 0, w, h, h_dc, 0, 0, 0x00CC0020)  # SRCCOPY
                
                # 2. Draw Windows Hardware Mouse Cursor onto captured screen
                try:
                    if user32.GetCursorInfo(ci_byref) and (ci.flags & 1):
                        user32.DrawIconEx(
                            h_mem_dc,
                            ci.ptScreenPos.x,
                            ci.ptScreenPos.y,
                            ci.hCursor,
                            0, 0, 0, None,
                            0x0003  # DI_NORMAL (Image + Mask)
                        )
                except Exception:
                    pass
                
                gdi32.GetDIBits(h_mem_dc, h_bmp, 0, h, buf_ptr, bmi_byref, 0)
                t_cap_end = time.perf_counter()
                cap_time_ms = (t_cap_end - t_cap_start) * 1000.0
                
                # 3. Extract BGR frame directly
                bgr = raw_buffer[:, :, :3].copy()
                
                # Scale if requested (keeping dimensions even)
                if self.scale < 0.99:
                    target_w = (int(w * self.scale) // 2) * 2
                    target_h = (int(h * self.scale) // 2) * 2
                    bgr = cv2.resize(bgr, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
                
                # 4. Publish latest numpy frame
                with self._lock:
                    self._latest_frame = bgr
                    self.capture_latency_ms = cap_time_ms
                
                # FPS Calculation
                frame_counter += 1
                now = time.perf_counter()
                if now - fps_timer >= 1.0:
                    self.capture_fps = frame_counter / (now - fps_timer)
                    frame_counter = 0
                    fps_timer = now
                
                # Pace loop to 60 FPS
                elapsed = time.perf_counter() - loop_start
                sleep_time = target_interval - elapsed
                if sleep_time > 0.001:
                    time.sleep(sleep_time)
        finally:
            gdi32.DeleteObject(h_bmp)
            gdi32.DeleteDC(h_mem_dc)
            user32.ReleaseDC(0, h_dc)
