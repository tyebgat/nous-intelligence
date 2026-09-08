// ── Settings sync ──
let originalSettings = null;
let themeUserSelected = false;

function loadSettings() {
  return fetch('/api/settings')
    .then((res) => res.json())
    .then((config) => {
      originalSettings = config;
      window.inputService = config.user_input_service || 'console';
      updateInputPlaceholder();
      document.querySelectorAll('[data-key]').forEach((el) => {
        const key = el.dataset.key;
        if (!(key in config)) return;
        if (themeUserSelected && key === 'theme') return;
        const value = config[key];
        if (el.type === 'checkbox') {
          el.checked = value === true;
        } else {
          el.value = value;
        }
      });
      if (!themeUserSelected) applyTheme(config.theme || 'dark');
      updateBlur();
      if (typeof applyI18n === 'function') applyI18n(config.app_language || 'english');
      if (typeof updateTtsDisabled === 'function') updateTtsDisabled();
      if (typeof updateChatbotDisabled === 'function') updateChatbotDisabled();
      if (typeof updateSttDisabled === 'function') updateSttDisabled();
    })
    .catch((err) => console.error('Failed to load settings', err));
}

function applyTheme(name) {
  const link = document.getElementById('themeStylesheet');
  if (!link || !name) return;
  link.href = '/gui/themes/' + name + '.css';
}

const themeSelect = document.querySelector('[data-key="theme"]');
if (themeSelect) {
  themeSelect.addEventListener('change', (e) => {
    applyTheme(e.target.value);
    themeUserSelected = true;
  });
}

// ── Load editable text files ──
function loadTextFiles() {
  document.querySelectorAll('[data-file]').forEach((el) => {
    const name = el.dataset.file;
    fetch('/api/text/' + name)
      .then((res) => res.json())
      .then((data) => { el.value = data.text || ''; })
      .catch((err) => console.error('Failed to load text file', name, err));
  });
}

function saveTextFiles() {
  document.querySelectorAll('[data-file]').forEach((el) => {
    const name = el.dataset.file;
    fetch('/api/text/' + name, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: el.value }),
    }).catch((err) => console.error('Failed to save text file', name, err));
  });
}

// ── API keys ──
function loadEnvKeys() {
  fetch('/api/env')
    .then((res) => res.json())
    .then((env) => {
      document.querySelectorAll('[data-env-key]').forEach((el) => {
        const key = el.dataset.envKey;
        el.value = env[key] || '';
      });
    })
    .catch((err) => console.error('Failed to load env keys', err));
}

function saveEnvKeys() {
  const data = {};
  document.querySelectorAll('[data-env-key]').forEach((el) => {
    data[el.dataset.envKey] = el.value;
  });
  fetch('/api/env', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
    .then((res) => res.json())
    .then(() => console.log('[POST] /api/env saved'))
    .catch((err) => console.error('Failed to save env keys', err));
}

// ── Blur Intensity ──
const blurSlider = document.getElementById('blurIntensity');
const blurSpots = document.querySelectorAll('.blur-spot');
function updateBlur() {
  blurSpots.forEach(spot => { spot.style.filter = `blur(${blurSlider.value}px)`; });
}
blurSlider.addEventListener('input', updateBlur);
updateBlur();

// ── Apply settings ──
function collectChangedSettings() {
  const diff = {};
  document.querySelectorAll('[data-key]').forEach((el) => {
    const key = el.dataset.key;
    if (originalSettings === null || !(key in originalSettings)) return;
    const value = el.type === 'checkbox'
      ? el.checked
      : el.type === 'number'
        ? parseFloat(el.value)
        : el.value;
    if (originalSettings[key] !== value) diff[key] = value;
  });
  return diff;
}

function applySettings() {
  const diff = collectChangedSettings();
  console.log('[POST] /api/settings', diff);
  fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(diff),
  })
    .then((res) => res.json())
    .then((data) => {
      originalSettings = data.config;
      if (typeof applyI18n === 'function' && data.config && data.config.app_language) {
        applyI18n(data.config.app_language);
      }
      if (data.config && data.config.user_input_service) {
        window.inputService = data.config.user_input_service;
        updateInputPlaceholder();
      }
      console.log('[POST] settings saved', data.config);
    })
    .catch((err) => console.error('Failed to apply settings', err));
}

// ── TTS service conditional disabling ──
const ttsService = document.querySelector('#tab-tts select');
const ttsLabels = document.querySelectorAll('#tab-tts label');

function updateTtsDisabled() {
  const val = ttsService.value;
  ttsLabels.forEach((label, i) => {
    if (i === 0) return;
    if (val === 'gtts' && i === 1) { label.classList.remove('disabled'); }
    else if (val === 'gtts') { label.classList.add('disabled'); }
    else if (val === 'openai' && (i === 2 || i === 3 || i === 4 || i === 5 || i === 6 || i === 7 || i === 8 || i === 9)) { label.classList.add('disabled'); }
    else if (val === 'pockettts' && (i === 8 || i === 9)) { label.classList.add('disabled'); }
    else { label.classList.remove('disabled'); }
  });
}

