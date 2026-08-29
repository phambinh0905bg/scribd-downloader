// Main Frontend Application Logic
let activeEventSource = null;
let activePollingInterval = null;
let countdownTimerInterval = null;
let currentTaskId = null;
let currentMode = "scribd"; // "scribd" or "youtube"

// Navigation Tabs
const tabScribd = document.getElementById("tab-scribd");
const tabYouTube = document.getElementById("tab-youtube");
const viewScribd = document.getElementById("view-scribd");
const viewYouTube = document.getElementById("view-youtube");

// Sections
const progressSection = document.getElementById("progress-section");
const resultSection = document.getElementById("result-section");
const errorSection = document.getElementById("error-section");

// Scribd Elements
const scribdForm = document.getElementById("scribd-form");
const scribdUrlInput = document.getElementById("scribd-url-input");
const scribdPagesInput = document.getElementById("scribd-pages-input");
const btnScribdSubmit = document.getElementById("btn-scribd-submit");
const btnScribdPaste = document.getElementById("btn-scribd-paste");

// YouTube Elements
const ytForm = document.getElementById("youtube-form");
const ytUrlInput = document.getElementById("yt-url-input");
const btnYtSubmit = document.getElementById("btn-yt-submit");
const btnYtPaste = document.getElementById("btn-yt-paste");
const ytVideoQuality = document.getElementById("yt-video-quality");
const ytAudioQuality = document.getElementById("yt-audio-quality");
const ytPreviewCard = document.getElementById("yt-preview-card");
const ytPreviewThumb = document.getElementById("yt-preview-thumb");
const ytPreviewTitle = document.getElementById("yt-preview-title");
const ytPreviewChannel = document.getElementById("yt-preview-channel");
const ytPreviewDuration = document.getElementById("yt-preview-duration");

// Progress UI Elements
const docTitleDisplay = document.getElementById("doc-title-display");
const docMetaBadge = document.getElementById("doc-meta-badge");
const progressBar = document.getElementById("progress-bar");
const progressPercentage = document.getElementById("progress-percentage");
const stageMessage = document.getElementById("stage-message");
const pageCounter = document.getElementById("page-counter");
const stepperProgressLine = document.getElementById("stepper-progress-line");
const step3Label = document.getElementById("step-3-label");

const logConsole = document.getElementById("log-console");
const toggleLogsBtn = document.getElementById("toggle-logs-btn");
const logBoxWrapper = document.getElementById("log-box-wrapper");

// Result UI Elements
const resTitle = document.getElementById("res-title");
const resSize = document.getElementById("res-size");
const resExtraLabel = document.getElementById("res-extra-label");
const resExtraVal = document.getElementById("res-extra-val");
const resDownloadBtn = document.getElementById("res-download-btn");
const resCountdown = document.getElementById("res-countdown");
const btnReset = document.getElementById("btn-reset");
const btnRetry = document.getElementById("btn-retry");
const errorText = document.getElementById("error-text");

// ==================== TAB NAVIGATION ====================

function switchTab(tab) {
  currentMode = tab;
  resetUI();
  progressSection.classList.add("hidden");
  resultSection.classList.add("hidden");
  errorSection.classList.add("hidden");

  if (tab === "scribd") {
    tabScribd.classList.add("active");
    tabScribd.classList.remove("text-slate-400");
    tabYouTube.classList.remove("active");
    tabYouTube.classList.add("text-slate-400");

    viewScribd.classList.remove("hidden");
    viewYouTube.classList.add("hidden");
    step3Label.innerText = "Gỡ Mờ & Render";
    scribdUrlInput.focus();
  } else {
    tabYouTube.classList.add("active");
    tabYouTube.classList.remove("text-slate-400");
    tabScribd.classList.remove("active");
    tabScribd.classList.add("text-slate-400");

    viewYouTube.classList.remove("hidden");
    viewScribd.classList.add("hidden");
    step3Label.innerText = "Tải Luồng Stream";
    ytUrlInput.focus();
  }
}

if (tabScribd) tabScribd.addEventListener("click", () => switchTab("scribd"));
if (tabYouTube) tabYouTube.addEventListener("click", () => switchTab("youtube"));

