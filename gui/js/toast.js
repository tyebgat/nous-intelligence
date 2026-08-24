// ── Toast notification ──
let toastMode = null;
let busyToasts = {};

function showToast(text, opts = {}) {
  const container = document.getElementById('toastContainer');
  if (!container) return null;

  const { busy = false, duration = 2500 } = opts;
  toastMode = busy ? text : null;

  const toast = document.createElement('div');
  toast.className = `toast ${busy ? 'busy' : ''}`;

  toast.innerHTML = `
    <span class="loader"></span>
    <span class="toast-text">${text}</span>
  `;

  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  if (busy) {
    busyToasts[text] = toast;
  }

  if (duration > 0 && !busy) {
    setTimeout(() => {
      removeToastElement(toast);
      if (toastMode === text) toastMode = null;
    }, duration);
  }

  return toast;
}

function hideToast(specificToast) {
  if (specificToast && specificToast instanceof HTMLElement) {
    removeToastElement(specificToast);
  } else if (specificToast && typeof specificToast === 'string' && busyToasts[specificToast]) {
    removeToastElement(busyToasts[specificToast]);
    delete busyToasts[specificToast];
  } else {
    toastMode = null;
    busyToasts = {};
    const container = document.getElementById('toastContainer');
    if (container) {
      container.querySelectorAll('.toast').forEach(removeToastElement);
    }
  }
}

function removeToastElement(toast) {
  toast.classList.remove('show');
  toast.addEventListener('transitionend', () => {
    toast.remove();
  }, { once: true });
}
