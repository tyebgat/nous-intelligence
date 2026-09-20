// ── Chat state ──
window.stagedMsg = null;
window.userStagedMsg = null;
window.aiBusy = false;
window.waitingSpeechResult = false;

// While the AI is busy the send button becomes a stop/interrupt button.
function updateSendButton() {
  const btn = document.getElementById('btnSend');
  if (!btn) return;
  const send = document.getElementById('sendIcon');
  const stop = document.getElementById('stopIcon');
  const busy = window.aiBusy === true;
  btn.classList.toggle('stop-mode', busy);
  btn.title = busy ? t('title_stop_ai') : t('title_send');
  if (send) send.style.display = busy ? 'none' : '';
  if (stop) stop.style.display = busy ? '' : 'none';
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', updateSendButton);
} else {
  updateSendButton();
}

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
  bubble.className = 'msg user-msg msg-typing';
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

function removeTypingBubble() {
  // Drop the AI's temporary typing bubble. If a turn is interrupted or ends
  // without a chat_response, this must be cleared or the next reply will be
  // placed where the leftover bubble is sitting.
  if (window.stagedMsg && window.stagedMsg.isConnected) {
    window.stagedMsg.remove();
  }
  window.stagedMsg = null;
}

function getOrCreateTypingBubble() {
  const msgs = document.getElementById('chatMessages');
  if (!msgs) return null;
  if (window.stagedMsg && window.stagedMsg.isConnected) return window.stagedMsg;
  const bubble = document.createElement('div');
  bubble.className = 'msg ai-msg msg-typing';
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
    window.stagedMsg.classList.remove('msg-typing');
    window.stagedMsg.classList.add('msg-in');
    window.stagedMsg = null;
  } else {
    const bubble = document.createElement('div');
    bubble.className = 'msg ai-msg msg-in';
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
  bubble.className = 'msg user-msg msg-in';
  bubble.textContent = msg;
  msgs.appendChild(bubble);
  msgs.scrollTop = msgs.scrollHeight;
}
