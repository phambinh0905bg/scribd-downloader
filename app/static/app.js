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
const tabFiles = document.getElementById("tab-files");
const tabTools = document.getElementById("tab-tools");

const tabScribdM = document.getElementById("tab-scribd-m");
const tabYouTubeM = document.getElementById("tab-youtube-m");
const tabFacebookM = document.getElementById("tab-facebook-m");
const tabDirectM = document.getElementById("tab-direct-m");
const tabFilesM = document.getElementById("tab-files-m");
const tabToolsM = document.getElementById("tab-tools-m");

const viewScribd = document.getElementById("view-scribd");
const viewYouTube = document.getElementById("view-youtube");
const viewFacebook = document.getElementById("view-facebook");
const viewDirect = document.getElementById("view-direct");
const viewFiles = document.getElementById("view-files");
const viewTools = document.getElementById("view-tools");
const filesBadge = document.getElementById("files-badge");

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
  [tabScribd, tabYouTube, tabFacebook, tabDirect, tabFiles, tabTools, tabScribdM, tabYouTubeM, tabFacebookM, tabDirectM, tabFilesM, tabToolsM].forEach(btn => {
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
  if (viewFiles) viewFiles.classList.add("hidden");
  if (viewTools) viewTools.classList.add("hidden");

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
  } else if (tab === "files") {
    if (tabFiles) { tabFiles.classList.add("active"); tabFiles.classList.remove("text-slate-400"); }
    if (tabFilesM) { tabFilesM.classList.add("active"); tabFilesM.classList.remove("text-slate-400"); }
    if (viewFiles) viewFiles.classList.remove("hidden");
    loadFilesList();
  } else if (tab === "tools") {
    if (tabTools) { tabTools.classList.add("active"); tabTools.classList.remove("text-slate-400"); }
    if (tabToolsM) { tabToolsM.classList.add("active"); tabToolsM.classList.remove("text-slate-400"); }
    if (viewTools) viewTools.classList.remove("hidden");
    populateToolsLists();
  }
}

if (tabScribd) tabScribd.addEventListener("click", () => switchTab("scribd"));
if (tabYouTube) tabYouTube.addEventListener("click", () => switchTab("youtube"));
if (tabFacebook) tabFacebook.addEventListener("click", () => switchTab("facebook"));
if (tabDirect) tabDirect.addEventListener("click", () => switchTab("direct"));
if (tabFiles) tabFiles.addEventListener("click", () => switchTab("files"));
if (tabTools) tabTools.addEventListener("click", () => switchTab("tools"));

if (tabScribdM) tabScribdM.addEventListener("click", () => switchTab("scribd"));
if (tabYouTubeM) tabYouTubeM.addEventListener("click", () => switchTab("youtube"));
if (tabFacebookM) tabFacebookM.addEventListener("click", () => switchTab("facebook"));
if (tabDirectM) tabDirectM.addEventListener("click", () => switchTab("direct"));
if (tabFilesM) tabFilesM.addEventListener("click", () => switchTab("files"));
if (tabToolsM) tabToolsM.addEventListener("click", () => switchTab("tools"));


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

// OCR Checkbox Toggle
const scribdEnableOcr = document.getElementById("scribd-enable-ocr");
const scribdOcrOptions = document.getElementById("scribd-ocr-options");
const scribdOcrLang = document.getElementById("scribd-ocr-lang");

if (scribdEnableOcr && scribdOcrOptions) {
  scribdEnableOcr.addEventListener("change", () => {
    if (scribdEnableOcr.checked) {
      scribdOcrOptions.classList.remove("hidden");
    } else {
      scribdOcrOptions.classList.add("hidden");
    }
  });
}

