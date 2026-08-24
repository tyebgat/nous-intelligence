// ── Voice input (speech / wake word) ──
window.inputService = 'console';
window.serviceRunning = false;

let micStream = null;
let micCtx = null;
let micSource = null;
let micProcessor = null;
let speechActive = false;
let wakeStreamActive = false;

function updateInputPlaceholder() {
  const input = document.getElementById('chatInput');
  if (!input) return;
  if (window.inputService === 'speech') {
    input.disabled = true;
    input.placeholder = t('hold_space');
  } else if (window.inputService === 'wake_word') {
    input.disabled = true;
    input.placeholder = t('say_wake_word');
  } else {
    input.disabled = false;
    input.placeholder = t('chat_placeholder_type');
  }
}

function bytesToBase64(bytes) {
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

async function populateAudioDevices() {
  const select = document.getElementById('audioDeviceSelect');
  if (!select) return;
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const inputs = devices.filter(d => d.kind === 'audioinput');
    const saved = originalSettings?.audio_device || select.value || '';
    select.innerHTML = '<option value="">' + t('system_default') + '</option>';
    inputs.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.deviceId;
      opt.textContent = d.label || t('device_n', { id: d.deviceId.slice(0, 8) });
      select.appendChild(opt);
    });
    select.value = saved;
    console.log('[Mic] Device list:', inputs.length, 'input(s)');
  } catch (err) {
    console.warn('[Mic] Cannot enumerate devices:', err);
  }
}

let micRecoveryAttempted = false;

async function recoverMutedMic() {
  // A muted track sometimes clears by tearing everything down and asking
  // for the microphone again (fresh WASAPI session). Only tried once per
  // acquisition; if the device is genuinely muted at OS/hardware level this
  // won't help and the user must unmute it themselves.
  if (micRecoveryAttempted || speechActive) return;
  micRecoveryAttempted = true;
  try {
    const wasWake = wakeStreamActive;
    releaseMic();
    showToast(t('reacquiring_mic'));
    if (wasWake && window.serviceRunning && window.inputService === 'wake_word') {
      await startWakeStream();
    } else {
      await requestMic();
    }
    populateAudioDevices();
  } finally {
    micRecoveryAttempted = false;
  }
}

async function requestMic() {
  if (micStream) return true;
  const select = document.getElementById('audioDeviceSelect');
  const deviceId = select?.value || '';
  try {
    micStream = await navigator.mediaDevices.getUserMedia(
      deviceId ? { audio: { deviceId: { exact: deviceId } } } : { audio: true }
    );
    const track = micStream.getAudioTracks()[0];
    const settings = track?.getSettings?.() || {};
    console.log('[Mic] Using:', track?.label,
      '| muted:', track?.muted,
      '| enabled:', track?.enabled,
      '| device rate:', settings.sampleRate);

    // Chrome reports tracks as muted until the hardware starts delivering
    // audio, so don't warn on the spot. Only flag it if it STAYS muted.
    track?.addEventListener?.('mute', () => {
      console.warn('[Mic] Track muted:', track.label || '?');
    });
    track?.addEventListener?.('unmute', () => {
      console.log('[Mic] Track unmuted - audio active again.');
      showToast(t('mic_active'));
    });
    setTimeout(async () => {
      const t = micStream?.getAudioTracks()[0];
      if (!(t && t.readyState === 'live' && t.muted)) return;
      const msg = `[MIC] Microphone "${t.label}" reports MUTED. ` +
        'Press the keyboard mic-mute key once, or check Levels in Sound settings > Recording. ' +
        'You can also pick another input device in Settings.';
      console.warn('[Mic]', msg);
      if (typeof appendLog === 'function') appendLog(msg);
      showToast(t('mic_muted_toast'));
      await recoverMutedMic();
    }, 3000);
    return true;
  } catch (err) {
    console.warn('[Mic] Access denied or device unavailable:', err);
    showToast(t('mic_denied'));
    return false;
  }
}

function ensureAudioContext() {
  // Browsers gate audio on a user gesture: create/resume the context while
  // the key press / click is being handled, or onaudioprocess never fires.
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return false;
  if (!micCtx) {
    // Use the device's native sample rate; forcing 16 kHz makes some
    // Windows drivers misbehave. The server resamples whatever rate this
    // context reports (sent in the mic init event).
    micCtx = new AC();
  }
  if (micCtx.state === 'suspended') micCtx.resume();
  return !!micCtx;
}

