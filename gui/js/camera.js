// ── Camera Toggle ──
let cameraStream = null;
const btnCamera = document.getElementById('btnCamera');
const cameraSlash = document.getElementById('cameraSlash');

function getCameraResolution() {
  const select = document.querySelector('[data-key="camera_resolution"]');
  if (!select) return {};
  const val = select.value;
  if (!val || !val.includes('x')) return {};
  const [w, h] = val.split('x').map(Number);
  return { width: { ideal: w }, height: { ideal: h } };
}

async function startCamera() {
  try {
    const constraints = { video: getCameraResolution() };
    cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
    const video = document.getElementById('cameraFeed');
    video.srcObject = cameraStream;
    await video.play();
    video.classList.add('active');
    document.getElementById('cameraPlaceholder').classList.add('hidden');
    btnCamera.style.borderColor = 'var(--accent)';
    cameraSlash.style.display = 'none';
  } catch (err) {
    console.log('Camera not available:', err.message);
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop());
    cameraStream = null;
  }
  const video = document.getElementById('cameraFeed');
  video.classList.remove('active');
  video.srcObject = null;
  document.getElementById('cameraPlaceholder').classList.remove('hidden');
  btnCamera.style.borderColor = '';
  cameraSlash.style.display = 'block';
}

btnCamera.addEventListener('click', () => {
  if (cameraStream) { stopCamera(); }
  else { startCamera(); }
});

// ── Keep Camera Aspect Ratio ──
const keepAspect = document.getElementById('keepAspect');
const camVideo = document.getElementById('cameraFeed');

keepAspect.addEventListener('change', () => {
  camVideo.classList.toggle('contain', keepAspect.checked);
});
