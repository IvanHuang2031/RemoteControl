/**
 * Ultra-Low-Latency WebRTC Remote Control Client (v5.0 Complete Edition)
 * Specialized for iPadOS Safari / Chrome, Logitech M650 & Full Windows Shortcuts
 */

(function () {
  'use strict';

  // DOM Elements
  const video = document.getElementById('stream-video');
  const viewport = document.getElementById('viewport');
  const appContainer = document.getElementById('app-container');
  
  const btnLock = document.getElementById('btn-lock');
  const lockBtnText = document.getElementById('lock-btn-text');
  const btnSoftKeyboard = document.getElementById('btn-soft-keyboard');
  const btnShortcutCenter = document.getElementById('btn-shortcut-center');
  const btnFullscreen = document.getElementById('btn-fullscreen');
  const btnSettingsToggle = document.getElementById('btn-settings-toggle');
  const btnCloseSettings = document.getElementById('btn-close-settings');
  
  // Floating Action Buttons (Always accessible in all modes)
  const fabKeyboard = document.getElementById('fab-keyboard');
  const fabShortcuts = document.getElementById('fab-shortcuts');
  const fabImmersive = document.getElementById('fab-immersive');

  const settingsDrawer = document.getElementById('settings-drawer');
  const lockPrompt = document.getElementById('lock-prompt');
  const statusDot = document.getElementById('status-dot');
  const textInputPanel = document.getElementById('text-input-panel');
  const imeInput = document.getElementById('ime-input');
  const btnSendText = document.getElementById('btn-send-text');
  const btnCloseIme = document.getElementById('btn-close-ime');
  const shortcutModal = document.getElementById('shortcut-modal');
  const btnCloseShortcuts = document.getElementById('btn-close-shortcuts');

  // Stats Elements
  const statFps = document.getElementById('stat-fps');
  const statRtt = document.getElementById('stat-rtt');

  // Settings Elements
  const sliderSensitivity = document.getElementById('slider-sensitivity');
  const valSensitivity = document.getElementById('val-sensitivity');
  const sliderWheelSpeed = document.getElementById('slider-wheel-speed');
  const valWheelSpeed = document.getElementById('val-wheel-speed');
  const chkInvertWheel = document.getElementById('chk-invert-wheel');
  const infoHostRes = document.getElementById('info-host-res');

  // Mouse HUD Elements
  const hudLeft = document.getElementById('hud-btn-left');
  const hudMid = document.getElementById('hud-btn-mid');
  const hudRight = document.getElementById('hud-btn-right');
  const hudB1 = document.getElementById('hud-btn-b1');
  const hudB2 = document.getElementById('hud-btn-b2');

  // Client State
  let pc = null;
  let dc = null;
  let isPointerLocked = false;
  let mouseSensitivity = 1.0;
  let wheelSpeed = 1.0;
  let pingInterval = null;

  // FPS tracking using native video frame callback
  let renderedFrames = 0;
  let lastFpsTime = performance.now();

  function startFpsMonitor() {
    if ('requestVideoFrameCallback' in HTMLVideoElement.prototype) {
      function onFrame() {
        renderedFrames++;
        video.requestVideoFrameCallback(onFrame);
      }
      video.requestVideoFrameCallback(onFrame);

      setInterval(() => {
        const now = performance.now();
        const elapsed = (now - lastFpsTime) / 1000;
        if (elapsed >= 1.0) {
          const fps = Math.round(renderedFrames / elapsed);
          statFps.textContent = fps;
          renderedFrames = 0;
          lastFpsTime = now;
        }
      }, 1000);
    }
  }

  // WebRTC Connection Setup
  async function startWebRTC() {
    statusDot.classList.remove('online');
    
    if (pc) {
      pc.close();
      pc = null;
    }

    pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' }
      ]
    });

    // Create DataChannel for ultra-low latency UDP inputs
    dc = pc.createDataChannel('input', { ordered: true });

    dc.onopen = () => {
      console.log('[WebRTC] DataChannel Open');
      statusDot.classList.add('online');
      startPing();
    };

    dc.onclose = () => {
      console.warn('[WebRTC] DataChannel Closed');
      statusDot.classList.remove('online');
      stopPing();
    };

    dc.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'pong') {
          const rtt = Math.round(performance.now() - msg.client_time);
          statRtt.textContent = `${rtt} ms`;
        }
      } catch (e) {}
    };

    pc.ontrack = (event) => {
      console.log('[WebRTC] Received 60FPS Video Track (H.264)');
      if (video.srcObject !== event.streams[0]) {
        video.srcObject = event.streams[0];
        video.play().catch(() => {});
        startFpsMonitor();
      }
    };

    pc.addTransceiver('video', { direction: 'recvonly' });

    try {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const response = await fetch('/offer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sdp: pc.localDescription.sdp,
          type: pc.localDescription.type
        })
      });

      const answer = await response.json();
      await pc.setRemoteDescription(new RTCSessionDescription(answer));

      if (answer.width && answer.height) {
        infoHostRes.textContent = `${answer.width} x ${answer.height}`;
      }
    } catch (err) {
      console.error('[WebRTC] Offer/Answer negotiation error:', err);
      setTimeout(startWebRTC, 2000);
    }
  }

  function startPing() {
    stopPing();
    pingInterval = setInterval(() => {
      if (dc && dc.readyState === 'open') {
        dc.send(JSON.stringify({ type: 'ping', client_time: performance.now() }));
      }
    }, 1000);
  }

  function stopPing() {
    if (pingInterval) {
      clearInterval(pingInterval);
      pingInterval = null;
    }
  }

  function sendInput(data) {
    if (dc && dc.readyState === 'open') {
      dc.send(JSON.stringify(data));
    }
  }

  // Pointer Lock API Handling
  function requestPointerLock() {
    const el = video;
    const requestMethod = el.requestPointerLock || el.webkitRequestPointerLock || el.mozRequestPointerLock;
    if (requestMethod) {
      try {
        const promise = el.requestPointerLock({ unadjustedMovement: true });
        if (promise && promise.catch) {
          promise.catch(() => el.requestPointerLock());
        }
      } catch (e) {
        el.requestPointerLock();
      }
    }
  }

  document.addEventListener('pointerlockchange', onPointerLockChange);
  document.addEventListener('webkitpointerlockchange', onPointerLockChange);
  document.addEventListener('mozpointerlockchange', onPointerLockChange);

  function onPointerLockChange() {
    const lockedEl = document.pointerLockElement || document.webkitPointerLockElement || document.mozPointerLockElement;
    isPointerLocked = (lockedEl === video);

    if (isPointerLocked) {
      lockPrompt.classList.remove('hidden');
      lockBtnText.textContent = '已鎖定滑鼠';
      btnLock.classList.add('btn-secondary');
      btnLock.classList.remove('btn-primary');
      setTimeout(() => {
        lockPrompt.classList.add('hidden');
      }, 2500);
    } else {
      lockPrompt.classList.add('hidden');
      lockBtnText.textContent = '鎖定滑鼠';
      btnLock.classList.add('btn-primary');
      btnLock.classList.remove('btn-secondary');
    }
  }

  btnLock.addEventListener('click', (e) => {
    e.stopPropagation();
    if (!isPointerLocked) {
      requestPointerLock();
    } else {
      if (document.exitPointerLock) document.exitPointerLock();
    }
  });

  // Accurate Video Coordinate Calculation (accounting for letterboxing)
  function getNormalizedVideoCoordinates(clientX, clientY) {
    const rect = video.getBoundingClientRect();
    const videoRatio = (video.videoWidth || 2560) / (video.videoHeight || 1440);
    const elementRatio = rect.width / rect.height;

    let actualWidth = rect.width;
    let actualHeight = rect.height;
    let offsetX = 0;
    let offsetY = 0;

    if (elementRatio > videoRatio) {
      actualWidth = rect.height * videoRatio;
      offsetX = (rect.width - actualWidth) / 2;
    } else {
      actualHeight = rect.width / videoRatio;
      offsetY = (rect.height - actualHeight) / 2;
    }

    const clickX = clientX - rect.left - offsetX;
    const clickY = clientY - rect.top - offsetY;

    const xRatio = Math.max(0.0, Math.min(1.0, clickX / actualWidth));
    const yRatio = Math.max(0.0, Math.min(1.0, clickY / actualHeight));

    return { xRatio, yRatio };
  }

  // Mouse Movement Listeners for Logitech M650
  window.addEventListener('mousemove', (e) => {
    if (!dc || dc.readyState !== 'open') return;

    if (isPointerLocked) {
      const dx = Math.round(e.movementX * mouseSensitivity);
      const dy = Math.round(e.movementY * mouseSensitivity);
      if (dx !== 0 || dy !== 0) {
        sendInput({ type: 'mouse_rel', dx, dy });
      }
    } else {
      const { xRatio, yRatio } = getNormalizedVideoCoordinates(e.clientX, e.clientY);
      sendInput({ type: 'mouse_abs', x: xRatio, y: yRatio });
    }
  });

  function updateHudButton(btn, active) {
    const hudMap = {
      0: hudLeft,
      1: hudMid,
      2: hudRight,
      3: hudB1,
      4: hudB2
    };
    const el = hudMap[btn];
    if (el) {
      if (active) el.classList.add('active');
      else el.classList.remove('active');
    }
  }

  // Prevent context menu to allow M650 Right Click
  window.addEventListener('contextmenu', (e) => {
    e.preventDefault();
  });

  // Handle Mousedown
  window.addEventListener('mousedown', (e) => {
    if (!dc || dc.readyState !== 'open') return;
    if (e.target.closest('#header-bar') || e.target.closest('#settings-drawer') || e.target.closest('#text-input-panel') || e.target.closest('.floating-fab-group') || e.target.closest('.modal-card') || e.target.closest('.quick-toolbar')) {
      return;
    }
    
    if (!isPointerLocked && (e.target === video || e.target === viewport)) {
      requestPointerLock();
    }

    updateHudButton(e.button, true);
    sendInput({ type: 'mouse_down', button: e.button });
  });

  // Handle Mouseup
  window.addEventListener('mouseup', (e) => {
    if (!dc || dc.readyState !== 'open') return;
    updateHudButton(e.button, false);
    sendInput({ type: 'mouse_up', button: e.button });
  });

  // Handle Auxclick (Middle click & Side buttons on M650)
  window.addEventListener('auxclick', (e) => {
    e.preventDefault();
  });

  // Handle SmartWheel / Wheel (Vertical + Horizontal)
  window.addEventListener('wheel', (e) => {
    if (!dc || dc.readyState !== 'open') return;
    if (e.target.closest('#settings-drawer') || e.target.closest('.modal-body') || e.target.closest('.quick-toolbar')) return;
    
    e.preventDefault();

    const invertMultiplier = chkInvertWheel && chkInvertWheel.checked ? -1 : 1;
    let deltaY = e.deltaY * invertMultiplier;
    let deltaX = e.deltaX;

    if (e.deltaMode === 1) { // Line mode
      deltaY *= 40;
      deltaX *= 40;
    } else if (e.deltaMode === 2) { // Page mode
      deltaY *= 120;
      deltaX *= 120;
    }

    deltaY = Math.round(deltaY * wheelSpeed);
    deltaX = Math.round(deltaX * wheelSpeed);

    sendInput({ type: 'mouse_wheel', delta_y: deltaY, delta_x: deltaX });
  }, { passive: false });

  // Touch Support for iPad Touchscreen
  let touchStartPos = null;
  let lastTapTime = 0;

  video.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      const now = performance.now();
      if (now - lastTapTime < 300) {
        // Double tap on stream toggles keyboard input panel
        toggleKeyboardPanel();
      }
      lastTapTime = now;

      const touch = e.touches[0];
      const { xRatio, yRatio } = getNormalizedVideoCoordinates(touch.clientX, touch.clientY);
      touchStartPos = { xRatio, yRatio };
      sendInput({ type: 'mouse_abs', x: xRatio, y: yRatio });
      sendInput({ type: 'mouse_down', button: 0 });
    }
  }, { passive: true });

  video.addEventListener('touchmove', (e) => {
    if (e.touches.length === 1) {
      const touch = e.touches[0];
      const { xRatio, yRatio } = getNormalizedVideoCoordinates(touch.clientX, touch.clientY);
      sendInput({ type: 'mouse_abs', x: xRatio, y: yRatio });
    }
  }, { passive: true });

  video.addEventListener('touchend', () => {
    if (touchStartPos) {
      sendInput({ type: 'mouse_up', button: 0 });
      touchStartPos = null;
    }
  });

  // ==========================================
  // Keyboard & Shortcut Handling
  // ==========================================

  function toggleKeyboardPanel() {
    textInputPanel.classList.toggle('hidden');
    if (!textInputPanel.classList.contains('hidden')) {
      imeInput.focus();
    }
  }

  function toggleShortcutModal() {
    shortcutModal.classList.toggle('hidden');
  }

  function toggleImmersiveMode() {
    appContainer.classList.toggle('immersive');
  }

  // All Macro Buttons (.s-btn and .v-macro)
  document.querySelectorAll('.s-btn, .v-macro').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const macroStr = btn.getAttribute('data-macro');
      if (macroStr) {
        const keys = macroStr.split(',');
        sendInput({ type: 'shortcut', keys: keys });
      }
    });
  });

  // All Key Buttons (.s-key and .v-key)
  document.querySelectorAll('.s-key, .v-key').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const key = btn.getAttribute('data-key');
      if (key) {
        sendInput({ type: 'key_press', key: key });
      }
    });
  });

  // Header & FAB Buttons
  btnSoftKeyboard.addEventListener('click', toggleKeyboardPanel);
  fabKeyboard.addEventListener('click', toggleKeyboardPanel);

  btnShortcutCenter.addEventListener('click', toggleShortcutModal);
  fabShortcuts.addEventListener('click', toggleShortcutModal);
  btnCloseShortcuts.addEventListener('click', toggleShortcutModal);

  btnFullscreen.addEventListener('click', toggleImmersiveMode);
  fabImmersive.addEventListener('click', toggleImmersiveMode);

  // Send Text via IME Input Box
  function submitImeText() {
    const val = imeInput.value;
    if (val && val.length > 0) {
      sendInput({ type: 'type_text', text: val });
      imeInput.value = '';
    }
  }

  btnSendText.addEventListener('click', (e) => {
    e.stopPropagation();
    submitImeText();
    imeInput.focus();
  });

  btnCloseIme.addEventListener('click', (e) => {
    e.stopPropagation();
    textInputPanel.classList.add('hidden');
  });

  imeInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      submitImeText();
    }
  });

  // Physical Bluetooth Keyboard Handler
  window.addEventListener('keydown', (e) => {
    if (document.activeElement === imeInput) return;
    
    // Check for keyboard combos e.g. Ctrl+C, Alt+Tab, etc.
    const keyMap = {
      'Backspace': 'backspace',
      'Tab': 'tab',
      'Enter': 'enter',
      'Escape': 'esc',
      'Space': 'space',
      'ArrowLeft': 'left',
      'ArrowUp': 'up',
      'ArrowRight': 'right',
      'ArrowDown': 'down',
      'Delete': 'delete',
      'Meta': 'win',
      'Control': 'ctrl',
      'Alt': 'alt',
      'Shift': 'shift'
    };

    if (e.ctrlKey && e.key.toLowerCase() === 'c') {
      e.preventDefault();
      sendInput({ type: 'shortcut', keys: ['ctrl', 'c'] });
      return;
    }
    if (e.ctrlKey && e.key.toLowerCase() === 'v') {
      e.preventDefault();
      sendInput({ type: 'shortcut', keys: ['ctrl', 'v'] });
      return;
    }
    if (e.ctrlKey && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      sendInput({ type: 'shortcut', keys: ['ctrl', 'z'] });
      return;
    }
    if (e.ctrlKey && e.key.toLowerCase() === 'a') {
      e.preventDefault();
      sendInput({ type: 'shortcut', keys: ['ctrl', 'a'] });
      return;
    }
    if (e.altKey && e.key === 'Tab') {
      e.preventDefault();
      sendInput({ type: 'shortcut', keys: ['alt', 'tab'] });
      return;
    }

    const targetKey = keyMap[e.key] || (e.key.length === 1 ? e.key : null);
    if (targetKey) {
      if (e.ctrlKey || e.altKey || e.metaKey || ['Tab', 'Escape', 'Enter', 'Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
        e.preventDefault();
        sendInput({ type: 'key_press', key: targetKey });
      } else if (e.key.length === 1) {
        sendInput({ type: 'type_text', text: e.key });
      }
    }
  });

  // UI Event Handlers
  btnSettingsToggle.addEventListener('click', () => {
    settingsDrawer.classList.toggle('hidden');
  });

  btnCloseSettings.addEventListener('click', () => {
    settingsDrawer.classList.add('hidden');
  });

  sliderSensitivity.addEventListener('input', () => {
    mouseSensitivity = parseFloat(sliderSensitivity.value);
    valSensitivity.textContent = mouseSensitivity.toFixed(1);
  });

  sliderWheelSpeed.addEventListener('input', () => {
    wheelSpeed = parseFloat(sliderWheelSpeed.value);
    valWheelSpeed.textContent = wheelSpeed.toFixed(1);
  });

  // Start WebRTC connection
  startWebRTC();
})();
