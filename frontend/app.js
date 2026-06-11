const API_BASE = "";

const el = (id) => document.getElementById(id);

const OUTPUT_FORMATS = {
  audio: [
    { value: "mp3", label: "MP3" },
    { value: "wav", label: "WAV" },
  ],
  video: [{ value: "mp4", label: "MP4" }],
};

const state = {
  pollTimer: null,
  currentJob: null,
};

function setBadge(text, tone = "soft") {
  const badge = el("jobBadge");
  badge.textContent = text;
  badge.className = tone === "success" ? "pill pill--soft" : "badge";
  if (tone === "success") {
    badge.style.borderColor = "rgba(34, 197, 94, 0.35)";
    badge.style.background = "rgba(34, 197, 94, 0.12)";
  } else if (tone === "danger") {
    badge.style.borderColor = "rgba(239, 68, 68, 0.35)";
    badge.style.background = "rgba(239, 68, 68, 0.12)";
  } else {
    badge.style.borderColor = "";
    badge.style.background = "";
  }
}

function updateHealth(text, ok) {
  const pill = el("apiHealth");
  pill.textContent = text;
  pill.style.borderColor = ok
    ? "rgba(34, 197, 94, 0.35)"
    : "rgba(250, 204, 21, 0.35)";
  pill.style.background = ok
    ? "rgba(34, 197, 94, 0.12)"
    : "rgba(250, 204, 21, 0.12)";
}

function inferMediaKindFromName(name = "") {
  const lower = name.toLowerCase();
  if (
    lower.endsWith(".mp3") ||
    lower.endsWith(".m4a") ||
    lower.endsWith(".wav") ||
    lower.endsWith(".aac")
  ) {
    return "audio";
  }
  if (
    lower.endsWith(".mp4") ||
    lower.endsWith(".webm") ||
    lower.endsWith(".mov") ||
    lower.endsWith(".mkv")
  ) {
    return "video";
  }
  return "audio";
}

function formatShiftLabel(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return "—";
  }
  return `${numeric > 0 ? "+" : ""}${numeric} semitones`;
}

function setSelectOptions(select, options, preferredValue) {
  select.replaceChildren();
  options.forEach(({ value, label }) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (value === preferredValue) {
      option.selected = true;
    }
    select.appendChild(option);
  });
  if (
    preferredValue &&
    options.some((option) => option.value === preferredValue)
  ) {
    select.value = preferredValue;
  }
}

function configureOutputFormat(selectId, kind, preferredValue) {
  const select = el(selectId);
  const options = OUTPUT_FORMATS[kind] || OUTPUT_FORMATS.audio;
  const preferred = options.some((option) => option.value === preferredValue)
    ? preferredValue
    : options[0].value;
  setSelectOptions(select, options, preferred);
  select.disabled = options.length === 1;
  return select.value;
}

function updateUploadMode(kind) {
  const outputFormat = configureOutputFormat(
    "uploadFormat",
    kind,
    kind === "video" ? "mp4" : "mp3",
  );
  const accepted =
    kind === "video" ? "MP4, WebM, MOV, MKV" : "MP3, WAV, M4A, AAC";
  const outputs = kind === "video" ? "MP4" : "MP3 or WAV";
  el("uploadHint").textContent =
    `Accepted formats: ${accepted}. Output format: ${outputs}.`;
  return outputFormat;
}

function updateYouTubeMode() {
  const outputFormat = configureOutputFormat("youtubeFormat", "video", "mp4");
  el("youtubeFormat").title = "YouTube jobs currently export as MP4";
  return outputFormat;
}

function setPlayerMode(kind, title, description) {
  const isVideo = kind === "video";
  document.body.classList.toggle("video-mode", isVideo);
  el("playerTitle").textContent = title;
  el("playerText").textContent = description;
  el("audioPlayer").hidden = isVideo;
  el("videoPlayer").hidden = !isVideo;
  el("playerPlaceholder").style.display = "flex";
  el("audioPlayer").removeAttribute("src");
  el("videoPlayer").removeAttribute("src");
  el("playerStage").style.display = "block";
}