function startAudioProcessor(onChunk) {
  if (!micStream || micProcessor) return null;
  if (!ensureAudioContext()) return null;
  if (micCtx.state === 'suspended') {
    const resumeOnGesture = () => {
      if (micCtx && micCtx.state === 'suspended') micCtx.resume();
    };
    document.addEventListener('pointerdown', resumeOnGesture, { once: true });
    document.addEventListener('keydown', resumeOnGesture, { once: true });
  }
  micSource = micCtx.createMediaStreamSource(micStream);
  micProcessor = micCtx.createScriptProcessor(4096, 1, 1);
  const mute = micCtx.createGain();
  mute.gain.value = 0;

  // Watchdog: alert if the mic keeps sending digital-zero frames.
  let silentSeconds = 0;
  let warnedSilence = false;
  const ctxRate = () => (micCtx ? micCtx.sampleRate : 48000);

  micProcessor.onaudioprocess = (e) => {
    const input = e.inputBuffer.getChannelData(0);
    const int16 = new Int16Array(input.length);
    let peak = 0;
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      const abs = s < 0 ? -s : s;
      if (abs > peak) peak = abs;
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    if (peak === 0) {
      silentSeconds += input.length / ctxRate();
      if (!warnedSilence && silentSeconds >= 3 && (speechActive || wakeStreamActive)) {
        warnedSilence = true;
        const msg = `[MIC] Capturing pure silence for ${silentSeconds.toFixed(1)}s ` +
          `(context ${ctxRate()} Hz, track "${micStream?.getAudioTracks()[0]?.label || '?'}"). ` +
          'Check Windows microphone privacy settings or pick another input device.';
        console.warn('[Mic]', msg);
        if (typeof appendLog === 'function') appendLog(msg);
        showToast(t('mic_silence_toast'));
      }
    } else {
      silentSeconds = 0;
    }
    onChunk(new Uint8Array(int16.buffer));
  };
  micSource.connect(micProcessor);
  micProcessor.connect(mute);
  mute.connect(micCtx.destination);
  console.log('[Mic] Processor started | context rate:', micCtx.sampleRate);
  return micCtx.sampleRate || 16000;
}

function stopAudioProcessor() {
  if (micProcessor) {
    try { micProcessor.disconnect(); } catch (e) {}
    micProcessor = null;
  }
  if (micSource) {
    try { micSource.disconnect(); } catch (e) {}
    micSource = null;
  }
}

function releaseMic() {
  speechActive = false;
  wakeStreamActive = false;
  stopAudioProcessor();
  if (micStream) {
    micStream.getTracks().forEach((t) => t.stop());
    micStream = null;
  }
  if (micCtx) {
    micCtx.close().catch(() => {});
    micCtx = null;
  }
}

function setRecordingVisual(on) {
  const input = document.getElementById('chatInput');
  if (!input) return;
  input.style.borderColor = on ? 'var(--accent)' : '';
  if (on) input.placeholder = t('release_space');
  else updateInputPlaceholder();
}

async function startPushToTalk() {
  if (speechActive) return;
  ensureAudioContext();
  const ok = await requestMic();
  if (!ok) return;
  populateAudioDevices();
  speechActive = true;
  setRecordingVisual(true);
  const rate = startAudioProcessor((pcm) => {
    if (speechActive) wsSend('mic', { event: 'audio', data: bytesToBase64(pcm) }, true);
  });
  wsSend('mic', { event: 'init', rate: rate || 16000 });
  wsSend('mic', { event: 'start' });
}

function stopPushToTalk() {
  if (!speechActive) return;
  speechActive = false;
  setRecordingVisual(false);
  stopAudioProcessor();
  wsSend('mic', { event: 'stop' });
  window.waitingSpeechResult = true;
  getOrCreateUserTypingBubble();
}

async function startWakeStream() {
  if (wakeStreamActive) return;
  ensureAudioContext();
  const ok = await requestMic();
  if (!ok) return;
  wakeStreamActive = true;
  const rate = startAudioProcessor((pcm) => {
    if (!wakeStreamActive) return;
    wsSend('mic', { event: 'audio', data: bytesToBase64(pcm) }, true);
  });
  wsSend('mic', { event: 'init', rate: rate || 16000 });
}

function stopWakeStream() {
  wakeStreamActive = false;
  stopAudioProcessor();
}

function ensureVoiceStreamStarted() {
  if (window.inputService === 'wake_word' && window.serviceRunning && !wakeStreamActive) {
    startWakeStream();
  }
}

// ── Push-to-talk: hold Space to talk ──
document.addEventListener('keydown', (e) => {
  if (e.key !== ' ' || e.repeat) return;
  if (window.inputService !== 'speech' || !window.serviceRunning) return;
  if (window.aiBusy) {
    showBusyWarning();
    e.preventDefault();
    return;
  }
  const t = document.activeElement;
  if (t && t !== document.body && t.id !== 'chatInput') return;
  const chatInputEl = document.getElementById('chatInput');
  if (t === chatInputEl && chatInputEl.value.trim().length > 0) return;
  e.preventDefault();
  startPushToTalk();
});

document.addEventListener('keyup', (e) => {
  if (e.key !== ' ') return;
  if (speechActive) {
    e.preventDefault();
    stopPushToTalk();
  }
});

window.addEventListener('blur', () => {
  if (speechActive) stopPushToTalk();
});

document.addEventListener('pointerdown', ensureVoiceStreamStarted);

const inputServiceSelect = document.querySelector('[data-key="user_input_service"]');
if (inputServiceSelect) {
  inputServiceSelect.addEventListener('change', () => {
    window.inputService = inputServiceSelect.value;
    updateInputPlaceholder();
  });
}

const audioDeviceSelect = document.getElementById('audioDeviceSelect');
if (audioDeviceSelect) {
  audioDeviceSelect.addEventListener('change', async () => {
    // Re-acquire the mic so the newly selected device takes effect right
    // away instead of after a full service restart.
    if (!micStream || speechActive) return;
    const wasWake = wakeStreamActive;
    releaseMic();
    if (wasWake && window.serviceRunning && window.inputService === 'wake_word') {
      await startWakeStream();
    } else if (window.serviceRunning && window.inputService === 'speech') {
      await requestMic();
    }
    populateAudioDevices();
  });
}