// Scribd Submit
if (scribdForm) {
  scribdForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = scribdUrlInput.value.trim();
    const pages = scribdPagesInput.value.trim() || "all";
    const enableOcr = scribdEnableOcr ? scribdEnableOcr.checked : false;
    const ocrLang = scribdOcrLang ? scribdOcrLang.value : "vie+eng";

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
        body: JSON.stringify({ 
          url, 
          pages,
          enable_ocr: enableOcr,
          ocr_lang: ocrLang
        })
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

const btnCancelDownload = document.getElementById("btn-cancel-download");
const btnDeleteServer = document.getElementById("btn-delete-server");

// Cancel/Abort Download Button
if (btnCancelDownload) {
  btnCancelDownload.addEventListener("click", async () => {
    if (!confirm("Bạn có chắc chắn muốn hủy tải và dọn dẹp các tệp tạm thời không?")) return;
    if (currentTaskId) {
      try {
        await fetch(`/api/task/${currentTaskId}`, { method: "DELETE" });
      } catch (e) {
        console.warn("Cancel delete error", e);
      }
      currentTaskId = null;
    }
    resetUI();
    progressSection.classList.add("hidden");
    resultSection.classList.add("hidden");
    errorSection.classList.add("hidden");
  });
}

// Delete from Server Button
if (btnDeleteServer) {
  btnDeleteServer.addEventListener("click", async () => {
    if (!confirm("Xác nhận xóa tệp tin này ngay lập tức khỏi máy chủ lưu trữ?")) return;
    if (currentTaskId) {
      try {
        await fetch(`/api/task/${currentTaskId}`, { method: "DELETE" });
      } catch (e) {
        console.warn("Delete error", e);
      }
      currentTaskId = null;
    }
    resetUI();
    progressSection.classList.add("hidden");
    resultSection.classList.add("hidden");
    errorSection.classList.add("hidden");
  });
}

// Reset button
if (btnReset) {
  btnReset.addEventListener("click", () => {
    currentTaskId = null;
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

// Beacon auto-cleanup if user closes page during active download
window.addEventListener("pagehide", () => {
  if (currentTaskId && activeEventSource) {
    navigator.sendBeacon(`/api/task/${currentTaskId}/abort`);
  }
});


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


// ==================== MY FILES & HISTORY MANAGER ====================

let allFiles = [];
let activeFileFilter = "all";
let fileSearchQuery = "";

const filesListContainer = document.getElementById("files-list-container");
const filesEmptyState = document.getElementById("files-empty-state");
const btnRefreshFiles = document.getElementById("btn-refresh-files");
const filesSearchInput = document.getElementById("files-search-input");
const fileFilterBtns = document.querySelectorAll(".file-filter-btn");

// Preview Modal Elements
const previewModal = document.getElementById("preview-modal");
const modalTypeBadge = document.getElementById("modal-type-badge");
const modalFileTitle = document.getElementById("modal-file-title");
const modalDownloadBtn = document.getElementById("modal-download-btn");
const modalCloseBtn = document.getElementById("modal-close-btn");
const modalIframe = document.getElementById("modal-iframe");
const modalVideo = document.getElementById("modal-video");
const modalAudioBox = document.getElementById("modal-audio-box");
const modalAudio = document.getElementById("modal-audio");
const modalUnsupported = document.getElementById("modal-unsupported");
const modalUnsupportedDownload = document.getElementById("modal-unsupported-download");

// Bookmarklet Modal Elements
const bookmarkletModal = document.getElementById("bookmarklet-modal");
const btnOpenBookmarklet = document.getElementById("btn-open-bookmarklet");
const bookmarkletCloseBtn = document.getElementById("bookmarklet-close-btn");
const bookmarkletDraggableLink = document.getElementById("bookmarklet-draggable-link");

async function loadFilesList() {
  if (btnRefreshFiles) {
    const icon = btnRefreshFiles.querySelector("svg");
    if (icon) icon.classList.add("animate-spin");
  }

  try {
    const res = await fetch("/api/files");
    const data = await res.json();
    allFiles = data.files || [];
    if (filesBadge) filesBadge.innerText = data.total_count || 0;
    renderFilesList();
  } catch (err) {
    console.error("Lỗi tải danh sách tệp:", err);
  } finally {
    if (btnRefreshFiles) {
      const icon = btnRefreshFiles.querySelector("svg");
      if (icon) icon.classList.remove("animate-spin");
    }
  }
}

async function loadFilesBadgeOnly() {
  try {
    const res = await fetch("/api/files");
    const data = await res.json();
    if (filesBadge) filesBadge.innerText = data.total_count || 0;
  } catch (_) {}
}

function renderFilesList() {
  if (!filesListContainer) return;

  // Filter by category
  let filtered = allFiles.filter(f => {
    if (activeFileFilter === "pdf") return f.file_type === "pdf";
    if (activeFileFilter === "video") return f.file_type === "video";
    if (activeFileFilter === "audio") return f.file_type === "audio";
    if (activeFileFilter === "pinned") return f.is_pinned === true;
    return true;
  });

  // Filter by search query
  if (fileSearchQuery) {
    const q = fileSearchQuery.toLowerCase();
    filtered = filtered.filter(f => f.filename.toLowerCase().includes(q));
  }

  if (filtered.length === 0) {
    filesListContainer.innerHTML = "";
    if (filesEmptyState) filesEmptyState.classList.remove("hidden");
    return;
  }

  if (filesEmptyState) filesEmptyState.classList.add("hidden");

  filesListContainer.innerHTML = filtered.map(f => {
    // Determine icon and colors
    let typeColor = "purple";
    let iconSvg = "";

    if (f.file_type === "pdf") {
      typeColor = "blue";
      iconSvg = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>`;
    } else if (f.file_type === "video") {
      typeColor = "red";
      iconSvg = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>`;
    } else if (f.file_type === "audio") {
      typeColor = "amber";
      iconSvg = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path>`;
    } else {
      typeColor = "emerald";
      iconSvg = `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"></path>`;
    }

    const pinBadge = f.is_pinned
      ? `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <svg class="w-3 h-3 text-amber-400" fill="currentColor" viewBox="0 0 20 20"><path d="M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"></path></svg>
          Đã ghim vĩnh viễn
        </span>`
      : `<span class="inline-flex items-center gap-1 text-[11px] text-slate-400">
          <svg class="w-3 h-3 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          Còn ${Math.floor(f.expires_in_minutes / 60)}h ${f.expires_in_minutes % 60}m
        </span>`;

    const pinButtonTitle = f.is_pinned ? "Bỏ ghim (khôi phục tự xóa sau 5h)" : "Ghim tệp này (không bao giờ tự xóa)";
    const pinButtonClass = f.is_pinned 
      ? "text-amber-400 bg-amber-500/10 border-amber-500/30 hover:bg-amber-500/20" 
      : "text-slate-400 bg-slate-800 border-slate-700 hover:text-amber-400 hover:bg-slate-700";

    return `
      <div class="glass-panel rounded-xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all hover:border-slate-700/90" data-task-id="${f.task_id}">
        <!-- File Info -->
        <div class="flex items-center gap-3.5 min-w-0 flex-1">
          <div class="w-11 h-11 rounded-xl bg-${typeColor}-500/10 border border-${typeColor}-500/20 text-${typeColor}-400 flex items-center justify-center flex-shrink-0">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              ${iconSvg}
            </svg>
          </div>
          <div class="min-w-0 flex-1 space-y-1">
            <div class="flex items-center gap-2">
              <h4 class="font-bold text-sm text-slate-200 truncate" title="${escapeHtml(f.filename)}">
                ${escapeHtml(f.filename)}
              </h4>
            </div>
            <div class="flex items-center gap-3 text-xs text-slate-400 flex-wrap font-mono">
              <span class="text-slate-300 font-semibold">${f.size_mb} MB</span>
              <span>•</span>
              <span class="text-slate-500">${f.created_at}</span>
              <span>•</span>
              ${pinBadge}
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex items-center gap-1.5 flex-shrink-0 self-end sm:self-center">
          <!-- Preview Button -->
          <button 
            type="button" 
            class="btn-file-preview px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600/80 hover:bg-indigo-600 text-white transition-all flex items-center gap-1 cursor-pointer"
            data-task-id="${f.task_id}"
            title="Xem trước trực tiếp"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
            </svg>
            <span>Xem</span>
          </button>

          <!-- Pin Button -->
          <button 
            type="button" 
            class="btn-file-pin p-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${pinButtonClass}"
            data-task-id="${f.task_id}"
            data-pinned="${f.is_pinned}"
            title="${pinButtonTitle}"
          >
            <svg class="w-4 h-4" fill="${f.is_pinned ? 'currentColor' : 'none'}" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
            </svg>
          </button>

          <!-- Send to Telegram Button -->
          <button 
            type="button" 
            class="btn-file-telegram p-1.5 rounded-lg text-xs font-semibold text-sky-400 bg-sky-950/40 hover:bg-sky-900/60 border border-sky-800/40 transition-all cursor-pointer"
            data-task-id="${f.task_id}"
            title="Gửi tệp này về Telegram"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .37z"/>
            </svg>
          </button>

          <!-- Download Button -->
          <a 
            href="${f.download_url}" 
            download="${escapeHtml(f.filename)}"
            class="p-1.5 rounded-lg text-xs font-semibold text-slate-300 bg-slate-800 hover:text-white hover:bg-slate-700 border border-slate-700 transition-all flex items-center justify-center cursor-pointer"
            title="Tải về máy"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
            </svg>
          </a>

          <!-- Copy Link Button -->
          <button 
            type="button" 
            class="btn-file-copy p-1.5 rounded-lg text-xs font-semibold text-slate-300 bg-slate-800 hover:text-white hover:bg-slate-700 border border-slate-700 transition-all cursor-pointer"
            data-url="${window.location.origin}${f.download_url}"
            title="Sao chép liên kết tải"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
            </svg>
          </button>

          <!-- Delete Button -->
          <button 
            type="button" 
            class="btn-file-delete p-1.5 rounded-lg text-xs font-semibold text-rose-400 bg-rose-950/30 hover:bg-rose-900/50 border border-rose-900/40 transition-all cursor-pointer"
            data-task-id="${f.task_id}"
            title="Xóa tệp khỏi máy chủ"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
            </svg>
          </button>
        </div>
      </div>
    `;
  }).join("");

  // Attach Event Listeners to rendered elements
  document.querySelectorAll(".btn-file-preview").forEach(btn => {
    btn.addEventListener("click", () => {
      const tid = btn.getAttribute("data-task-id");
      const file = allFiles.find(x => x.task_id === tid);
      if (file) openPreviewModal(file);
    });
  });

  document.querySelectorAll(".btn-file-pin").forEach(btn => {
    btn.addEventListener("click", async () => {
      const tid = btn.getAttribute("data-task-id");
      const isPinned = btn.getAttribute("data-pinned") === "true";
      const endpoint = isPinned ? `/api/files/unpin/${tid}` : `/api/files/pin/${tid}`;
      
      try {
        const res = await fetch(endpoint, { method: "POST" });
        const resData = await res.json();
        if (resData.status === "success") {
          const target = allFiles.find(x => x.task_id === tid);
          if (target) target.is_pinned = resData.is_pinned;
          renderFilesList();
        }
      } catch (err) {
        console.error("Lỗi ghim tệp:", err);
      }
    });
  });

  document.querySelectorAll(".btn-file-copy").forEach(btn => {
    btn.addEventListener("click", async () => {
      const url = btn.getAttribute("data-url");
      try {
        await navigator.clipboard.writeText(url);
        const originalHtml = btn.innerHTML;
        btn.innerHTML = `<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
        setTimeout(() => { btn.innerHTML = originalHtml; }, 2000);
      } catch (_) {}
    });
  });

  document.querySelectorAll(".btn-file-delete").forEach(btn => {
    btn.addEventListener("click", async () => {
      const tid = btn.getAttribute("data-task-id");
      if (!confirm("Bạn có chắc chắn muốn xóa vĩnh viễn tệp này khỏi máy chủ?")) return;
      
      try {
        const res = await fetch(`/api/task/${tid}/delete`, { method: "POST" });
        const resData = await res.json();
        if (resData.status === "success") {
          allFiles = allFiles.filter(x => x.task_id !== tid);
          if (filesBadge) filesBadge.innerText = allFiles.length;
          renderFilesList();
        }
      } catch (err) {
        console.error("Lỗi xóa tệp:", err);
      }
    });
  });
  document.querySelectorAll(".btn-file-telegram").forEach(btn => {
    btn.addEventListener("click", async () => {
      const tid = btn.getAttribute("data-task-id");
      const origHtml = btn.innerHTML;
      btn.innerHTML = `<svg class="w-4 h-4 animate-spin text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>`;
      btn.disabled = true;

      try {
        const res = await fetch(`/api/telegram/send/${tid}`, { method: "POST" });
        const data = await res.json();
        if (res.ok) {
          btn.innerHTML = `<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>`;
          setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2500);
        } else {
          alert("Lỗi gửi Telegram: " + (data.detail || "Chưa cấu hình Telegram Bot. Vui lòng bấm nút 'Telegram' ở góc trên để cài đặt!"));
          btn.innerHTML = origHtml;
          btn.disabled = false;
        }
      } catch (err) {
        alert("Lỗi kết nối máy chủ khi gửi Telegram.");
        btn.innerHTML = origHtml;
        btn.disabled = false;
      }
    });
  });
}

// Search and Filter Listeners
if (filesSearchInput) {
  filesSearchInput.addEventListener("input", (e) => {
    fileSearchQuery = e.target.value.trim();
    renderFilesList();
  });
}

fileFilterBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    fileFilterBtns.forEach(b => {
      b.classList.remove("active", "bg-purple-600", "text-white");
      b.classList.add("text-slate-400");
    });
    btn.classList.add("active", "bg-purple-600", "text-white");
    btn.classList.remove("text-slate-400");
    activeFileFilter = btn.getAttribute("data-filter");
    renderFilesList();
  });
});

