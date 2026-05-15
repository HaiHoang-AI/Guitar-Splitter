const form = document.querySelector("#uploadForm");
const fileInput = document.querySelector("#audioFile");
const dropZone = document.querySelector("#dropZone");
const fileMeta = document.querySelector("#fileMeta");
const startButton = document.querySelector("#startButton");
const resetButton = document.querySelector("#resetButton");
const healthBadge = document.querySelector("#healthBadge");
const jobBadge = document.querySelector("#jobBadge");
const statusText = document.querySelector("#statusText");
const logOutput = document.querySelector("#logOutput");
const progressBar = document.querySelector("#progressBar");

const players = {
  original: document.querySelector("#audioOriginal"),
  guitar: document.querySelector("#audioGuitar"),
  no_guitar: document.querySelector("#audioNoGuitar"),
};

const canvases = {
  original: document.querySelector("#waveOriginal"),
  guitar: document.querySelector("#waveGuitar"),
  no_guitar: document.querySelector("#waveNoGuitar"),
};

const downloads = {
  original: document.querySelector("#downloadOriginal"),
  guitar: document.querySelector("#downloadGuitar"),
  no_guitar: document.querySelector("#downloadNoGuitar"),
};

let pollTimer = null;
let currentJobId = null;

function setBadge(element, text, type = "") {
  element.textContent = text;
  element.className = `badge ${type}`.trim();
}

function setProgress(status) {
  progressBar.classList.remove("is-active");
  if (status === "queued") {
    progressBar.style.width = "18%";
  } else if (status === "running") {
    progressBar.classList.add("is-active");
  } else if (status === "done") {
    progressBar.style.width = "100%";
  } else if (status === "error") {
    progressBar.style.width = "100%";
  } else {
    progressBar.style.width = "0%";
  }
}

function resetDownloads() {
  for (const key of Object.keys(downloads)) {
    downloads[key].href = "#";
    downloads[key].classList.add("is-disabled");
    downloads[key].setAttribute("aria-disabled", "true");
    players[key].removeAttribute("src");
    drawEmptyWave(canvases[key]);
  }
}

function enableDownload(key, url) {
  downloads[key].href = url;
  downloads[key].classList.remove("is-disabled");
  downloads[key].removeAttribute("aria-disabled");
  players[key].src = url;
  drawWaveform(url, canvases[key]).catch(() => drawReadyWave(canvases[key]));
}

function drawEmptyWave(canvas) {
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.floor(88 * dpr);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, 88);
  ctx.strokeStyle = "#cbd5e1";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(12, 44);
  ctx.lineTo(rect.width - 12, 44);
  ctx.stroke();
}

function drawReadyWave(canvas) {
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.floor(88 * dpr);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, 88);
  ctx.fillStyle = "#0f766e";
  const bars = 48;
  for (let i = 0; i < bars; i += 1) {
    const h = 12 + Math.sin(i * 0.8) * 14 + Math.cos(i * 0.31) * 9;
    const x = 12 + (i * (rect.width - 24)) / bars;
    ctx.fillRect(x, 44 - Math.abs(h), 3, Math.abs(h) * 2);
  }
}

async function drawWaveform(url, canvas) {
  const response = await fetch(url);
  const arrayBuffer = await response.arrayBuffer();
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const audioContext = new AudioContextClass();
  const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));
  const data = audioBuffer.getChannelData(0);
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.floor(88 * dpr);
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, rect.width, 88);
  ctx.fillStyle = "#0f766e";

  const bars = Math.max(40, Math.floor(rect.width / 5));
  const samplesPerBar = Math.max(1, Math.floor(data.length / bars));
  for (let i = 0; i < bars; i += 1) {
    let min = 1;
    let max = -1;
    const offset = i * samplesPerBar;
    for (let j = 0; j < samplesPerBar; j += 1) {
      const sample = data[offset + j] || 0;
      if (sample < min) min = sample;
      if (sample > max) max = sample;
    }
    const x = 12 + (i * (rect.width - 24)) / bars;
    const height = Math.max(2, (max - min) * 34);
    ctx.fillRect(x, 44 - height / 2, 3, height);
  }

  await audioContext.close();
}

