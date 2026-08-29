// Main Frontend Application Logic
let activeEventSource = null;
let activePollingInterval = null;
let countdownTimerInterval = null;
let currentTaskId = null;

// DOM Elements
const form = document.getElementById("download-form");
const urlInput = document.getElementById("url-input");
const pagesInput = document.getElementById("pages-input");
const btnSubmit = document.getElementById("btn-submit");
const btnPaste = document.getElementById("btn-paste");
const btnClear = document.getElementById("btn-clear");

const inputSection = document.getElementById("input-section");
const progressSection = document.getElementById("progress-section");
const resultSection = document.getElementById("result-section");
const errorSection = document.getElementById("error-section");

const docTitleDisplay = document.getElementById("doc-title-display");
const docMetaBadge = document.getElementById("doc-meta-badge");
const progressBar = document.getElementById("progress-bar");
const progressPercentage = document.getElementById("progress-percentage");
const stageMessage = document.getElementById("stage-message");
const pageCounter = document.getElementById("page-counter");

const logConsole = document.getElementById("log-console");
const toggleLogsBtn = document.getElementById("toggle-logs-btn");
const logBoxWrapper = document.getElementById("log-box-wrapper");

const resTitle = document.getElementById("res-title");
const resPages = document.getElementById("res-pages");
const resSize = document.getElementById("res-size");
const resDownloadBtn = document.getElementById("res-download-btn");
const resCountdown = document.getElementById("res-countdown");
const btnReset = document.getElementById("btn-reset");
const btnRetry = document.getElementById("btn-retry");
const errorText = document.getElementById("error-text");

// Paste from Clipboard
if (btnPaste) {
  btnPaste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        urlInput.focus();
      }
    } catch (err) {
      console.warn("Could not access clipboard", err);
    }
  });
}

// Clear Input
if (btnClear) {
  btnClear.addEventListener("click", () => {
    urlInput.value = "";
    urlInput.focus();
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

// Form Submit Handler
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = urlInput.value.trim();
  const pages = pagesInput ? pagesInput.value.trim() : "all";

  if (!url) {
    alert("Vui lòng nhập đường dẫn URL tài liệu Scribd!");
    urlInput.focus();
    return;
  }

  // Reset states
  resetUI();
  setSubmitting(true);

  try {
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, pages: pages || "all" })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Không thể khởi tạo tác vụ tải tài liệu.");
    }

    currentTaskId = data.task_id;
    showProgressView();
    startTrackingProgress(currentTaskId);
  } catch (err) {
    showErrorView(err.message);
  } finally {
    setSubmitting(false);
  }
});

function setSubmitting(isSubmitting) {
  if (btnSubmit) {
    btnSubmit.disabled = isSubmitting;
    btnSubmit.innerHTML = isSubmitting
      ? `<svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Đang khởi tạo...`
      : `<span class="flex items-center justify-center gap-2"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg> Bắt Đầu Tải PDF</span>`;
  }
}