if (btnRefreshFiles) {
  btnRefreshFiles.addEventListener("click", loadFilesList);
}


// ==================== PREVIEW MODAL LOGIC ====================

function openPreviewModal(file) {
  if (!previewModal) return;

  // Set file details
  if (modalFileTitle) modalFileTitle.innerText = file.filename;
  if (modalTypeBadge) modalTypeBadge.innerText = file.file_type.toUpperCase();
  if (modalDownloadBtn) {
    modalDownloadBtn.href = file.download_url;
    modalDownloadBtn.setAttribute("download", file.filename);
  }

  // Hide all players first
  if (modalIframe) { modalIframe.classList.add("hidden"); modalIframe.src = "about:blank"; }
  if (modalVideo) { modalVideo.classList.add("hidden"); modalVideo.pause(); modalVideo.src = ""; }
  if (modalAudioBox) { modalAudioBox.classList.add("hidden"); modalAudio.pause(); modalAudio.src = ""; }
  if (modalUnsupported) modalUnsupported.classList.add("hidden");

  // Show relevant viewer
  if (file.file_type === "pdf") {
    if (modalIframe) {
      modalIframe.src = file.preview_url;
      modalIframe.classList.remove("hidden");
    }
  } else if (file.file_type === "video") {
    if (modalVideo) {
      modalVideo.src = file.preview_url;
      modalVideo.classList.remove("hidden");
      modalVideo.play().catch(() => {});
    }
  } else if (file.file_type === "audio") {
    if (modalAudioBox) {
      modalAudio.src = file.preview_url;
      modalAudioBox.classList.remove("hidden");
      modalAudio.play().catch(() => {});
    }
  } else {
    if (modalUnsupported) {
      if (modalUnsupportedDownload) {
        modalUnsupportedDownload.href = file.download_url;
        modalUnsupportedDownload.setAttribute("download", file.filename);
      }
      modalUnsupported.classList.remove("hidden");
    }
  }

  previewModal.classList.remove("hidden");
}