// ==================== CLIPBOARD PASTE HELPERS ====================

if (btnScribdPaste) {
  btnScribdPaste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        scribdUrlInput.value = text.trim();
        scribdUrlInput.focus();
      }
    } catch (err) {
      console.warn("Clipboard access denied", err);
    }
  });
}

if (btnYtPaste) {
  btnYtPaste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        ytUrlInput.value = text.trim();
        ytUrlInput.focus();
        fetchYouTubePreview(text.trim());
      }
    } catch (err) {
      console.warn("Clipboard access denied", err);
    }
  });
}

// Auto-inspect YouTube Video info on URL change
let ytInspectTimeout = null;
if (ytUrlInput) {
  ytUrlInput.addEventListener("input", (e) => {
    clearTimeout(ytInspectTimeout);
    const val = e.target.value.trim();
    if (val.includes("youtube.com") || val.includes("youtu.be")) {
      ytInspectTimeout = setTimeout(() => {
        fetchYouTubePreview(val);
      }, 500);
    } else {
      ytPreviewCard.classList.add("hidden");
    }
  });
}

async function fetchYouTubePreview(url) {
  try {
    const res = await fetch("/api/youtube/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    if (res.ok) {
      const respData = await res.json();
      const data = respData.data;
      if (data) {
        ytPreviewTitle.innerText = data.title || "Video YouTube";
        ytPreviewChannel.innerText = data.uploader || "";
        ytPreviewDuration.innerText = data.duration || "";
        if (data.thumbnail) {
          ytPreviewThumb.src = data.thumbnail;
        }
        ytPreviewCard.classList.remove("hidden");
      }
    }
  } catch (err) {
    console.debug("Preview fetch error", err);
  }
}

// ==================== FORM SUBMISSION ====================

// Scribd Submit
if (scribdForm) {
  scribdForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = scribdUrlInput.value.trim();
    const pages = scribdPagesInput.value.trim() || "all";

    if (!url) {
      alert("Vui lòng nhập đường dẫn tài liệu Scribd!");
      return;
    }

    resetUI();
    setSubmitting(btnScribdSubmit, true, "Đang kết nối Scribd...");
    showProgressView();

    try {
      const response = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, pages })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Không thể khởi tạo tác vụ tải Scribd.");
      }

      currentTaskId = data.task_id;
      startTrackingProgress(currentTaskId);
    } catch (err) {
      showErrorView(err.message);
    } finally {
      setSubmitting(btnScribdSubmit, false, "Bắt Đầu Tải File PDF");
    }
  });
}

// YouTube Submit
if (ytForm) {
  ytForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = ytUrlInput.value.trim();
    const formatType = document.querySelector('input[name="yt-format-type"]:checked')?.value || "video";
    const quality = formatType === "video" ? ytVideoQuality.value : ytAudioQuality.value;

    if (!url) {
      alert("Vui lòng nhập URL video YouTube!");
      return;
    }

    resetUI();
    setSubmitting(btnYtSubmit, true, "Đang phân tích YouTube...");
    showProgressView();

    try {
      const response = await fetch("/api/youtube/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, format_type: formatType, quality })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Không thể khởi tạo tác vụ tải YouTube.");
      }

      currentTaskId = data.task_id;
      startTrackingProgress(currentTaskId);
    } catch (err) {
      showErrorView(err.message);
    } finally {
      setSubmitting(btnYtSubmit, false, "Bắt Đầu Tải Video / Audio");
    }
  });
}

function setSubmitting(button, isSubmitting, label) {
  if (button) {
    button.disabled = isSubmitting;
    button.innerHTML = isSubmitting
      ? `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> <span>${label}</span>`
      : `<span>${label}</span>`;
  }
}

// ==================== VIEW SWITCHING ====================

