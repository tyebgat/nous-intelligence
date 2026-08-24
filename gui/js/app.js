// ── Initialize / Splash screen ──
const initScreen = document.getElementById('initScreen');
const splashScreen = document.getElementById('splashScreen');

function hideSplash() {
  if (!splashScreen || splashScreen.classList.contains('hidden')) return;
  splashScreen.classList.add('hidden');
  setTimeout(() => { splashScreen.style.display = 'none'; }, 700);
}

function startSplash() {
  if (!splashScreen) return;
  const logo = splashScreen.querySelector('img');
  if (logo) {
    logo.style.animation = 'none';
    void logo.offsetWidth;
    logo.style.animation = '';
  }
  if (initScreen) initScreen.classList.add('hidden');
  const audio = new Audio('/gui/Splash-screen.mp3');
  let hidden = false;
  const hideOnce = () => {
    if (hidden) return;
    hidden = true;
    hideSplash();
  };
  audio.addEventListener('ended', hideOnce);
  audio.addEventListener('error', hideOnce);
  audio.play().catch(() => {
    setTimeout(hideOnce, 3000);
  });
  setTimeout(hideOnce, 15000);
}

const btnInitialize = document.getElementById('btnInitialize');
if (btnInitialize) btnInitialize.addEventListener('click', startSplash);
if (splashScreen) splashScreen.addEventListener('click', hideSplash);

// ── Settings tabs ──
document.querySelectorAll('.settings-tabs .tab').forEach(tab => {
  tab.addEventListener('click', () => {
    if (window.serviceRunning && tab.dataset.tab !== 'appearance') {
      showWarning(t('only_when_stopped'), t('ok'));
      activateSettingsTab('appearance');
      return;
    }
    activateSettingsTab(tab.dataset.tab);
  });
});

// ── Button handlers ──
function refreshStatus() {
  fetch('/api/status')
    .then((res) => res.json())
    .then((data) => {
      const running = data.running === true;
      window.serviceRunning = running;
      if (data.voice_mode !== undefined) {
        window.inputService = data.voice_mode || 'console';
        updateInputPlaceholder();
      }
      setServiceStatus(running ? 'online' : 'off');
      if (running && window.inputService === 'wake_word') startWakeStream();
      else if (running && window.inputService === 'speech') requestMic();
      else if (!running) releaseMic();
    })
    .catch(() => setServiceStatus('off'));
}

document.getElementById('btnStart').addEventListener('click', () => {
  console.log('[WS] POST /api/start');
  setServiceStatus('starting');
  openInitPanel();
  wsSend('start', {});
});

document.getElementById('btnStop').addEventListener('click', () => {
  console.log('[WS] POST /api/stop');
  setServiceStatus('off');
  wsSend('stop', {});
});

// ── Terminal toggle ──
const btnTerminal = document.getElementById('btnTerminal');
const terminalPanel = document.getElementById('terminalPanel');

btnTerminal.addEventListener('click', () => {
  const visible = terminalPanel.classList.toggle('visible');
  btnTerminal.classList.toggle('active', visible);
});

document.getElementById('terminalClear').addEventListener('click', () => {
  if (terminalLog) terminalLog.textContent = '';
});

document.getElementById('initOk').addEventListener('click', closeInitPanel);

document.getElementById('btnSettings').addEventListener('click', () => {
  activateSettingsTab('appearance');
  document.getElementById('settingsOverlay').classList.add('open');
  loadSettings().then(() => {
    loadTextFiles();
    loadEnvKeys();
    populateAudioDevices();
  });
});

document.getElementById('refreshDevicesBtn').addEventListener('click', (e) => {
  e.preventDefault();
  populateAudioDevices();
});

document.querySelectorAll('.browse-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    const type = btn.dataset.type || 'file';
    const ext = btn.dataset.ext || '';
    const input = btn.parentElement.querySelector('input[type="text"]');
    fetch('/api/browse?type=' + encodeURIComponent(type) + '&ext=' + encodeURIComponent(ext))
      .then((res) => res.json())
      .then((data) => {
        if (data.path && input) input.value = data.path;
      })
      .catch((err) => console.error('Browse failed', err));
  });
});

document.getElementById('settingsClose').addEventListener('click', () => {
  document.getElementById('settingsOverlay').classList.remove('open');
});

document.getElementById('settingsOverlay').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) {
    document.getElementById('settingsOverlay').classList.remove('open');
  }
});

document.getElementById('settingsApply').addEventListener('click', () => {
  applySettings();
  saveTextFiles();
  saveEnvKeys();
  document.getElementById('settingsOverlay').classList.remove('open');
  showToast(t('settings_applied'));
  try {
    new Audio('/gui/notif.mp3').play();
  } catch (e) { /* audio not available */ }
});

// ── Warning modal ──
function showWarning(message, okText) {
  const text = document.getElementById('warningText');
  const ok = document.getElementById('warningOk');
  if (text) text.textContent = message;
  if (ok) ok.textContent = okText || 'Ok';
  const overlay = document.getElementById('warningOverlay');
  if (overlay) overlay.classList.add('open');
}

const warningOverlay = document.getElementById('warningOverlay');
if (warningOverlay) {
  const ok = document.getElementById('warningOk');
  if (ok) ok.addEventListener('click', () => warningOverlay.classList.remove('open'));
  warningOverlay.addEventListener('click', (e) => {
    if (e.target === warningOverlay) warningOverlay.classList.remove('open');
  });
}

document.getElementById('btnGithub').addEventListener('click', () => {
  window.open('https://github.com/tyebgat/nous-intelligence', '_blank');
});

// ── Clear chat ──
document.getElementById('btnClearChat').addEventListener('click', () => {
  const msgs = document.getElementById('chatMessages');
  if (!msgs) return;
  msgs.innerHTML = '';
  const ph = document.createElement('div');
  ph.className = 'placeholder';
  ph.textContent = t('chat_placeholder_start');
  msgs.appendChild(ph);
  window.stagedMsg = null;
  window.userStagedMsg = null;
  window.aiBusy = false;
  window.waitingSpeechResult = false;
  hideBusyWarning();
  hideToast();
});

// ── Chat send ──
document.getElementById('btnSend').addEventListener('click', () => {
  if (window.aiBusy) {
    showBusyWarning();
    return;
  }
  const input = document.getElementById('chatInput');
  sendChatMessage(input.value);
  input.value = '';
});

document.getElementById('chatInput').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.altKey && !e.shiftKey) {
    e.preventDefault();
    document.getElementById('btnSend').click();
  }
});

// ── Init ──
refreshStatus();
connectWebSocket();