function closePreviewModal() {
  if (!previewModal) return;
  if (modalVideo) { modalVideo.pause(); modalVideo.src = ""; }
  if (modalAudio) { modalAudio.pause(); modalAudio.src = ""; }
  if (modalIframe) { modalIframe.src = "about:blank"; }
  previewModal.classList.add("hidden");
}

if (modalCloseBtn) modalCloseBtn.addEventListener("click", closePreviewModal);
if (previewModal) {
  previewModal.addEventListener("click", (e) => {
    if (e.target === previewModal) closePreviewModal();
  });
}


// ==================== BOOKMARKLET MODAL & 1-CLICK ====================

function initBookmarklet() {
  const origin = window.location.origin;
  const scriptCode = `javascript:(function(){var u=encodeURIComponent(window.location.href);window.open('${origin}/?url='+u,'_blank');})();`;
  if (bookmarkletDraggableLink) {
    bookmarkletDraggableLink.href = scriptCode;
  }
}

if (btnOpenBookmarklet) {
  btnOpenBookmarklet.addEventListener("click", () => {
    initBookmarklet();
    if (bookmarkletModal) bookmarkletModal.classList.remove("hidden");
  });
}

if (bookmarkletCloseBtn) {
  bookmarkletCloseBtn.addEventListener("click", () => {
    if (bookmarkletModal) bookmarkletModal.classList.add("hidden");
  });
}