function showProgressView() {
  progressSection.classList.remove("hidden");
  resultSection.classList.add("hidden");
  errorSection.classList.add("hidden");
  progressSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showResultView(taskData) {
  progressSection.classList.add("hidden");
  resultSection.classList.remove("hidden");
  errorSection.classList.add("hidden");

  resTitle.innerText = taskData.title || "Tệp tin hoàn tất";
  resSize.innerText = `${taskData.file_size_mb || taskData.pdf_size_mb || 0} MB`;
  
  if (taskData.type === "youtube") {
    resExtraLabel.innerText = "Định dạng:";
    resExtraVal.innerText = taskData.format_type === "audio" ? `Audio MP3 (${taskData.quality})` : `Video MP4 (${taskData.quality})`;
  } else {
    resExtraLabel.innerText = "Số trang:";
    resExtraVal.innerText = `${taskData.total_pages || 0} trang`;
  }

  resDownloadBtn.href = taskData.download_url || `/api/file/${taskData.task_id}`;
  resDownloadBtn.setAttribute("download", taskData.filename || "downloaded_media");

  startCountdown(taskData.expires_in_seconds || 1800);
  resultSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showErrorView(message) {
  progressSection.classList.add("hidden");
  resultSection.classList.add("hidden");
  errorSection.classList.remove("hidden");
  errorText.innerText = message || "Đã xảy ra lỗi không xác định.";
  errorSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function resetUI() {
  stopTracking();
  if (countdownTimerInterval) clearInterval(countdownTimerInterval);
  
  progressBar.style.width = "0%";
  progressPercentage.innerText = "0%";
  stageMessage.innerText = "Đang kết nối...";
  pageCounter.innerText = "";
  logConsole.innerHTML = "";
  updateStepper(1);
}

// Reset button
if (btnReset) {
  btnReset.addEventListener("click", () => {
    resetUI();
    progressSection.classList.add("hidden");
    resultSection.classList.add("hidden");
    errorSection.classList.add("hidden");
    if (currentMode === "scribd") {
      scribdUrlInput.value = "";
      scribdUrlInput.focus();
    } else {
      ytUrlInput.value = "";
      ytPreviewCard.classList.add("hidden");
      ytUrlInput.focus();
    }
  });
}

// Retry button
if (btnRetry) {
  btnRetry.addEventListener("click", () => {
    errorSection.classList.add("hidden");
    if (currentMode === "scribd") {
      scribdForm.dispatchEvent(new Event("submit"));
    } else {
      ytForm.dispatchEvent(new Event("submit"));
    }
  });
}

// Toggle Logs
if (toggleLogsBtn && logBoxWrapper) {
  toggleLogsBtn.addEventListener("click", () => {
    logBoxWrapper.classList.toggle("hidden");
    const isHidden = logBoxWrapper.classList.contains("hidden");
    toggleLogsBtn.innerText = isHidden ? "Xem nhật ký chi tiết" : "Ẩn nhật ký chi tiết";
  });
}

// ==================== REAL-TIME PROGRESS TRACKING ====================

function startTrackingProgress(taskId) {
  stopTracking();

  const streamUrl = `/api/stream/${taskId}`;
  activeEventSource = new EventSource(streamUrl);

  activeEventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleProgressUpdate(data);
    } catch (err) {
      console.warn("SSE parse error", err);
    }
  };

  activeEventSource.onerror = (err) => {
    console.warn("SSE error, falling back to polling...", err);
    if (activeEventSource) {
      activeEventSource.close();
      activeEventSource = null;
    }
    startFallbackPolling(taskId);
  };
}

function startFallbackPolling(taskId) {
  if (activePollingInterval) clearInterval(activePollingInterval);
  activePollingInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${taskId}`);
      if (res.ok) {
        const data = await res.json();
        handleProgressUpdate(data);
        if (data.status === "completed" || data.status === "failed") {
          stopTracking();
        }
      }
    } catch (err) {
      console.error("Polling error", err);
    }
  }, 1000);
}

function stopTracking() {
  if (activeEventSource) {
    activeEventSource.close();
    activeEventSource = null;
  }
  if (activePollingInterval) {
    clearInterval(activePollingInterval);
    activePollingInterval = null;
  }
}

function handleProgressUpdate(data) {
  if (data.title && !data.title.includes("Đang khởi tạo") && !data.title.includes("Tài liệu Scribd")) {
    docTitleDisplay.innerText = data.title;
  }

  if (data.type === "youtube") {
    docMetaBadge.innerText = data.format_type === "audio" ? `MP3 (${data.quality})` : `MP4 (${data.quality})`;
    docMetaBadge.classList.remove("hidden");
    if (data.speed || data.eta) {
      pageCounter.innerText = `${data.speed} ${data.eta ? '• ' + data.eta : ''}`;
    }
  } else {
    if (data.doc_id) {
      docMetaBadge.innerText = `ID: ${data.doc_id}`;
      docMetaBadge.classList.remove("hidden");
    }
    if (data.total_pages > 0) {
      pageCounter.innerText = `Trang: ${data.current_page || 0} / ${data.total_pages}`;
    }
  }

  // Update Progress Bar
  const pct = Math.max(0, Math.min(100, data.percentage || 0));
  progressBar.style.width = `${pct}%`;
  progressPercentage.innerText = `${pct}%`;
  stageMessage.innerText = data.stage_message || "Đang xử lý...";

  // Stepper
  mapStatusToStep(data.status, pct);

  // Logs
  if (data.logs && Array.isArray(data.logs)) {
    renderLogs(data.logs);
  }

  // Check Terminal Status
  if (data.status === "completed") {
    stopTracking();
    setTimeout(() => {
      showResultView(data);
    }, 600);
  } else if (data.status === "failed") {
    stopTracking();
    setTimeout(() => {
      showErrorView(data.error_message || "Quá trình tải thất bại.");
    }, 500);
  }
}

function mapStatusToStep(status, pct) {
  if (status === "connecting" || pct <= 15) {
    updateStepper(1);
  } else if (status === "extracting" || (pct > 15 && pct <= 25)) {
    updateStepper(2);
  } else if (status === "rendering" || status === "downloading" || (pct > 25 && pct <= 85)) {
    updateStepper(3);
  } else if (status === "compiling" || (pct > 85 && pct < 100)) {
    updateStepper(4);
  } else if (status === "completed" || pct === 100) {
    updateStepper(5);
  }
}

function updateStepper(activeStep) {
  const nodes = document.querySelectorAll(".step-node");
  nodes.forEach((node) => {
    const step = parseInt(node.getAttribute("data-step"), 10);
    node.classList.remove("active", "completed");
    if (step < activeStep) {
      node.classList.add("completed");
    } else if (step === activeStep) {
      node.classList.add("active");
    }
  });

  if (stepperProgressLine) {
    const percent = Math.min(100, ((activeStep - 1) / 4) * 100);
    stepperProgressLine.style.width = `${percent}%`;
  }
}

function renderLogs(logs) {
  logConsole.innerHTML = "";
  logs.forEach((log) => {
    const line = document.createElement("div");
    line.className = "flex items-start gap-2 leading-relaxed";

    let colorClass = "text-slate-300";
    if (log.level === "error") colorClass = "text-red-400 font-semibold";
    else if (log.level === "warning") colorClass = "text-amber-400";
    else if (log.level === "success") colorClass = "text-emerald-400";

    line.innerHTML = `
      <span class="text-slate-600 select-none">[${log.time || '--:--:--'}]</span>
      <span class="${colorClass}">${escapeHtml(log.message || '')}</span>
    `;
    logConsole.appendChild(line);
  });

  if (logBoxWrapper) {
    logBoxWrapper.scrollTop = logBoxWrapper.scrollHeight;
  }
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function startCountdown(seconds) {
  let remaining = seconds;
  if (countdownTimerInterval) clearInterval(countdownTimerInterval);

  function update() {
    if (remaining <= 0) {
      clearInterval(countdownTimerInterval);
      resCountdown.innerText = "00:00 (Đã hết hạn)";
      resDownloadBtn.classList.add("opacity-50", "pointer-events-none");
      return;
    }
    const mins = Math.floor(remaining / 60);
    const secs = remaining % 60;
    resCountdown.innerText = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    remaining--;
  }

  update();
  countdownTimerInterval = setInterval(update, 1000);
}
