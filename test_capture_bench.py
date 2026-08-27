import time
import mss
import numpy as np
from PIL import Image, ImageGrab
import io
import dxcam

def bench_mss(n=60):
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        t0 = time.perf_counter()
        for _ in range(n):
            img = sct.grab(monitor)
            _ = np.frombuffer(img.raw, dtype=np.uint8)
        t1 = time.perf_counter()
    fps = n / (t1 - t0)
    latency_ms = (t1 - t0) / n * 1000
    print(f"MSS: {n} frames in {t1-t0:.3f}s -> {fps:.1f} FPS, {latency_ms:.2f} ms/frame")
    return fps, latency_ms

def bench_dxcam(n=60):
    try:
        camera = dxcam.create(output_idx=0)
        t0 = time.perf_counter()
        count = 0
        for _ in range(n):
            frame = camera.grab()
            if frame is not None:
                count += 1
        t1 = time.perf_counter()
        del camera
        if count > 0:
            fps = count / (t1 - t0)
            latency_ms = (t1 - t0) / count * 1000
            print(f"DXCam (DXGI Desktop Duplication): {count} frames in {t1-t0:.3f}s -> {fps:.1f} FPS, {latency_ms:.2f} ms/frame")
            return fps, latency_ms
        else:
            print("DXCam: grab returned None")
            return 0, 0
    except Exception as e:
        print(f"DXCam error: {e}")
        return 0, 0

def bench_pillow(n=30):
    t0 = time.perf_counter()
    for _ in range(n):
        _ = ImageGrab.grab()
    t1 = time.perf_counter()
    fps = n / (t1 - t0)
    latency_ms = (t1 - t0) / n * 1000
    print(f"Pillow ImageGrab: {n} frames in {t1-t0:.3f}s -> {fps:.1f} FPS, {latency_ms:.2f} ms/frame")
    return fps, latency_ms

def bench_jpeg_encoding(n=60):
    with mss.mss() as sct:
        sct_img = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
        # Test JPEG quality 70
        t0 = time.perf_counter()
        total_size = 0
        for _ in range(n):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=70, optimize=False)
            total_size += buf.tell()
        t1 = time.perf_counter()
        fps = n / (t1 - t0)
        ms = (t1 - t0) / n * 1000
        avg_kb = (total_size / n) / 1024
        print(f"Pillow JPEG (Q70, {img.width}x{img.height}): {fps:.1f} FPS, {ms:.2f} ms/frame, Avg Size: {avg_kb:.1f} KB")

        # Test WebP
        t0 = time.perf_counter()
        total_size = 0
        for _ in range(n):
            buf = io.BytesIO()
            img.save(buf, format="WEBP", quality=70, method=0)
            total_size += buf.tell()
        t1 = time.perf_counter()
        fps = n / (t1 - t0)
        ms = (t1 - t0) / n * 1000
        avg_kb = (total_size / n) / 1024
        print(f"Pillow WebP (Q70 fast, {img.width}x{img.height}): {fps:.1f} FPS, {ms:.2f} ms/frame, Avg Size: {avg_kb:.1f} KB")

if __name__ == '__main__':
    print("=== Screen Capture Benchmark ===")
    bench_dxcam(60)
    bench_mss(60)
    bench_pillow(30)
    print("\n=== Encoding Benchmark ===")
    bench_jpeg_encoding(60)