if (bookmarkletModal) {
  bookmarkletModal.addEventListener("click", (e) => {
    if (e.target === bookmarkletModal) bookmarkletModal.classList.add("hidden");
  });
}


// ==================== TELEGRAM BOT INTEGRATION ====================

const telegramModal = document.getElementById("telegram-modal");
const btnOpenTelegram = document.getElementById("btn-open-telegram");
const telegramCloseBtn = document.getElementById("telegram-close-btn");
const tgTokenInput = document.getElementById("tg-token-input");
const tgChatIdInput = document.getElementById("tg-chatid-input");
const tgAutoSendToggle = document.getElementById("tg-autosend-toggle");
const btnTestTelegram = document.getElementById("btn-test-telegram");
const btnSaveTelegram = document.getElementById("btn-save-telegram");
const tgStatusMsg = document.getElementById("tg-status-msg");

async function loadTelegramConfig() {
  try {
    const res = await fetch("/api/telegram/config");
    const data = await res.json();
    if (data.status === "success") {
      if (tgTokenInput) tgTokenInput.value = data.bot_token || "";
      if (tgChatIdInput) tgChatIdInput.value = data.chat_id || "";
      if (tgAutoSendToggle) tgAutoSendToggle.checked = Boolean(data.auto_send_enabled);
    }
  } catch (err) {
    console.error("Lỗi đọc cấu hình Telegram:", err);
  }
}