function setPlayerContent(downloadUrl, mediaKind) {
  const audioPlayer = el("audioPlayer");
  const videoPlayer = el("videoPlayer");
  const placeholder = el("playerPlaceholder");

  if (!downloadUrl) {
    placeholder.style.display = "flex";
    audioPlayer.removeAttribute("src");
    videoPlayer.removeAttribute("src");
    return;
  }

  // Hide placeholder and set the appropriate player source
  placeholder.style.display = "none";
  if (mediaKind === "video") {
    videoPlayer.src = downloadUrl;
  } else {
    audioPlayer.src = downloadUrl;
  }
}

function setOutputReady(downloadUrl) {
  const link = el("downloadLink");
  const pill = el("downloadPill");
  const outputText = el("outputText");

  if (!downloadUrl) {
    pill.textContent = "Download unavailable";
    pill.style.borderColor = "";
    pill.style.background = "";
    link.classList.add("button--disabled");
    link.setAttribute("aria-disabled", "true");
    link.removeAttribute("href");
    outputText.textContent =
      "When a job completes, the backend download link will be surfaced here.";
    return;
  }

  pill.textContent = "Ready to download";
  pill.style.borderColor = "rgba(34, 197, 94, 0.35)";
  pill.style.background = "rgba(34, 197, 94, 0.12)";
  link.classList.remove("button--disabled");
  link.removeAttribute("aria-disabled");
  link.href = downloadUrl;
  outputText.textContent =
    "The processed artifact is ready. Use the button below to fetch the file.";
}

function renderJob(job) {
  state.currentJob = job;
  el("jobStatus").textContent = job.status || "unknown";
  el("jobSource").textContent = job.source_url || job.original_name || "—";
  el("jobShift").textContent = formatShiftLabel(job.shift_semitones);
  el("jobFormat").textContent = (job.output_format || "—")
    .toString()
    .toUpperCase();

  const status = job.status || "unknown";
  if (status === "completed") {
    setBadge("Completed", "success");
    const downloadUrl = job.download_url
      ? job.download_url
      : `/download/${job.job_id || job.id}`;
    setOutputReady(downloadUrl);
    setPlayerContent(downloadUrl, job.media_kind);
  } else if (status === "failed") {
    setBadge("Failed", "danger");
    setOutputReady(null);
    setPlayerContent(null, job.media_kind);
    el("outputText").textContent =
      job.error ||
      "The job failed. Check the backend logs for more information.";
  } else {
    setBadge(status.charAt(0).toUpperCase() + status.slice(1));
    setOutputReady(null);
  }
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers:
      options.body instanceof FormData
        ? { ...(options.headers || {}) }
        : { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail || data?.message || response.statusText;
    throw new Error(detail);
  }
  return data;
}

async function checkHealth() {
  try {
    await fetchJson("/healthz");
    updateHealth("API: online", true);
  } catch {
    updateHealth("API: offline", false);
  }
}

function startPolling(jobId) {
  clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async () => {
    try {
      const job = await fetchJson(`/jobs/${jobId}`);
      renderJob(job);
      if (job.status === "completed" || job.status === "failed") {
        clearInterval(state.pollTimer);
      }
    } catch (error) {
      clearInterval(state.pollTimer);
      setBadge("Error", "danger");
      el("outputText").textContent = error.message;
    }
  }, 1500);
}

