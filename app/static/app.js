// Main Frontend Application Logic
let activeEventSource = null;
let activePollingInterval = null;
let countdownTimerInterval = null;
let currentTaskId = null;
let currentMode = "scribd"; // "scribd", "youtube", "facebook", or "direct"

// Navigation Tabs (Desktop & Mobile)
const tabScribd = document.getElementById("tab-scribd");
const tabYouTube = document.getElementById("tab-youtube");
const tabFacebook = document.getElementById("tab-facebook");
const tabDirect = document.getElementById("tab-direct");

const tabScribdM = document.getElementById("tab-scribd-m");
const tabYouTubeM = document.getElementById("tab-youtube-m");
const tabFacebookM = document.getElementById("tab-facebook-m");
const tabDirectM = document.getElementById("tab-direct-m");

const viewScribd = document.getElementById("view-scribd");
const viewYouTube = document.getElementById("view-youtube");
const viewFacebook = document.getElementById("view-facebook");
const viewDirect = document.getElementById("view-direct");

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

// Facebook Elements
const fbForm = document.getElementById("fb-form");
const fbUrlInput = document.getElementById("fb-url-input");
const btnFbSubmit = document.getElementById("btn-fb-submit");
const btnFbPaste = document.getElementById("btn-fb-paste");
const fbVideoQuality = document.getElementById("fb-video-quality");
const fbAudioQuality = document.getElementById("fb-audio-quality");
const fbPreviewCard = document.getElementById("fb-preview-card");
const fbPreviewThumb = document.getElementById("fb-preview-thumb");
const fbPreviewTitle = document.getElementById("fb-preview-title");
const fbPreviewChannel = document.getElementById("fb-preview-channel");
const fbPreviewDuration = document.getElementById("fb-preview-duration");

// Direct Remote URL Elements
const directForm = document.getElementById("direct-form");
const directUrlInput = document.getElementById("direct-url-input");
const directCustomName = document.getElementById("direct-custom-name");
const btnDirectSubmit = document.getElementById("btn-direct-submit");
const btnDirectPaste = document.getElementById("btn-direct-paste");
const directPreviewCard = document.getElementById("direct-preview-card");
const directPreviewFilename = document.getElementById("direct-preview-filename");
const directPreviewSize = document.getElementById("direct-preview-size");
const directPreviewType = document.getElementById("direct-preview-type");

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
const btnCopyLink = document.getElementById("btn-copy-link");
const copyLinkText = document.getElementById("copy-link-text");
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

  // Reset tab button styles (Desktop & Mobile)
  [tabScribd, tabYouTube, tabFacebook, tabDirect, tabScribdM, tabYouTubeM, tabFacebookM, tabDirectM].forEach(btn => {
    if (btn) {
      btn.classList.remove("active");
      btn.classList.add("text-slate-400");
    }
  });

  // Hide all views
  viewScribd.classList.add("hidden");
  viewYouTube.classList.add("hidden");
  if (viewFacebook) viewFacebook.classList.add("hidden");
  if (viewDirect) viewDirect.classList.add("hidden");

  if (tab === "scribd") {
    if (tabScribd) { tabScribd.classList.add("active"); tabScribd.classList.remove("text-slate-400"); }
    if (tabScribdM) { tabScribdM.classList.add("active"); tabScribdM.classList.remove("text-slate-400"); }
    viewScribd.classList.remove("hidden");
    step3Label.innerText = "Gỡ Mờ & Render";
    scribdUrlInput.focus();
  } else if (tab === "youtube") {
    if (tabYouTube) { tabYouTube.classList.add("active"); tabYouTube.classList.remove("text-slate-400"); }
    if (tabYouTubeM) { tabYouTubeM.classList.add("active"); tabYouTubeM.classList.remove("text-slate-400"); }
    viewYouTube.classList.remove("hidden");
    step3Label.innerText = "Tải Luồng Stream";
    ytUrlInput.focus();
  } else if (tab === "facebook") {
    if (tabFacebook) { tabFacebook.classList.add("active"); tabFacebook.classList.remove("text-slate-400"); }
    if (tabFacebookM) { tabFacebookM.classList.add("active"); tabFacebookM.classList.remove("text-slate-400"); }
    if (viewFacebook) viewFacebook.classList.remove("hidden");
    step3Label.innerText = "Tải Luồng Stream";
    fbUrlInput.focus();
  } else if (tab === "direct") {
    if (tabDirect) { tabDirect.classList.add("active"); tabDirect.classList.remove("text-slate-400"); }
    if (tabDirectM) { tabDirectM.classList.add("active"); tabDirectM.classList.remove("text-slate-400"); }
    if (viewDirect) viewDirect.classList.remove("hidden");
    step3Label.innerText = "Tải Stream Tệp";
    directUrlInput.focus();
  }
}