if (btnOpenTelegram) {
  btnOpenTelegram.addEventListener("click", () => {
    loadTelegramConfig();
    if (tgStatusMsg) tgStatusMsg.classList.add("hidden");
    if (telegramModal) telegramModal.classList.remove("hidden");
  });
}

if (telegramCloseBtn) {
  telegramCloseBtn.addEventListener("click", () => {
    if (telegramModal) telegramModal.classList.add("hidden");
  });
}

if (telegramModal) {
  telegramModal.addEventListener("click", (e) => {
    if (e.target === telegramModal) telegramModal.classList.add("hidden");
  });
}

if (btnTestTelegram) {
  btnTestTelegram.addEventListener("click", async () => {
    btnTestTelegram.innerText = "Đang gửi test...";
    btnTestTelegram.disabled = true;

    try {
      const res = await fetch("/api/telegram/test", { method: "POST" });
      const data = await res.json();
      if (tgStatusMsg) {
        tgStatusMsg.classList.remove("hidden");
        if (res.ok) {
          tgStatusMsg.innerHTML = `<span class="text-emerald-400 font-semibold">✅ ${data.message}</span>`;
        } else {
          tgStatusMsg.innerHTML = `<span class="text-rose-400 font-semibold">❌ Lỗi: ${data.detail || "Không thể kết nối Telegram"}</span>`;
        }
      }
    } catch (err) {
      if (tgStatusMsg) {
        tgStatusMsg.classList.remove("hidden");
        tgStatusMsg.innerHTML = `<span class="text-rose-400 font-semibold">❌ Lỗi kết nối tới máy chủ</span>`;
      }
    } finally {
      btnTestTelegram.innerText = "Thử Nghiệm Gửi Tin";
      btnTestTelegram.disabled = false;
    }
  });
}

if (btnSaveTelegram) {
  btnSaveTelegram.addEventListener("click", async () => {
    const bot_token = tgTokenInput.value.trim();
    const chat_id = tgChatIdInput.value.trim();
    const auto_send_enabled = tgAutoSendToggle.checked;

    btnSaveTelegram.innerText = "Đang lưu...";
    btnSaveTelegram.disabled = true;

    try {
      const res = await fetch("/api/telegram/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_token, chat_id, auto_send_enabled })
      });
      const data = await res.json();
      if (tgStatusMsg) {
        tgStatusMsg.classList.remove("hidden");
        if (res.ok) {
          tgStatusMsg.innerHTML = `<span class="text-emerald-400 font-semibold">✅ ${data.message}</span>`;
          setTimeout(() => {
            if (telegramModal) telegramModal.classList.add("hidden");
          }, 1500);
        } else {
          tgStatusMsg.innerHTML = `<span class="text-rose-400 font-semibold">❌ ${data.detail || "Lỗi lưu cấu hình"}</span>`;
        }
      }
    } catch (err) {
      if (tgStatusMsg) {
        tgStatusMsg.classList.remove("hidden");
        tgStatusMsg.innerHTML = `<span class="text-rose-400 font-semibold">❌ Lỗi kết nối mạng</span>`;
      }
    } finally {
      btnSaveTelegram.innerText = "Lưu Cấu Hình";
      btnSaveTelegram.disabled = false;
    }
  });
}


// ==================== QUICK PDF & MEDIA TOOLS LOGIC ====================

const toolCompressSelect = document.getElementById("tool-compress-select");
const btnRunCompress = document.getElementById("btn-run-compress");
const toolCompressResult = document.getElementById("tool-compress-result");
const toolCompressSavedPct = document.getElementById("tool-compress-saved-pct");
const toolCompressOrig = document.getElementById("tool-compress-orig");
const toolCompressNew = document.getElementById("tool-compress-new");
const toolCompressDownloadBtn = document.getElementById("tool-compress-download-btn");