async function handleUploadSubmit(event) {
  event.preventDefault();
  const fileInput = el("uploadFile");
  const file = fileInput.files?.[0];
  if (!file) {
    setBadge("Missing file", "danger");
    el("outputText").textContent = "Pick a media file before uploading.";
    return;
  }

  const kind = inferMediaKindFromName(file.name);
  const shift = Number(el("uploadShift").value || 0);
  const outputFormat = el("uploadFormat").value;
  setPlayerMode(
    kind,
    `${kind === "video" ? "Video" : "Audio"} preview ready`,
    `Selected file: ${file.name}`,
  );

  const submitBtn = el("uploadForm").querySelector("button[type=submit]");
  submitBtn.disabled = true;
  setBadge("Uploading…");
  el("outputText").textContent = "Submitting the upload to the backend…";

  const formData = new FormData();
  formData.append("file", file);
  formData.append("shift_semitones", String(shift));
  formData.append("output_format", outputFormat);

  try {
    const data = await fetchJson("/ingest/upload", {
      method: "POST",
      body: formData,
    });

    renderJob({
      ...data,
      original_name: file.name,
      status: data.status || "queued",
      shift_semitones: data.shift_semitones ?? shift,
      output_format: data.output_format || outputFormat,
      media_kind: data.media_kind || kind,
    });
    startPolling(data.job_id || data.id);
  } catch (error) {
    setBadge("Upload failed", "danger");
    el("outputText").textContent = error.message || "Upload failed. Check your file and try again.";
  } finally {
    submitBtn.disabled = false;
  }
}

async function handleYoutubeSubmit(event) {
  event.preventDefault();
  const url = el("youtubeUrl").value.trim();
  if (!url) {
    setBadge("Missing URL", "danger");
    el("outputText").textContent =
      "Paste a valid YouTube URL before submitting.";
    return;
  }

  const shift = Number(el("youtubeShift").value || 0);
  const outputFormat = el("youtubeFormat").value;
  setPlayerMode("video", "YouTube source queued", url);

  const submitBtn = el("youtubeForm").querySelector("button[type=submit]");
  submitBtn.disabled = true;
  setBadge("Submitting…");
  el("outputText").textContent = "Submitting the YouTube URL to the backend…";

  try {
    const data = await fetchJson("/ingest/youtube", {
      method: "POST",
      body: JSON.stringify({
        url,
        shift_semitones: shift,
        output_format: outputFormat,
      }),
    });

    renderJob({
      ...data,
      source_url: url,
      status: data.status || "queued",
      shift_semitones: data.shift_semitones ?? shift,
      output_format: data.output_format || outputFormat,
      media_kind: data.media_kind || "video",
    });
    startPolling(data.job_id || data.id);
  } catch (error) {
    setBadge("Request failed", "danger");
    el("outputText").textContent = error.message || "Could not reach the backend. Please try again.";
  } finally {
    submitBtn.disabled = false;
  }
}

function init() {
  updateUploadMode("audio");
  updateYouTubeMode();

  el("uploadForm").addEventListener("submit", (event) => {
    handleUploadSubmit(event);
  });

  el("youtubeForm").addEventListener("submit", (event) => {
    handleYoutubeSubmit(event);
  });

  el("uploadFile").addEventListener("change", () => {
    const file = el("uploadFile").files?.[0];
    if (file) {
      const kind = inferMediaKindFromName(file.name);
      updateUploadMode(kind);
      el("uploadHint").textContent =
        `Selected ${file.name}. The preview will switch to ${kind} mode.`;
      setPlayerMode(
        kind,
        `${kind === "video" ? "Video" : "Audio"} preview placeholder`,
        `Ready for ${file.name}`,
      );
    }
  });

  setPlayerMode(
    "audio",
    "No media loaded yet",
    "Your preview controls will appear here once an audio or video job is created.",
  );
  setOutputReady(null);
  checkHealth();
}

function loadJobById(jobId) {
  fetchJson(`/jobs/${jobId}`)
    .then((job) => {
      renderJob(job);
      // Scroll to results section
      el("results").scrollIntoView({ behavior: "smooth" });
      // If job is still processing, start polling
      if (job.status === "queued" || job.status === "running") {
        startPolling(jobId);
      }
    })
    .catch((error) => {
      setBadge("Error loading job", "danger");
      el("outputText").textContent = error.message;
    });
}

init();
