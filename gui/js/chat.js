// ── Chat state ──
window.stagedMsg = null;
window.userStagedMsg = null;
window.aiBusy = false;
window.waitingSpeechResult = false;

function showBusyWarning() {
  const el = document.getElementById('busyWarning');
  if (el) el.classList.add('visible');
}

function hideBusyWarning() {
  const el = document.getElementById('busyWarning');
  if (el) el.classList.remove('visible');
}

function getOrCreateUserTypingBubble() {
  const msgs = document.getElementById('chatMessages');
  if (!msgs) return null;
  if (window.userStagedMsg && window.userStagedMsg.isConnected) return window.userStagedMsg;
  const bubble = document.createElement('div');
  bubble.className = 'msg user-msg';
  const dots = document.createElement('span');
  dots.className = 'typing-dots';
  bubble.appendChild(dots);
  msgs.appendChild(bubble);
  msgs.scrollTop = msgs.scrollHeight;
  window.userStagedMsg = bubble;
  return bubble;
}

function removeUserTypingBubble() {
  if (window.userStagedMsg && window.userStagedMsg.isConnected) {
    window.userStagedMsg.remove();
  }
  window.userStagedMsg = null;
}

function getOrCreateTypingBubble() {
  const msgs = document.getElementById('chatMessages');
  if (!msgs) return null;
  if (window.stagedMsg && window.stagedMsg.isConnected) return window.stagedMsg;
  const bubble = document.createElement('div');
  bubble.className = 'msg ai-msg';
  const dots = document.createElement('span');
  dots.className = 'typing-dots';
  bubble.appendChild(dots);
  msgs.appendChild(bubble);
  msgs.scrollTop = msgs.scrollHeight;
  window.stagedMsg = bubble;
  return bubble;
}

function replaceTypingBubble(text) {
  const msgs = document.getElementById('chatMessages');
  if (!msgs) return;
  if (window.stagedMsg && window.stagedMsg.isConnected) {
    window.stagedMsg.textContent = text;
    window.stagedMsg = null;
  } else {
    const bubble = document.createElement('div');
    bubble.className = 'msg ai-msg';
    bubble.textContent = text;
    msgs.appendChild(bubble);
  }
  msgs.scrollTop = msgs.scrollHeight;
  // NOTE: aiBusy stays true here; it is only cleared by the server's
  // "tts_done" event once the AI has finished speaking.
}

// ── Chat Panel Resize ──
const chatPanel = document.getElementById('chatPanel');
const sideStack = document.getElementById('sideStack');
const resizeHandle = document.getElementById('resizeHandle');
let isResizing = false;

resizeHandle.addEventListener('mousedown', (e) => {
  isResizing = true;
  document.body.style.cursor = 'ew-resize';
  resizeHandle.classList.add('active');
  e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
  if (!isResizing) return;
  const rect = sideStack.getBoundingClientRect();
  let newWidth = e.clientX - rect.left;
  newWidth = Math.max(280, Math.min(700, newWidth));
  sideStack.style.width = newWidth + 'px';
});

document.addEventListener('mouseup', () => {
  if (isResizing) {
    isResizing = false;
    document.body.style.cursor = '';
    resizeHandle.classList.remove('active');
  }
});

// ── Send chat message ──
function sendChatMessage(msg) {
  msg = String(msg || '').trim();
  if (!msg) return;

  console.log(`[WS] chat message: "${msg}"`);
  wsSend('chat', { message: msg });

  const msgs = document.getElementById('chatMessages');
  msgs.querySelector('.placeholder')?.remove();

  const bubble = document.createElement('div');
  bubble.style.cssText = 'align-self:flex-end;background:var(--panel);color:var(--text);padding:10px 14px;border-radius:14px 14px 4px 14px;max-width:80%;word-wrap:break-word;white-space:pre-wrap;font-size:14px;';
  bubble.textContent = msg;
  msgs.appendChild(bubble);
  msgs.scrollTop = msgs.scrollHeight;
}
