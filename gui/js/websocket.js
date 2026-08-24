// ── WebSocket ──
let socket = null;
let reconnectTimer = null;

function wsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws`;
}

function connectWebSocket() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  socket = new WebSocket(wsUrl());

  socket.onopen = () => {
    console.log('[WS] Conexión establecida con éxito.');
  };

  socket.onmessage = (event) => {
    console.log('[WS] Mensaje recibido del servidor:', event.data);
    try {
      const data = JSON.parse(event.data);
      handleIncomingMessage(data);
    } catch (e) {
      console.error('[WS] No se pudo parsear el mensaje:', e);
    }
  };

  socket.onerror = (error) => {
    console.error('[WS] Error en la conexión:', error);
  };

  socket.onclose = () => {
    console.warn('[WS] Conexión cerrada. Intentando reconectar en 3 segundos...');
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectWebSocket, 3000);
  };
}

function wsSend(type, payload, quiet = false) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    const messageObject = {
      type: type,
      payload: payload,
      timestamp: Date.now()
    };
    socket.send(JSON.stringify(messageObject));
    if (!quiet) console.log(`[WS Enviado] (${type}):`, payload);
  } else {
    if (!quiet) console.error('[WS Error] No se pudo enviar el mensaje: La conexión no está abierta.');
    connectWebSocket();
  }
}

function setServiceStatus(status) {
  const statusDot = document.getElementById('statusDot');
  if (!statusDot) return;
  statusDot.classList.remove('starting', 'online');
  if (status === 'starting') statusDot.classList.add('starting');
  else if (status === 'online') statusDot.classList.add('online');
}

function handleIncomingMessage(data) {
  if (data.type === 'chat_stage') {
    const stage = data.payload.stage;
    if (stage === 'thinking') {
      window.aiBusy = true;
      getOrCreateTypingBubble();
      showToast(t('generating_response'), { busy: true, duration: 0 });
    } else if (stage === 'voice') {
      showToast(t('generating_tts'), { busy: true, duration: 0 });
    } else if (stage === 'speaking') {
      hideToast(t('generating_tts'));
    }
  } else if (data.type === 'chat_response') {
    replaceTypingBubble(data.payload.text);
    hideToast(t('generating_response'));
  } else if (data.type === 'tts_done') {
    window.aiBusy = false;
    hideBusyWarning();
  } else if (data.type === 'log') {
    appendLog(data.payload.line);
  } else if (data.type === 'speech_result') {
    const text = (data.payload.text || '').trim();
    window.waitingSpeechResult = false;
    removeUserTypingBubble();
    hideToast(t('listening'));
    if (text) {
      sendChatMessage(text);
    } else {
      showToast(t('could_not_understand'));
    }
  } else if (data.type === 'wake_detected') {
    if (window.aiBusy) {
      showBusyWarning();
    } else {
      window.waitingSpeechResult = true;
      getOrCreateUserTypingBubble();
      showToast(t('listening'), { busy: true, duration: 0 });
    }
  } else if (data.type === 'wake_busy') {
    // Wake word heard while the AI is responding: red warning, no input.
    showBusyWarning();
  } else if (data.type === 'status_update') {
    const running = data.payload.running === true;
    setServiceStatus(running ? 'online' : 'off');
    window.serviceRunning = running;
    if (data.payload.voice_mode !== undefined) {
      window.inputService = data.payload.voice_mode || 'console';
      updateInputPlaceholder();
    }
    if (running) {
      showInitOk();
      if (window.inputService === 'wake_word') startWakeStream();
      else if (window.inputService === 'speech') requestMic();
    } else {
      releaseMic();
      window.aiBusy = false;
      window.waitingSpeechResult = false;
      removeUserTypingBubble();
      hideBusyWarning();
      hideToast();
    }
  } else if (data.type === 'crash') {
    window.aiBusy = false;
    window.waitingSpeechResult = false;
    removeUserTypingBubble();
    hideBusyWarning();
    const crashMsg = t('crash');
    const html = '<span style="color:#ff4444;">' + crashMsg + '</span>';
    if (terminalLog) {
      terminalLog.innerHTML += html + '\n';
      terminalLog.scrollTop = terminalLog.scrollHeight;
    }
    if (initConsole) {
      initConsole.innerHTML += html + '\n';
      initConsole.scrollTop = initConsole.scrollHeight;
    }
    setServiceStatus('off');
    window.serviceRunning = false;
    showInitOk();
  }
}
