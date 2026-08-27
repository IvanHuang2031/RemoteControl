# Windows Ultra-Low-Latency Remote Control (iPad + Logitech M650)

基於 **WebRTC H.264 硬體串流** 與 **Win32 底層輸入 API** 打造的極低延遲、高畫質 Windows 遠端控制系統。專為外出旅遊時使用 **iPad 搭配羅技 M650 藍牙滑鼠** 遙控家中電腦所設計。

---

## ✨ 核心特色

1. **⚡ WebRTC H.264 60 FPS 硬體編解碼**：
   - 伺服端採用 25~35 Mbps 高碼率 H.264 視訊串流，徹底消除模糊與慢啟動延遲。
   - iPad 端透過 Apple Silicon 晶片硬體解碼，端到端延遲僅 **10 ~ 15 ms**。
2. **🖱️ 羅技 M650 滑鼠專屬適配**：
   - **Pointer Lock 游標鎖定**：原生隱藏 iOS 小圓點，支援相對位移與無邊界移動。
   - **SmartWheel 滾輪**：支援平滑滾動與方向反轉切換。
   - **側邊前後鍵**：映射至 Windows 瀏覽器前進/後退（`XBUTTON1` / `XBUTTON2`）。
   - **即時硬體滑鼠游標繪製**：伺服端自動捕捉並即時將 Windows 滑鼠游標（箭頭/手指/I-Beam）繪入畫面。
3. **⌨️ 全功能鍵盤與 Windows 快捷鍵中心**：
   - **中文 / 英文打字**：彈出式輸入面板，完美支援 iPadOS 原生注音、倉頡、拼音與 Emoji 輸入。
   - **⚡ 快捷鍵中心**：內建全功能 Windows 快捷鍵（`Ctrl+C/V/Z/A/S`, `Alt+Tab`, `Win+D`, `Win+Tab`, `Ctrl+Shift+Esc` 等）。
   - **實體藍牙鍵盤直通**：iPad 外接鍵盤時可直接敲擊所有組合鍵。
4. **🛡️ 五重安全保險防護機制**：
   - **實體 F12 緊急斷電保險絲**：電腦實體鍵盤按下 `F12` 立即一鍵鎖死所有遠端輸入（`F11` 解除）。
   - **斷線自動復位**：連線中斷無條件釋放所有按鍵與滑鼠點擊，絕不卡鍵。
   - **輸入數值箝位與頻率限制**：防止異常封包導致游標暴衝或系統過載。
5. **📱 滿版沉浸與 PWA 原生支援**：
   - 支援 Safari **「加入主畫面」**，獲得 100% 滿版無網址列的原生 App 體驗。

---

## 🚀 快速啟動指引

### 1. 電腦端啟動伺服器
在專案目錄雙擊執行：
```cmd
start_server.bat
```
或者在命令列執行：
```cmd
python server.py
```

### 2. iPad 端連線
1. 確保 iPad 與電腦連在同一 Wi-Fi（外出時可搭配 Tailscale P2P）。
2. 在 iPad 的 Safari 瀏覽器打開提示的網址：
   ```text
   http://<電腦IP>:8080
   ```
3. 點擊 **「鎖定滑鼠」** 即可開始操作！

---

## 📁 檔案架構

- `server.py`：WebRTC H.264 串流與 HTTP/DataChannel 伺服器
- `screen_capture.py`：Win32 DPI 感知 GDI 畫面與滑鼠游標擷取引擎
- `input_controller.py`：Win32 `SendInput` 底層輸入模擬與五重安全防護模組
- `static/index.html`：前端介面與快捷鍵中心
- `static/app.js`：WebRTC 連線、Pointer Lock 與輸入事件轉發
- `static/style.css`：暗黑風格響應式介面
- `start_server.bat`：Windows 一鍵啟動腳本