async function loadHealth() {
  const response = await fetch("/api/health");
  const health = await response.json();
  fileMeta.textContent = `Max upload: ${health.max_upload_mb} MB. Model: ${health.demucs_model}.`;
  if (health.ok) {
    setBadge(healthBadge, "Ready", "badge-ok");
  } else {
    setBadge(healthBadge, "Setup", "badge-error");
    statusText.textContent = health.setup_hint;
    const missing = [
      health.ffmpeg ? "" : "FFmpeg missing",
      health.demucs_python ? "" : "Demucs missing",
    ].filter(Boolean);
    logOutput.textContent = missing.join("\n") || health.setup_hint;
  }
}

function renderJob(job) {
  setBadge(jobBadge, job.status);
  setProgress(job.status);
  currentJobId = job.id;
  logOutput.textContent = job.logs?.length ? job.logs.join("\n") : "No logs yet.";

  if (job.status === "queued") {
    statusText.textContent = "Job queued.";
    startButton.disabled = true;
  } else if (job.status === "running") {
    statusText.textContent = "Separating guitar stem. CPU runs can take several minutes.";
    startButton.disabled = true;
  } else if (job.status === "done") {
    statusText.textContent = "Done. Preview or download the generated audio.";
    setBadge(jobBadge, "Done", "badge-ok");
    startButton.disabled = false;
    clearInterval(pollTimer);
  } else if (job.status === "error") {
    statusText.textContent = job.error || "Processing failed.";
    setBadge(jobBadge, "Error", "badge-error");
    startButton.disabled = false;
    clearInterval(pollTimer);
  }

  if (job.files?.original) enableDownload("original", job.files.original);
  if (job.files?.guitar) enableDownload("guitar", job.files.guitar);
  if (job.files?.no_guitar) enableDownload("no_guitar", job.files.no_guitar);
}

async function pollJob() {
  if (!currentJobId) return;
  const response = await fetch(`/api/jobs/${currentJobId}`);
  const job = await response.json();
  renderJob(job);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files?.[0];
  if (!file) {
    statusText.textContent = "Choose an audio file first.";
    return;
  }

  resetDownloads();
  setBadge(jobBadge, "Queued", "badge-pending");
  setProgress("queued");
  logOutput.textContent = "Uploading...";
  statusText.textContent = "Uploading source audio.";
  startButton.disabled = true;

  const data = new FormData();
  data.append("audio", file);

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: data,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Upload failed.");
    }
    renderJob(payload);
    clearInterval(pollTimer);
    pollTimer = setInterval(pollJob, 1800);
  } catch (error) {
    statusText.textContent = error.message;
    setBadge(jobBadge, "Error", "badge-error");
    setProgress("error");
    startButton.disabled = false;
  }
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  if (file) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    fileMeta.textContent = `${file.name} - ${sizeMb} MB`;
  }
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropZone.classList.add("is-dragging");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("is-dragging");
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
  if (event.dataTransfer.files.length) {
    fileInput.files = event.dataTransfer.files;
    fileInput.dispatchEvent(new Event("change"));
  }
});

resetButton.addEventListener("click", () => {
  clearInterval(pollTimer);
  currentJobId = null;
  form.reset();
  resetDownloads();
  setBadge(jobBadge, "Idle");
  setProgress("idle");
  statusText.textContent = "Waiting for an upload.";
  logOutput.textContent = "No job logs yet.";
  loadHealth().catch(() => {});
});

window.addEventListener("resize", () => {
  for (const canvas of Object.values(canvases)) drawEmptyWave(canvas);
});

resetDownloads();
loadHealth().catch(() => {
  setBadge(healthBadge, "Offline", "badge-error");
  statusText.textContent = "Cannot reach the local server health endpoint.";
});