if (tabScribd) tabScribd.addEventListener("click", () => switchTab("scribd"));
if (tabYouTube) tabYouTube.addEventListener("click", () => switchTab("youtube"));
if (tabFacebook) tabFacebook.addEventListener("click", () => switchTab("facebook"));
if (tabDirect) tabDirect.addEventListener("click", () => switchTab("direct"));

if (tabScribdM) tabScribdM.addEventListener("click", () => switchTab("scribd"));
if (tabYouTubeM) tabYouTubeM.addEventListener("click", () => switchTab("youtube"));
if (tabFacebookM) tabFacebookM.addEventListener("click", () => switchTab("facebook"));
if (tabDirectM) tabDirectM.addEventListener("click", () => switchTab("direct"));


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

if (btnFbPaste) {
  btnFbPaste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        fbUrlInput.value = text.trim();
        fbUrlInput.focus();
        fetchFacebookPreview(text.trim());
      }
    } catch (err) {
      console.warn("Clipboard access denied", err);
    }
  });
}

if (btnDirectPaste) {
  btnDirectPaste.addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        directUrlInput.value = text.trim();
        directUrlInput.focus();
        fetchDirectPreview(text.trim());
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

// Auto-inspect Facebook Video info on URL change
let fbInspectTimeout = null;
if (fbUrlInput) {
  fbUrlInput.addEventListener("input", (e) => {
    clearTimeout(fbInspectTimeout);
    const val = e.target.value.trim();
    if (val.includes("facebook.com") || val.includes("fb.watch")) {
      fbInspectTimeout = setTimeout(() => {
        fetchFacebookPreview(val);
      }, 500);
    } else {
      fbPreviewCard.classList.add("hidden");
    }
  });
}

// Auto-inspect Direct Remote URL info on URL change
let directInspectTimeout = null;
if (directUrlInput) {
  directUrlInput.addEventListener("input", (e) => {
    clearTimeout(directInspectTimeout);
    const val = e.target.value.trim();
    if (val.startsWith("http://") || val.startsWith("https://")) {
      directInspectTimeout = setTimeout(() => {
        fetchDirectPreview(val);
      }, 600);
    } else {
      directPreviewCard.classList.add("hidden");
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

        if (data.video_qualities && Array.isArray(data.video_qualities) && ytVideoQuality) {
          ytVideoQuality.innerHTML = "";
          data.video_qualities.forEach((q) => {
            const opt = document.createElement("option");
            opt.value = q.id;
            opt.innerText = q.label;
            ytVideoQuality.appendChild(opt);
          });
        }

        if (data.audio_qualities && Array.isArray(data.audio_qualities) && ytAudioQuality) {
          ytAudioQuality.innerHTML = "";
          data.audio_qualities.forEach((q) => {
            const opt = document.createElement("option");
            opt.value = q.id;
            opt.innerText = `${q.label} ${q.note ? '(' + q.note + ')' : ''}`;
            ytAudioQuality.appendChild(opt);
          });
        }
      }
    }
  } catch (err) {
    console.debug("YouTube Preview fetch error", err);
  }
}

async function fetchFacebookPreview(url) {
  try {
    const res = await fetch("/api/facebook/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    if (res.ok) {
      const respData = await res.json();
      const data = respData.data;
      if (data) {
        fbPreviewTitle.innerText = data.title || "Video Facebook";
        fbPreviewChannel.innerText = data.uploader || "Facebook User";
        fbPreviewDuration.innerText = data.duration || "";
        if (data.thumbnail) {
          fbPreviewThumb.src = data.thumbnail;
        }
        fbPreviewCard.classList.remove("hidden");

        if (data.video_qualities && Array.isArray(data.video_qualities) && fbVideoQuality) {
          fbVideoQuality.innerHTML = "";
          data.video_qualities.forEach((q) => {
            const opt = document.createElement("option");
            opt.value = q.id;
            opt.innerText = q.label;
            fbVideoQuality.appendChild(opt);
          });
        }

        if (data.audio_qualities && Array.isArray(data.audio_qualities) && fbAudioQuality) {
          fbAudioQuality.innerHTML = "";
          data.audio_qualities.forEach((q) => {
            const opt = document.createElement("option");
            opt.value = q.id;
            opt.innerText = `${q.label} ${q.note ? '(' + q.note + ')' : ''}`;
            fbAudioQuality.appendChild(opt);
          });
        }
      }
    }
  } catch (err) {
    console.debug("Facebook Preview fetch error", err);
  }
}

async function fetchDirectPreview(url) {
  try {
    const res = await fetch("/api/direct/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    if (res.ok) {
      const respData = await res.json();
      const data = respData.data;
      if (data) {
        directPreviewFilename.innerText = data.filename || "remote_file";
        directPreviewSize.innerText = data.file_size_str || "--";
        directPreviewType.innerText = data.content_type || "application/octet-stream";
        directPreviewCard.classList.remove("hidden");
      }
    }
  } catch (err) {
    console.debug("Direct Preview fetch error", err);
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

// Facebook Submit
if (fbForm) {
  fbForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = fbUrlInput.value.trim();
    const formatType = document.querySelector('input[name="fb-format-type"]:checked')?.value || "video";
    const quality = formatType === "video" ? fbVideoQuality.value : fbAudioQuality.value;

    if (!url) {
      alert("Vui lòng nhập URL video Facebook!");
      return;
    }

    resetUI();
    setSubmitting(btnFbSubmit, true, "Đang phân tích Facebook...");
    showProgressView();

    try {
      const response = await fetch("/api/facebook/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, format_type: formatType, quality })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Không thể khởi tạo tác vụ tải Facebook.");
      }

      currentTaskId = data.task_id;
      startTrackingProgress(currentTaskId);
    } catch (err) {
      showErrorView(err.message);
    } finally {
      setSubmitting(btnFbSubmit, false, "Bắt Đầu Tải Video Facebook");
    }
  });
}