const toolMergeList = document.getElementById("tool-merge-list");
const toolMergeFilename = document.getElementById("tool-merge-filename");
const btnRunMerge = document.getElementById("btn-run-merge");
const toolMergeResult = document.getElementById("tool-merge-result");
const toolMergePages = document.getElementById("tool-merge-pages");
const toolMergeDownloadBtn = document.getElementById("tool-merge-download-btn");

const toolAudioSelect = document.getElementById("tool-audio-select");
const toolAudioBitrate = document.getElementById("tool-audio-bitrate");
const btnRunAudio = document.getElementById("btn-run-audio");
const toolAudioResult = document.getElementById("tool-audio-result");
const toolAudioDownloadBtn = document.getElementById("tool-audio-download-btn");

function populateToolsLists() {
  const pdfs = allFiles.filter(f => f.file_type === "pdf");
  const videos = allFiles.filter(f => f.file_type === "video");

  // Populate Compress Select
  if (toolCompressSelect) {
    if (pdfs.length === 0) {
      toolCompressSelect.innerHTML = `<option value="">-- Chưa có tệp PDF nào trong thư viện --</option>`;
    } else {
      toolCompressSelect.innerHTML = `<option value="">-- Chọn tệp PDF cần nén (${pdfs.length} tệp) --</option>` +
        pdfs.map(p => `<option value="${p.task_id}">${escapeHtml(p.filename)} (${p.size_mb} MB)</option>`).join("");
    }
  }

  // Populate Merge Checkbox List
  if (toolMergeList) {
    if (pdfs.length === 0) {
      toolMergeList.innerHTML = `<span class="text-slate-500 text-[11px]">Chưa có tệp PDF nào trong thư viện.</span>`;
    } else {
      toolMergeList.innerHTML = pdfs.map(p => `
        <label class="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-800/80 cursor-pointer">
          <input type="checkbox" name="merge-pdf-item" value="${p.task_id}" class="w-3.5 h-3.5 text-purple-600 rounded bg-slate-950 border-slate-700">
          <span class="truncate flex-1 font-mono text-[11px] text-slate-200">${escapeHtml(p.filename)}</span>
          <span class="text-[10px] text-slate-400 font-mono flex-shrink-0">${p.size_mb} MB</span>
        </label>
      `).join("");
    }
  }

  // Populate Audio Select
  if (toolAudioSelect) {
    if (videos.length === 0) {
      toolAudioSelect.innerHTML = `<option value="">-- Chưa có tệp video nào trong thư viện --</option>`;
    } else {
      toolAudioSelect.innerHTML = `<option value="">-- Chọn tệp video (${videos.length} video) --</option>` +
        videos.map(v => `<option value="${v.task_id}">${escapeHtml(v.filename)} (${v.size_mb} MB)</option>`).join("");
    }
  }
}

// Compress PDF Action
if (btnRunCompress) {
  btnRunCompress.addEventListener("click", async () => {
    const tid = toolCompressSelect?.value;
    if (!tid) {
      alert("Vui lòng chọn 1 tệp PDF cần nén!");
      return;
    }

    btnRunCompress.innerText = "Đang nén dữ liệu qua Pikepdf...";
    btnRunCompress.disabled = true;

    try {
      const res = await fetch("/api/tools/compress-pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: tid })
      });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        if (toolCompressSavedPct) toolCompressSavedPct.innerText = data.percentage_saved;
        if (toolCompressOrig) toolCompressOrig.innerText = data.original_size_mb;
        if (toolCompressNew) toolCompressNew.innerText = data.compressed_size_mb;
        if (toolCompressDownloadBtn) {
          toolCompressDownloadBtn.href = data.download_url;
          toolCompressDownloadBtn.setAttribute("download", data.filename);
        }
        if (toolCompressResult) toolCompressResult.classList.remove("hidden");
        loadFilesList();
      } else {
        alert("Lỗi nén PDF: " + (data.detail || "Không thể nén tệp"));
      }
    } catch (err) {
      alert("Lỗi kết nối máy chủ khi nén PDF.");
    } finally {
      btnRunCompress.innerText = "Bắt Đầu Nén PDF";
      btnRunCompress.disabled = false;
    }
  });
}

