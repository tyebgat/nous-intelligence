// ── Init panel / terminal logging ──
const initOverlay = document.getElementById('initOverlay');
const initSpinner = document.getElementById('initSpinner');
const initStatus = document.getElementById('initStatus');
const terminalLog = document.getElementById('terminalLog');

const ANSI_COLORS = {
  30: '#000000', 31: '#ff5555', 32: '#50fa7b', 33: '#f1fa8c',
  34: '#8be9fd', 35: '#ff79c6', 36: '#4ad2d2', 37: '#f8f8f2',
  90: '#777777', 91: '#ff6e6e', 92: '#69ff94', 93: '#ffffa5',
  94: '#d6acff', 95: '#ff92df', 96: '#a4ffff', 97: '#ffffff'
};

function ansiToHtml(line) {
  line = String(line).replace(/\r/g, '');
  const escaped = line
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  const re = /\x1b\[([0-9;]*)m/g;
  let out = '';
  let cur = null;
  let last = 0;
  let m;
  while ((m = re.exec(escaped)) !== null) {
    out += escaped.slice(last, m.index);
    last = re.lastIndex;
    const seq = m[1] ? m[1].split(';') : ['0'];
    let next = cur;
    for (const c of seq) {
      if (c === '0' || c === '') next = null;
      else if (c === '38') next = '#FFA500';
      else if (ANSI_COLORS[c]) next = ANSI_COLORS[c];
    }
    if (next !== cur) {
      if (cur) out += '</span>';
      if (next) out += `<span style="color:${next};">`;
      cur = next;
    }
  }
  out += escaped.slice(last);
  if (cur) out += '</span>';
  return out;
}

function stripAnsi(line) {
  return String(line).replace(/\x1b\[[0-9;]*m/g, '');
}

function cleanInitLabel(line) {
  return stripAnsi(line)
    .trim()
    .replace(/^\[[^\]]*\]\s*/, '')
    .replace(/\.{3,}$/, '');
}

function updateInitStatus(line) {
  if (!initStatus || !initOverlay || !initOverlay.classList.contains('open')) return;
  const raw = stripAnsi(line);
  if (!/(initializ|inicializ|arranc|conect|connect|start|prepar|ready|listo|online|fail|error|fallo|download|descarg)/i.test(raw)) return;
  initStatus.textContent = cleanInitLabel(raw);
}

function appendLog(line) {
  const raw = String(line);
  const html = ansiToHtml(raw);
  if (terminalLog) {
    terminalLog.innerHTML += html + '\n';
    terminalLog.scrollTop = terminalLog.scrollHeight;
  }
  updateInitStatus(raw);
  if (raw.indexOf('All requested AI services are online') !== -1 ||
      raw.indexOf('están en línea') !== -1) {
    showInitOk();
  }
}

function openInitPanel() {
  if (initStatus) initStatus.textContent = '';
  if (initSpinner) initSpinner.classList.remove('finished');
  const ok = document.getElementById('initOk');
  if (ok) ok.classList.remove('visible');
  if (initOverlay) initOverlay.classList.add('open');
}

function showInitOk() {
  if (initSpinner) initSpinner.classList.add('finished');
  const ok = document.getElementById('initOk');
  if (ok) ok.classList.add('visible');
}

function closeInitPanel() {
  if (initOverlay) initOverlay.classList.remove('open');
}