// Direct Remote URL Submit
if (directForm) {
  directForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = directUrlInput.value.trim();
    const customFilename = directCustomName ? directCustomName.value.trim() : null;

    if (!url) {
      alert("Vui lòng nhập đường dẫn URL tệp tin!");
      return;
    }

    resetUI();
    setSubmitting(btnDirectSubmit, true, "Đang kết nối máy chủ tệp tin...");
    showProgressView();

    try {
      const response = await fetch("/api/direct/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, custom_filename: customFilename })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Không thể khởi tạo tác vụ tải tệp tin từ xa.");
      }

      currentTaskId = data.task_id;
      startTrackingProgress(currentTaskId);
    } catch (err) {
      showErrorView(err.message);
    } finally {
      setSubmitting(btnDirectSubmit, false, "Bắt Đầu Tải Tệp Về Máy Chủ");
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
  
  if (taskData.type === "youtube" || taskData.type === "facebook") {
    const srcName = taskData.type === "youtube" ? "YouTube" : "Facebook";
    resExtraLabel.innerText = "Định dạng:";
    resExtraVal.innerText = taskData.format_type === "audio" ? `${srcName} MP3 (${taskData.quality})` : `${srcName} MP4 (${taskData.quality.toUpperCase()})`;
  } else if (taskData.type === "direct") {
    resExtraLabel.innerText = "Tên tệp:";
    resExtraVal.innerText = taskData.filename || "file.bin";
  } else {
    resExtraLabel.innerText = "Số trang:";
    resExtraVal.innerText = `${taskData.total_pages || 0} trang`;
  }

  const downloadRelUrl = taskData.download_url || `/api/file/${taskData.task_id}`;
  resDownloadBtn.href = downloadRelUrl;
  resDownloadBtn.setAttribute("download", taskData.filename || "downloaded_media");

  // Setup Copy Direct Link Button
  const fullDownloadUrl = `${window.location.origin}${downloadRelUrl}`;
  if (btnCopyLink) {
    btnCopyLink.onclick = async () => {
      try {
        await navigator.clipboard.writeText(fullDownloadUrl);
        copyLinkText.innerText = "Đã sao chép link!";
        setTimeout(() => {
          copyLinkText.innerText = "Sao Chép Link Tải";
        }, 2500);
      } catch (err) {
        prompt("Sao chép link tải bên dưới:", fullDownloadUrl);
      }
    };
  }

  startCountdown(taskData.expires_in_seconds || 18000); // 5 hours default
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
    } else if (currentMode === "youtube") {
      ytUrlInput.value = "";
      ytPreviewCard.classList.add("hidden");
      ytUrlInput.focus();
    } else if (currentMode === "facebook") {
      fbUrlInput.value = "";
      fbPreviewCard.classList.add("hidden");
      fbUrlInput.focus();
    } else if (currentMode === "direct") {
      directUrlInput.value = "";
      directPreviewCard.classList.add("hidden");
      directUrlInput.focus();
    }
  });
}