if (ttsService) {
  ttsService.addEventListener('change', updateTtsDisabled);
  updateTtsDisabled();
}

// ── Wake word threshold display ──
const wakeThreshold = document.getElementById('wakeThreshold');
const wakeThresholdVal = document.getElementById('wakeThresholdVal');
if (wakeThreshold) {
  wakeThreshold.addEventListener('input', () => {
    wakeThresholdVal.textContent = parseFloat(wakeThreshold.value).toFixed(2);
  });
}

// ── Chatbot service conditional disabling ──
const chatbotService = document.querySelectorAll('#tab-chatbot select')[1];
const chatbotLabels = document.querySelectorAll('#tab-chatbot label');

function updateChatbotDisabled() {
  const val = chatbotService.value;
  chatbotLabels.forEach((label, i) => {
    if (i === 0 || i === 1) return;
    // i===4 Model Directory, i===5 Llama Server Device (local only)
    if (val === 'openai' && (i === 4 || i === 5)) { label.classList.add('disabled'); }
    else if (val === 'test' && (i === 3 || i === 4 || i === 5)) { label.classList.add('disabled'); }
    else if (val !== 'local' && i === 5) { label.classList.add('disabled'); }
    else { label.classList.remove('disabled'); }
  });
}

if (chatbotService) {
  chatbotService.addEventListener('change', updateChatbotDisabled);
  updateChatbotDisabled();
}

// ── STT service conditional disabling ──
const sttService = document.querySelector('#tab-stt select');
const sttLabels = document.querySelectorAll('#tab-stt label');

function updateSttDisabled() {
  const val = sttService.value;
  sttLabels.forEach((label, i) => {
    if (i === 0) return;
    if (val === 'google' && i !== 3) { label.classList.add('disabled'); }
    else { label.classList.remove('disabled'); }
  });
}

if (sttService) {
  sttService.addEventListener('change', updateSttDisabled);
  updateSttDisabled();
}

function activateSettingsTab(name) {
  document.querySelectorAll('.settings-tabs .tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const t = document.querySelector('.settings-tabs .tab[data-tab="' + name + '"]');
  if (t) t.classList.add('active');
  const c = document.getElementById('tab-' + name);
  if (c) c.classList.add('active');
}

// ── Numeric settings cannot go below 0 ──
document.querySelectorAll('.tab-content input[type="number"]').forEach((inp) => {
  inp.addEventListener('change', () => {
    const v = parseFloat(inp.value);
    if (isNaN(v) || v < 0) inp.value = 0;
  });
});

// ── Setting tooltips ──
(function () {
  const TIP_DELAY = 500;
  const tip = document.createElement('div');
  tip.className = 'setting-tooltip';
  document.body.appendChild(tip);

  let showTimer = null;
  let lastX = 0;
  let lastY = 0;

  function move() {
    const pad = 14;
    const rect = tip.getBoundingClientRect();
    let x = lastX + pad;
    let y = lastY + pad;
    if (x + rect.width > window.innerWidth - 8) x = window.innerWidth - rect.width - 8;
    if (y + rect.height > window.innerHeight - 8) y = lastY - rect.height - pad;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }

  function hide() {
    clearTimeout(showTimer);
    showTimer = null;
    tip.classList.remove('visible');
    tip.textContent = '';
  }

  document.querySelectorAll('[data-tip],[data-tip-i18n]').forEach((el) => {
    // Icon shows on the right side of the setting name; hovering it shows the tooltip.
    const nameSpan = el.querySelector('.setting-name-text, span[data-i18n]');
    let icon = el.querySelector('.setting-tip-icon');
    if (!icon) {
      icon = document.createElement('span');
      icon.className = 'setting-tip-icon';
      icon.textContent = '?';
      icon.setAttribute('role', 'img');
      icon.setAttribute('aria-label', 'Help');
      if (nameSpan) {
        // Keep the icon OUT of the data-i18n span so language re-translation
        // (el.textContent = ...) can't delete it. Wrap name + icon together.
        let wrap = nameSpan.parentElement && nameSpan.parentElement.classList.contains('setting-name')
          ? nameSpan.parentElement
          : null;
        if (!wrap) {
          wrap = document.createElement('span');
          wrap.className = 'setting-name';
          nameSpan.parentNode.insertBefore(wrap, nameSpan);
          wrap.appendChild(nameSpan);
        }
        wrap.appendChild(icon);
      } else {
        el.insertBefore(icon, el.firstChild);
      }
    }

    icon.addEventListener('mouseenter', (e) => {
      hide();
      lastX = e.clientX;
      lastY = e.clientY;
      showTimer = setTimeout(() => {
        // Read at display time so the current language is used.
        const text = el.dataset.tip || el.getAttribute('data-tip') || '';
        if (!text) return;
        tip.textContent = text;
        tip.classList.add('visible');
        move();
      }, TIP_DELAY);
    });
    icon.addEventListener('mousemove', (e) => {
      lastX = e.clientX;
      lastY = e.clientY;
      if (tip.classList.contains('visible')) move();
    });
    icon.addEventListener('mouseleave', hide);
    icon.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
  });
})();