function showProgressView() {
  progressSection.classList.remove("hidden");
  resultSection.classList.add("hidden");
  errorSection.classList.add("hidden");
  // Scroll to progress
  progressSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function showResultView(taskData) {
  progressSection.classList.add("hidden");
  resultSection.classList.remove("hidden");
  errorSection.classList.add("hidden");

  resTitle.innerText = taskData.title || "Tài liệu Scribd";
  resPages.innerText = `${taskData.total_pages || 0} trang`;
  resSize.innerText = `${taskData.pdf_size_mb || 0} MB`;
  resDownloadBtn.href = taskData.download_url || `/api/file/${taskData.task_id}`;
  resDownloadBtn.setAttribute("download", taskData.filename || "document.pdf");

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

// Reset & Download Another
if (btnReset) {
  btnReset.addEventListener("click", () => {
    resetUI();
    progressSection.classList.add("hidden");
    resultSection.classList.add("hidden");
    errorSection.classList.add("hidden");
    urlInput.value = "";
    urlInput.focus();
    inputSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
}

if (btnRetry) {
  btnRetry.addEventListener("click", () => {
    errorSection.classList.add("hidden");
    form.dispatchEvent(new Event("submit"));
  });
}

// Real-Time Progress Tracking via Server-Sent Events
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
  // Update Title & Badges
  if (data.title && data.title !== "Tài liệu Scribd") {
    docTitleDisplay.innerText = data.title;
  }
  if (data.doc_id) {
    docMetaBadge.innerText = `ID: ${data.doc_id}`;
    docMetaBadge.classList.remove("hidden");
  }

  // Update Progress Bar
  const pct = Math.max(0, Math.min(100, data.percentage || 0));
  progressBar.style.width = `${pct}%`;
  progressPercentage.innerText = `${pct}%`;
  stageMessage.innerText = data.stage_message || "Đang xử lý...";

  if (data.total_pages > 0) {
    pageCounter.innerText = `Trang: ${data.current_page || 0} / ${data.total_pages}`;
  }

  // Update Stepper
  mapStatusToStep(data.status, pct);

  // Update Logs
  if (data.logs && Array.isArray(data.logs)) {
    renderLogs(data.logs);
  }

  // Check Terminal Status
  if (data.status === "completed") {
    stopTracking();
    setTimeout(() => {
      showResultView(data);
    }, 800);
  } else if (data.status === "failed") {
    stopTracking();
    setTimeout(() => {
      showErrorView(data.error_message || "Quá trình tải thất bại.");
    }, 500);
  }
}

function mapStatusToStep(status, pct) {
  let step = 1;
  if (status === "connecting") {
    step = pct > 10 ? 2 : 1;
  } else if (status === "extracting") {
    step = 2;
  } else if (status === "rendering") {
    step = 3;
  } else if (status === "compiling") {
    step = 4;
  } else if (status === "completed") {
    step = 5;
  }
  updateStepper(step);
}

function updateStepper(activeStep) {
  for (let i = 1; i <= 5; i++) {
    const stepEl = document.getElementById(`step-${i}`);
    if (!stepEl) continue;

    stepEl.classList.remove("active", "completed", "pending");
    const iconEl = stepEl.querySelector(".step-icon");

    if (i < activeStep) {
      stepEl.classList.add("completed");
      if (iconEl) iconEl.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
    } else if (i === activeStep) {
      stepEl.classList.add("active");
      if (iconEl) iconEl.innerHTML = `<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-30"></span><span>${i}</span>`;
    } else {
      stepEl.classList.add("pending");
      if (iconEl) iconEl.innerHTML = `<span>${i}</span>`;
    }
  }
}

function renderLogs(logs) {
  if (!logConsole) return;
  const isScrolledToBottom = logConsole.scrollHeight - logConsole.clientHeight <= logConsole.scrollTop + 50;

  logConsole.innerHTML = logs.map(log => {
    let colorClass = "text-slate-300";
    if (log.level === "error") colorClass = "text-red-400 font-semibold";
    if (log.level === "warning") colorClass = "text-amber-400";
    if (log.level === "success") colorClass = "text-emerald-400 font-semibold";

    return `<div class="py-0.5 leading-relaxed"><span class="text-slate-500 mr-2">[${log.time}]</span><span class="${colorClass}">${escapeHtml(log.message)}</span></div>`;
  }).join("");

  if (isScrolledToBottom) {
    logConsole.scrollTop = logConsole.scrollHeight;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.innerText = text;
  return div.innerHTML;
}

// Live Countdown Timer
function startCountdown(seconds) {
  if (countdownTimerInterval) clearInterval(countdownTimerInterval);
  let remaining = seconds;

  function updateTimerText() {
    if (remaining <= 0) {
      clearInterval(countdownTimerInterval);
      resCountdown.innerText = "File đã hết hạn và được dọn dẹp.";
      resDownloadBtn.classList.add("opacity-50", "pointer-events-none");
      return;
    }
    const mins = Math.floor(remaining / 60);
    const secs = remaining % 60;
    const formatted = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    resCountdown.innerText = `File sẽ tự động xóa sau: ${formatted}`;
    remaining--;
  }

  updateTimerText();
  countdownTimerInterval = setInterval(updateTimerText, 1000);
}