// Merge PDFs Action
if (btnRunMerge) {
  btnRunMerge.addEventListener("click", async () => {
    const selected = Array.from(document.querySelectorAll("input[name='merge-pdf-item']:checked")).map(cb => cb.value);
    if (selected.length < 2) {
      alert("Vui lòng tích chọn ít nhất 2 tệp PDF để ghép!");
      return;
    }

    const output_filename = toolMergeFilename?.value.trim() || "tai_lieu_tong_hop.pdf";

    btnRunMerge.innerText = `Đang ghép ${selected.length} tệp PDF...`;
    btnRunMerge.disabled = true;

    try {
      const res = await fetch("/api/tools/merge-pdfs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_ids: selected, output_filename })
      });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        if (toolMergePages) toolMergePages.innerText = data.total_pages;
        if (toolMergeDownloadBtn) {
          toolMergeDownloadBtn.href = data.download_url;
          toolMergeDownloadBtn.setAttribute("download", data.filename);
        }
        if (toolMergeResult) toolMergeResult.classList.remove("hidden");
        loadFilesList();
      } else {
        alert("Lỗi ghép PDF: " + (data.detail || "Không thể ghép tệp"));
      }
    } catch (err) {
      alert("Lỗi kết nối máy chủ khi ghép PDF.");
    } finally {
      btnRunMerge.innerText = "Ghép Các Tệp Này";
      btnRunMerge.disabled = false;
    }
  });
}

// Extract Audio Action
if (btnRunAudio) {
  btnRunAudio.addEventListener("click", async () => {
    const tid = toolAudioSelect?.value;
    if (!tid) {
      alert("Vui lòng chọn 1 video để tách nhạc!");
      return;
    }

    const bitrate = toolAudioBitrate?.value || "320k";

    btnRunAudio.innerText = "FFmpeg đang tách audio MP3...";
    btnRunAudio.disabled = true;

    try {
      const res = await fetch("/api/tools/extract-audio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: tid, bitrate })
      });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        if (toolAudioDownloadBtn) {
          toolAudioDownloadBtn.href = data.download_url;
          toolAudioDownloadBtn.setAttribute("download", data.filename);
        }
        if (toolAudioResult) toolAudioResult.classList.remove("hidden");
        loadFilesList();
      } else {
        alert("Lỗi trích xuất audio: " + (data.detail || "Không thể tách âm thanh"));
      }
    } catch (err) {
      alert("Lỗi kết nối máy chủ khi tách audio.");
    } finally {
      btnRunAudio.innerText = "Trích Xuất Nhạc MP3";
      btnRunAudio.disabled = false;
    }
  });
}


// ==================== URL QUERY PARAMETER DISPATCHER ====================

function handleUrlParamsOnLoad() {
  const urlParams = new URLSearchParams(window.location.search);
  const incomingUrl = urlParams.get("url");
  if (!incomingUrl) return;

  const cleanUrl = decodeURIComponent(incomingUrl).trim();

  if (cleanUrl.includes("scribd.com") || cleanUrl.includes("slideshare.net")) {
    switchTab("scribd");
    if (scribdUrlInput) {
      scribdUrlInput.value = cleanUrl;
      scribdUrlInput.focus();
    }
  } else if (cleanUrl.includes("youtube.com") || cleanUrl.includes("youtu.be")) {
    switchTab("youtube");
    if (ytUrlInput) {
      ytUrlInput.value = cleanUrl;
      ytUrlInput.dispatchEvent(new Event("input"));
    }
  } else if (cleanUrl.includes("facebook.com") || cleanUrl.includes("fb.watch") || cleanUrl.includes("tiktok.com") || cleanUrl.includes("instagram.com")) {
    switchTab("facebook");
    if (fbUrlInput) {
      fbUrlInput.value = cleanUrl;
      fbUrlInput.dispatchEvent(new Event("input"));
    }
  } else {
    switchTab("direct");
    if (directUrlInput) {
      directUrlInput.value = cleanUrl;
      directUrlInput.dispatchEvent(new Event("input"));
    }
  }
}

// Initial Boot Sequence
document.addEventListener("DOMContentLoaded", () => {
  initBookmarklet();
  handleUrlParamsOnLoad();
  loadFilesBadgeOnly();
});

// Also run immediately in case DOM is already parsed
initBookmarklet();
handleUrlParamsOnLoad();
loadFilesBadgeOnly();


