"""
Windows Ultra-Low-Latency Remote Desktop Server (WebRTC True 60FPS High-Bitrate Edition)
Fixes:
- Native 60 FPS Pacing override in next_timestamp() (Removes aiortc 30FPS hardcoded ceiling)
- 25~35 Mbps High-Bitrate H.264 (Crystal clear 2K resolution)
- Full 2560x1440 DPI-Aware Capture
- WebRTC DataChannel (1ms UDP input for Logitech M650 & Full Keyboard)
- Immersive Fullscreen & Floating Keyboard Controls
- Five-layer safety fail-safe with physical F12 Emergency Kill Switch
"""

import asyncio
import ctypes
import json
import os
import socket
import sys
import threading
import time
from fractions import Fraction

# Enable Per-Monitor DPI Aware V2 before initializing any Windows subsystem
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
except Exception:
    pass

import av
import numpy as np
from aiohttp import web
import aiortc.codecs.h264 as h264_mod
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.rtcrtpsender import RTCRtpSender

# ==============================================================================
# Patch aiortc H.264 Encoder for 60 FPS & 25 Mbps High-Bitrate Crystal Clear Video
# ==============================================================================
h264_mod.DEFAULT_BITRATE = 25_000_000   # 25 Mbps (vs default 1 Mbps)
h264_mod.MAX_BITRATE = 60_000_000       # 60 Mbps
h264_mod.MIN_BITRATE = 15_000_000       # 15 Mbps
h264_mod.MAX_FRAME_RATE = 60            # 60 FPS (vs default 30 FPS)

def patched_encode_frame(self, frame: av.VideoFrame, force_keyframe: bool):
    if self.codec and (
        frame.width != self.codec.width
        or frame.height != self.codec.height
        or abs(self.target_bitrate - self.codec.bit_rate) / self.codec.bit_rate > 0.1
    ):
        self.buffer_data = b""
        self.buffer_pts = None
        self.codec = None

    if force_keyframe:
        frame.pict_type = av.video.frame.PictureType.I
    else:
        frame.pict_type = av.video.frame.PictureType.NONE

    if self.codec is None:
        self.codec = av.CodecContext.create("libx264", "w")
        self.codec.width = frame.width
        self.codec.height = frame.height
        self.codec.bit_rate = max(15_000_000, self.target_bitrate)
        self.codec.pix_fmt = "yuv420p"
        self.codec.framerate = Fraction(60, 1)
        self.codec.time_base = Fraction(1, 60)
        self.codec.options = {
            "tune": "zerolatency",
            "preset": "ultrafast",
            "crf": "18",               # Near-lossless visual quality
            "x264-params": "ref=1:bframes=0:force-cfr=1:sliced-threads=1:threads=4",
        }

    data_to_send = b""
    for package in self.codec.encode(frame):
        data_to_send += bytes(package)

    if data_to_send:
        yield from self._split_bitstream(data_to_send)

h264_mod.H264Encoder._encode_frame = patched_encode_frame

# ==============================================================================

from input_controller import WindowsInputController
from screen_capture import ScreenCaptureEngine

HTTP_PORT = 8080
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE = Fraction(1, VIDEO_CLOCK_RATE)

def get_local_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip and not ip.startswith("127."):
                if ip not in ips:
                    ips.append(ip)
    except Exception:
        pass
    if not ips:
        ips.append("127.0.0.1")
    return ips

class ScreenVideoTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, capture_engine):
        super().__init__()
        self.capture_engine = capture_engine
        self.fps = 60
        self._ptime = 1 / 60
        self._start = None
        self._timestamp = 0

    async def next_timestamp(self) -> tuple[int, Fraction]:
        if self.readyState != "live":
            from aiortc.mediastreams import MediaStreamError
            raise MediaStreamError

        if self._start is None:
            self._start = time.time()
            self._timestamp = 0
        else:
            self._timestamp += int(self._ptime * VIDEO_CLOCK_RATE)
            wait = self._start + (self._timestamp / VIDEO_CLOCK_RATE) - time.time()
            if wait > 0.001:
                await asyncio.sleep(wait)
        return self._timestamp, VIDEO_TIME_BASE

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        
        frame_bgr = self.capture_engine.get_latest_frame()
        if frame_bgr is None:
            frame_bgr = np.zeros((720, 1280, 3), dtype=np.uint8)

        video_frame = av.VideoFrame.from_ndarray(frame_bgr, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

class RemoteControlServer:
    def __init__(self):
        self.input_ctrl = WindowsInputController()
        # Full 2560x1440 native resolution, 60 FPS
        self.capture_engine = ScreenCaptureEngine(target_fps=60, scale=1.0)
        self.pcs = set()

    def process_command(self, message_str):
        try:
            data = json.loads(message_str)
            msg_type = data.get("type")

            # Mouse relative movement (Pointer Lock)
            if msg_type == "mouse_rel":
                dx = data.get("dx", 0)
                dy = data.get("dy", 0)
                self.input_ctrl.move_rel(dx, dy)

            # Mouse absolute positioning (Touchscreen tap)
            elif msg_type == "mouse_abs":
                x = data.get("x", 0.0)
                y = data.get("y", 0.0)
                self.input_ctrl.move_abs(x, y)

            # Mouse Buttons (Left, Right, Middle, M650 Side Buttons)
            elif msg_type == "mouse_down":
                btn = data.get("button", 0)
                self.input_ctrl.mouse_down(btn)

            elif msg_type == "mouse_up":
                btn = data.get("button", 0)
                self.input_ctrl.mouse_up(btn)

            # Scroll wheel
            elif msg_type == "mouse_wheel":
                dy = data.get("delta_y", 0)
                dx = data.get("delta_x", 0)
                self.input_ctrl.mouse_wheel(dy, dx)

            # Keyboard Events
            elif msg_type == "key_down":
                key = data.get("key")
                self.input_ctrl.key_down(key)

            elif msg_type == "key_up":
                key = data.get("key")
                self.input_ctrl.key_up(key)

            elif msg_type == "key_press":
                key = data.get("key")
                self.input_ctrl.key_press(key)

            # Direct Unicode typing (Chinese, English, Symbols, Emojis)
            elif msg_type == "type_text":
                text = data.get("text", "")
                self.input_ctrl.type_unicode(text)

            # Shortcut combinations e.g. ['ctrl', 'c'], ['win', 'd']
            elif msg_type == "shortcut":
                keys = data.get("keys", [])
                self.input_ctrl.send_shortcut(keys)

        except Exception as e:
            print(f"[Server] Error processing input message: {e}")

    async def handle_offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        self.pcs.add(pc)
        print(f"[WebRTC] Client connected (Active sessions: {len(self.pcs)})")

        @pc.on("datachannel")
        def on_datachannel(channel):
            print(f"[WebRTC] DataChannel ready: {channel.label}")

            @channel.on("message")
            def on_message(message):
                if isinstance(message, str):
                    if '"ping"' in message:
                        try:
                            msg_obj = json.loads(message)
                            channel.send(json.dumps({
                                "type": "pong",
                                "client_time": msg_obj.get("client_time")
                            }))
                        except Exception:
                            pass
                    else:
                        self.process_command(message)

            @channel.on("close")
            def on_close():
                print(f"[WebRTC] DataChannel closed")
                self.input_ctrl.release_all_inputs()

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"[WebRTC] ConnectionState: {pc.connectionState}")
            if pc.connectionState in ["failed", "closed", "disconnected"]:
                self.input_ctrl.release_all_inputs()
                await pc.close()
                self.pcs.discard(pc)

        # Add screen capture video track (True 60 FPS Native)
        video_track = ScreenVideoTrack(self.capture_engine)
        pc.addTrack(video_track)

        # Prefer H.264
        transceiver = pc.getTransceivers()[0]
        capabilities = RTCRtpSender.getCapabilities("video")
        preferences = [codec for codec in capabilities.codecs if codec.mimeType.lower() == "video/h264"]
        if preferences:
            transceiver.setCodecPreferences(preferences)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        # SDP Munging: Inject High-Bitrate parameters (35 Mbps) and 60 FPS
        sdp = pc.localDescription.sdp
        if "c=IN IP4" in sdp:
            sdp = sdp.replace("c=IN IP4", "b=AS:35000\r\nc=IN IP4", 1)

        return web.json_response({
            "sdp": sdp,
            "type": pc.localDescription.type,
            "width": self.capture_engine.orig_w,
            "height": self.capture_engine.orig_h
        })

    def _start_safety_hotkey_listener(self):
        """Background thread monitoring F12 key on physical keyboard for instant Emergency Stop"""
        def hotkey_loop():
            import ctypes
            user32 = ctypes.windll.user32
            VK_F12 = 0x7B
            VK_F11 = 0x7A
            
            while True:
                time.sleep(0.05)
                if user32.GetAsyncKeyState(VK_F12) & 0x8000:
                    if not self.input_ctrl.is_emergency_stopped:
                        self.input_ctrl.emergency_stop()
                    time.sleep(0.3)
                elif user32.GetAsyncKeyState(VK_F11) & 0x8000:
                    if self.input_ctrl.is_emergency_stopped:
                        self.input_ctrl.resume_input()
                    time.sleep(0.3)

        thread = threading.Thread(target=hotkey_loop, daemon=True)
        thread.start()

    async def on_shutdown(self, app):
        print("\n[Server] Shutting down WebRTC sessions...")
        self.input_ctrl.release_all_inputs()
        coros = [pc.close() for pc in self.pcs]
        await asyncio.gather(*coros)
        self.pcs.clear()
        self.capture_engine.stop()

def create_app():
    server = RemoteControlServer()
    server.capture_engine.start()
    server._start_safety_hotkey_listener()

    app = web.Application()
    app.on_shutdown.append(server.on_shutdown)
    
    app.router.add_post("/offer", server.handle_offer)
    app.router.add_static("/", STATIC_DIR, show_index=True)
    
    return app, server

def main():
    app, server = create_app()
    
    print("=" * 65)
    print("  Windows Ultra-Low-Latency Remote Control (True 60FPS Edition)")
    print(f"  Target: {server.capture_engine.orig_w} x {server.capture_engine.orig_h} (60 FPS Native @ 25-35 Mbps)")
    print("=" * 65)
    print("  [SAFETY GUARD ACTIVE]:")
    print("   - Press [F12] on physical keyboard: Instant Emergency Kill Switch")
    print("   - Press [F11] on physical keyboard: Resume Remote Input")
    print("   - Disconnect Auto-Release: ACTIVE")
    print("=" * 65)

    ips = get_local_ips()
    print("\n[Web Client Ready]")
    for ip in ips:
        print(f"  👉 http://{ip}:{HTTP_PORT}")
    print(f"  👉 http://localhost:{HTTP_PORT}")
    print("=" * 65)
    print("Press Ctrl+C to terminate the server.\n")

    web.run_app(app, host="0.0.0.0", port=HTTP_PORT, print=None)

if __name__ == "__main__":
    main()