// Retry button
if (btnRetry) {
  btnRetry.addEventListener("click", () => {
    errorSection.classList.add("hidden");
    if (currentMode === "scribd") {
      scribdForm.dispatchEvent(new Event("submit"));
    } else if (currentMode === "youtube") {
      ytForm.dispatchEvent(new Event("submit"));
    } else if (currentMode === "facebook") {
      fbForm.dispatchEvent(new Event("submit"));
    } else if (currentMode === "direct") {
      directForm.dispatchEvent(new Event("submit"));
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
  if (data.title && !data.title.includes("Đang khởi tạo") && !data.title.includes("Tài liệu Scribd") && !data.title.includes("Đang phân tích")) {
    docTitleDisplay.innerText = data.title;
  }

  if (data.type === "youtube" || data.type === "facebook") {
    const srcName = data.type === "youtube" ? "YouTube" : "Facebook";
    docMetaBadge.innerText = data.format_type === "audio" ? `${srcName} MP3 (${data.quality})` : `${srcName} MP4 (${data.quality.toUpperCase()})`;
    docMetaBadge.classList.remove("hidden");
    if (data.speed || data.eta) {
      pageCounter.innerText = `${data.speed} ${data.eta ? '• ' + data.eta : ''}`;
    }
  } else if (data.type === "direct") {
    docMetaBadge.innerText = data.filename || `Remote URL File`;
    docMetaBadge.classList.remove("hidden");
    if (data.total_bytes > 0) {
      const curMb = (data.downloaded_bytes / (1024 * 1024)).toFixed(2);
      const totMb = (data.total_bytes / (1024 * 1024)).toFixed(2);
      pageCounter.innerText = `${curMb} MB / ${totMb} MB ${data.speed ? '• ' + data.speed : ''} ${data.eta ? '• ' + data.eta : ''}`;
    } else if (data.downloaded_bytes > 0) {
      const curMb = (data.downloaded_bytes / (1024 * 1024)).toFixed(2);
      pageCounter.innerText = `${curMb} MB ${data.speed ? '• ' + data.speed : ''}`;
    } else if (data.speed || data.eta) {
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

    const msg = log.message || '';
    let colorClass = "text-slate-300";
    let prefixTag = "";

    if (log.level === "error") {
      colorClass = "text-red-400 font-semibold";
    } else if (log.level === "warning") {
      colorClass = "text-amber-400";
    } else if (log.level === "success" || msg.includes("Hoàn tất") || msg.includes("hoàn thành")) {
      colorClass = "text-emerald-400 font-medium";
    } else if (msg.includes("FFmpeg") || msg.includes("🎬") || msg.includes("⚙️") || msg.includes("⏳")) {
      colorClass = "text-purple-300 font-medium";
      prefixTag = `<span class="px-1.5 py-0.2 rounded bg-purple-900/60 text-purple-300 text-[10px] font-mono border border-purple-700/50 mr-1">FFmpeg</span>`;
    }

    line.innerHTML = `
      <span class="text-slate-600 select-none flex-shrink-0">[${log.time || '--:--:--'}]</span>
      <span class="${colorClass}">${prefixTag}${escapeHtml(msg)}</span>
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
      resCountdown.innerText = "00:00:00 (Đã hết hạn)";
      resDownloadBtn.classList.add("opacity-50", "pointer-events-none");
      return;
    }
    const hours = Math.floor(remaining / 3600);
    const mins = Math.floor((remaining % 3600) / 60);
    const secs = remaining % 60;
    resCountdown.innerText = `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    remaining--;
  }

  update();
  countdownTimerInterval = setInterval(update, 1000);
}
