/**
 * AutoSlide Studio Client JS — Canvas-First Architecture
 * Pure Vanilla ES6, Zero External Dependencies.
 *
 * Features:
 * - Immediate Ingest State upon PPTX file selection
 * - Robust Preview Artifact Loading with Retry & Error Fallbacks
 * - Slide Filmstrip Navigator with Modified Badges
 * - Side-by-side Before/After Canvas with Highlight Overlays
 * - Click-Drag Region Selection in Slide-Local Normalized Coordinates
 * - Target Scope Control (Current Slide, Region, All Slides)
 * - Chronological Event Timeline & Quality Findings Panel
 * - Human Review Actions (Approve, Repair, Reject)
 */

(function () {
  // Application State
  let currentJobId = null;
  let pollingInterval = null;
  let selectedFile = null;
  let previewDiffData = null;
  let activeSlideIndex = 1;

  // Scope State: "slide", "region", "deck"
  const scopeState = {
    kind: "slide",
    slide_index: 1,
    region: null, // { x, y, width, height } in [0, 1]
  };

  // Drag Selection State
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;

  // DOM Elements — Command Bar
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const fileBadge = document.getElementById("fileBadge");
  const fileBadgeName = document.getElementById("fileBadgeName");
  const ingestStatusPill = document.getElementById("ingestStatusPill");
  const dropzoneText = document.getElementById("dropzoneText");
  const instructionInput = document.getElementById("instructionInput");
  const promptScopeTag = document.getElementById("promptScopeTag");
  const runtimeSelect = document.getElementById("runtimeSelect");
  const runtimeIndicator = document.getElementById("runtimeIndicator");
  const runtimeName = document.getElementById("runtimeName");
  const btnSubmit = document.getElementById("btnSubmit");

  // Scope Elements
  const scopePillSlide = document.getElementById("scopePillSlide");
  const scopePillRegion = document.getElementById("scopePillRegion");
  const scopePillDeck = document.getElementById("scopePillDeck");
  const scopeSlideSelect = document.getElementById("scopeSlideSelect");
  const slideSelectRow = document.getElementById("slideSelectRow");
  const regionBadge = document.getElementById("regionBadge");
  const regionCoordsLabel = document.getElementById("regionCoordsLabel");
  const btnClearRegion = document.getElementById("btnClearRegion");

  // Filmstrip Elements
  const filmstripTrack = document.getElementById("filmstripTrack");
  const filmstripCount = document.getElementById("filmstripCount");
  const filmstripEmpty = document.getElementById("filmstripEmpty");
  const previewNavigator = document.getElementById("previewNavigator");
  const navPills = document.getElementById("navPills");

  // Canvas Diff Elements
  const beforeFrame = document.getElementById("beforeFrame");
  const afterFrame = document.getElementById("afterFrame");
  const beforeImg = document.getElementById("beforeImg");
  const afterImg = document.getElementById("afterImg");
  const beforePlaceholder = document.getElementById("beforePlaceholder");
  const afterPlaceholder = document.getElementById("afterPlaceholder");
  const beforeIngestState = document.getElementById("beforeIngestState");
  const ingestDeckTitle = document.getElementById("ingestDeckTitle");
  const ingestDeckSubtitle = document.getElementById("ingestDeckSubtitle");
  const beforeLoading = document.getElementById("beforeLoading");
  const afterLoading = document.getElementById("afterLoading");
  const beforeError = document.getElementById("beforeError");
  const afterError = document.getElementById("afterError");
  const beforeErrorMsg = document.getElementById("beforeErrorMsg");
  const afterErrorMsg = document.getElementById("afterErrorMsg");
  const btnRetryBefore = document.getElementById("btnRetryBefore");
  const btnRetryAfter = document.getElementById("btnRetryAfter");
  const diffBadge = document.getElementById("diffBadge");
  const afterStatusLabel = document.getElementById("afterStatusLabel");

  // Drag Region & Overlays
  const selectionOverlayCanvas = document.getElementById("selectionOverlayCanvas");
  const selectionRect = document.getElementById("selectionRect");
  const selectionCoordsText = document.getElementById("selectionCoordsText");
  const highlightOverlayLayer = document.getElementById("highlightOverlayLayer");

  // Timeline & Findings
  const eventLogs = document.getElementById("eventLogs");
  const eventCounter = document.getElementById("eventCounter");
  const timelineEmpty = document.getElementById("timelineEmpty");
  const findingsContainer = document.getElementById("findingsContainer");
  const findingsEmpty = document.getElementById("findingsEmpty");
  const qaStatusTag = document.getElementById("qaStatusTag");

  // Action Bar
  const actionBar = document.getElementById("actionBar");
  const btnApprove = document.getElementById("btnApprove");
  const btnReject = document.getElementById("btnReject");
  const btnRepair = document.getElementById("btnRepair");

  // Store URLs for retrying
  let currentBeforeUrl = null;
  let currentAfterUrl = null;

  // Initialize on DOM Ready
  window.addEventListener("DOMContentLoaded", () => {
    initRuntimes();
    setupEventListeners();
    setupRegionSelection();
    updateScopeUI();
  });

  /* ==========================================================================
     Runtime Discovery
     ========================================================================== */
  async function initRuntimes() {
    try {
      const res = await fetch("/api/v1/runtimes");
      if (res.ok) {
        const runtimes = await res.json();
        runtimeSelect.innerHTML = "";
        const available = runtimes.filter((r) => r.available ?? (r.installed && r.authenticated));
        if (available.length > 0) {
          runtimeName.textContent = available[0].name;
          runtimeIndicator.style.backgroundColor = "var(--success)";
        } else {
          runtimeName.textContent = "No runtime ready";
          runtimeIndicator.style.backgroundColor = "var(--danger)";
        }

        runtimes.forEach((r) => {
          const isReady = Boolean(r.available ?? (r.installed && r.authenticated));
          const opt = document.createElement("option");
          opt.value = r.name;
          opt.textContent = `${r.name} (${isReady ? "Ready" : "Unavailable"})`;
          if (!isReady) opt.disabled = true;
          runtimeSelect.appendChild(opt);
        });

        if (available.length > 0) {
          runtimeSelect.value = available[0].name;
        }
      }
    } catch (e) {
      console.warn("Failed to load runtimes:", e);
      if (runtimeName) runtimeName.textContent = "Offline";
    }
  }

  /* ==========================================================================
     Event Listeners
     ========================================================================== */
  function setupEventListeners() {
    // Dropzone drag & drop
    if (dropzone) {
      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("drag-over");
      });
      dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("drag-over");
      });
      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("drag-over");
        if (e.dataTransfer.files.length > 0) {
          handleFileSelect(e.dataTransfer.files[0]);
        }
      });
    }

    if (fileInput) {
      fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
          handleFileSelect(e.target.files[0]);
        }
      });
    }

    // Scope Selection Pills
    if (scopePillSlide) scopePillSlide.addEventListener("click", () => setScopeKind("slide"));
    if (scopePillRegion) scopePillRegion.addEventListener("click", () => setScopeKind("region"));
    if (scopePillDeck) scopePillDeck.addEventListener("click", () => setScopeKind("deck"));

    if (scopeSlideSelect) {
      scopeSlideSelect.addEventListener("change", (e) => {
        const idx = parseInt(e.target.value, 10) || 1;
        selectSlide(idx);
      });
    }

    if (btnClearRegion) {
      btnClearRegion.addEventListener("click", clearRegionSelection);
    }

    // Submit Job
    if (btnSubmit) {
      btnSubmit.addEventListener("click", submitJob);
    }

    // Retries for image loading
    if (btnRetryBefore) {
      btnRetryBefore.addEventListener("click", () => {
        if (currentBeforeUrl) loadPreviewImage("before", currentBeforeUrl, true);
      });
    }
    if (btnRetryAfter) {
      btnRetryAfter.addEventListener("click", () => {
        if (currentAfterUrl) loadPreviewImage("after", currentAfterUrl, true);
      });
    }

    // Human Decisions
    if (btnApprove) btnApprove.addEventListener("click", () => submitDecision("approve"));
    if (btnReject) btnReject.addEventListener("click", () => submitDecision("reject"));
    if (btnRepair) btnRepair.addEventListener("click", () => submitDecision("repair"));
  }

  /* ==========================================================================
     File Selection & Immediate Ingestion State
     ========================================================================== */
  function handleFileSelect(file) {
    if (!file.name.toLowerCase().endsWith(".pptx")) {
      alert("Please select a valid PowerPoint (.pptx) file.");
      return;
    }

    selectedFile = file;
    const formattedSize = (file.size / 1024).toFixed(1) + " KB";

    // 1. Update Command Bar Ingestion Info
    if (fileBadge && fileBadgeName) {
      fileBadge.style.display = "flex";
      fileBadgeName.textContent = file.name;
    }
    if (ingestStatusPill) {
      ingestStatusPill.style.display = "flex";
    }
    if (dropzoneText) {
      dropzoneText.textContent = "Change .pptx file";
    }

    // 2. Immediate Ingest State on Slide Canvas
    if (beforePlaceholder) beforePlaceholder.style.display = "none";
    if (beforeImg) beforeImg.style.display = "none";
    if (beforeError) beforeError.style.display = "none";
    if (beforeLoading) beforeLoading.style.display = "none";

    if (beforeIngestState) {
      beforeIngestState.style.display = "flex";
      if (ingestDeckTitle) ingestDeckTitle.textContent = file.name;
      if (ingestDeckSubtitle) {
        ingestDeckSubtitle.textContent = `Size: ${formattedSize} • Template ready for editing. Enter an instruction prompt to execute.`;
      }
    }

    // 3. Update Filmstrip state
    if (filmstripCount) filmstripCount.textContent = "Ready";
    if (filmstripEmpty) {
      filmstripEmpty.innerHTML = `<span><b>${file.name}</b> selected (${formattedSize}). Run AI Edit to render filmstrip.</span>`;
    }

    appendTimelineEvent("INGEST", `Template selected: ${file.name} (${formattedSize})`);
  }

  /* ==========================================================================
     Target Edit Scope Handling
     ========================================================================== */
  function setScopeKind(kind) {
    scopeState.kind = kind;
    updateScopeUI();
  }

  function updateScopeUI() {
    const kind = scopeState.kind;
    [scopePillSlide, scopePillRegion, scopePillDeck].forEach((pill) => {
      if (pill) pill.classList.remove("active");
    });

    if (kind === "slide") {
      if (scopePillSlide) scopePillSlide.classList.add("active");
      if (slideSelectRow) slideSelectRow.style.display = "flex";
      if (regionBadge) regionBadge.style.display = "none";
      if (promptScopeTag) promptScopeTag.textContent = `Slide ${activeSlideIndex}`;
      if (instructionInput) instructionInput.placeholder = `Edit Slide ${activeSlideIndex} (e.g. Change title, adjust KPI cards)...`;
    } else if (kind === "region") {
      if (scopePillRegion) scopePillRegion.classList.add("active");
      if (slideSelectRow) slideSelectRow.style.display = "flex";
      if (regionBadge) regionBadge.style.display = "flex";
      if (promptScopeTag) promptScopeTag.textContent = `Region S${activeSlideIndex}`;
      if (instructionInput) instructionInput.placeholder = `Edit selected region on Slide ${activeSlideIndex}...`;
    } else if (kind === "deck") {
      if (scopePillDeck) scopePillDeck.classList.add("active");
      if (slideSelectRow) slideSelectRow.style.display = "none";
      if (regionBadge) regionBadge.style.display = "none";
      if (promptScopeTag) promptScopeTag.textContent = "All Slides (Deck)";
      if (instructionInput) instructionInput.placeholder = "Edit entire presentation (e.g. Update company branding across all slides)...";
    }
  }

  function clearRegionSelection() {
    scopeState.region = null;
    if (selectionRect) selectionRect.style.display = "none";
    if (regionBadge) regionBadge.style.display = "none";
    setScopeKind("slide");
  }

  function setupRegionSelection() {
    if (!selectionOverlayCanvas) return;

    selectionOverlayCanvas.addEventListener("mousedown", (e) => {
      const rect = selectionOverlayCanvas.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;

      isDragging = true;
      dragStartX = e.clientX - rect.left;
      dragStartY = e.clientY - rect.top;

      selectionRect.style.left = `${dragStartX}px`;
      selectionRect.style.top = `${dragStartY}px`;
      selectionRect.style.width = "0px";
      selectionRect.style.height = "0px";
      selectionRect.style.display = "block";
    });

    window.addEventListener("mousemove", (e) => {
      if (!isDragging || !selectionOverlayCanvas) return;
      const rect = selectionOverlayCanvas.getBoundingClientRect();
      const currentX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
      const currentY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));

      const boxX = Math.min(dragStartX, currentX);
      const boxY = Math.min(dragStartY, currentY);
      const boxW = Math.abs(currentX - dragStartX);
      const boxH = Math.abs(currentY - dragStartY);

      selectionRect.style.left = `${boxX}px`;
      selectionRect.style.top = `${boxY}px`;
      selectionRect.style.width = `${boxW}px`;
      selectionRect.style.height = `${boxH}px`;

      if (selectionCoordsText && rect.width > 0 && rect.height > 0) {
        const pctW = ((boxW / rect.width) * 100).toFixed(0);
        const pctH = ((boxH / rect.height) * 100).toFixed(0);
        selectionCoordsText.textContent = `${pctW}% × ${pctH}%`;
      }
    });

    window.addEventListener("mouseup", (e) => {
      if (!isDragging || !selectionOverlayCanvas) return;
      isDragging = false;

      const rect = selectionOverlayCanvas.getBoundingClientRect();
      const currentX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
      const currentY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));

      const boxX = Math.min(dragStartX, currentX);
      const boxY = Math.min(dragStartY, currentY);
      const boxW = Math.abs(currentX - dragStartX);
      const boxH = Math.abs(currentY - dragStartY);

      // Require significant drag (> 10px)
      if (boxW > 10 && boxH > 10 && rect.width > 0 && rect.height > 0) {
        const normX = Math.max(0.0, Math.min(1.0, +(boxX / rect.width).toFixed(4)));
        const normY = Math.max(0.0, Math.min(1.0, +(boxY / rect.height).toFixed(4)));
        const normW = Math.max(0.01, Math.min(1.0 - normX, +(boxW / rect.width).toFixed(4)));
        const normH = Math.max(0.01, Math.min(1.0 - normY, +(boxH / rect.height).toFixed(4)));

        scopeState.region = { x: normX, y: normY, width: normW, height: normH };
        scopeState.slide_index = activeSlideIndex;

        setScopeKind("region");
        if (regionCoordsLabel) {
          regionCoordsLabel.textContent = `Region: [${(normX * 100).toFixed(0)}%, ${(normY * 100).toFixed(0)}% • ${(normW * 100).toFixed(0)}%×${(normH * 100).toFixed(0)}%]`;
        }
        if (regionBadge) regionBadge.style.display = "flex";
      } else {
        selectionRect.style.display = "none";
      }
    });
  }

  /* ==========================================================================
     Robust Preview Image Loading & Fallbacks
     ========================================================================== */
  function loadPreviewImage(pane, url, isRetry = false) {
    const isBefore = pane === "before";
    const imgEl = isBefore ? beforeImg : afterImg;
    const loadingEl = isBefore ? beforeLoading : afterLoading;
    const errorEl = isBefore ? beforeError : afterError;
    const errorMsgEl = isBefore ? beforeErrorMsg : afterErrorMsg;
    const placeholderEl = isBefore ? beforePlaceholder : afterPlaceholder;
    const ingestEl = isBefore ? beforeIngestState : null;

    if (!imgEl) return;

    if (isBefore) currentBeforeUrl = url;
    else currentAfterUrl = url;

    // Cache-busting if retrying
    const targetUrl = isRetry ? `${url}${url.includes("?") ? "&" : "?"}_t=${Date.now()}` : url;

    // Show loading skeleton, hide other layers
    if (loadingEl) loadingEl.style.display = "flex";
    if (errorEl) errorEl.style.display = "none";
    if (placeholderEl) placeholderEl.style.display = "none";
    if (ingestEl) ingestEl.style.display = "none";

    imgEl.onload = () => {
      if (loadingEl) loadingEl.style.display = "none";
      if (errorEl) errorEl.style.display = "none";
      imgEl.style.display = "block";
    };

    imgEl.onerror = () => {
      if (loadingEl) loadingEl.style.display = "none";
      imgEl.style.display = "none";
      if (errorEl) {
        errorEl.style.display = "flex";
        if (errorMsgEl) errorMsgEl.textContent = `Could not load ${isBefore ? "original" : "modified"} preview from ${url}`;
      }
    };

    imgEl.src = targetUrl;
  }

  /* ==========================================================================
     Job Submission & Lifecycle
     ========================================================================== */
  async function submitJob() {
    if (!selectedFile) {
      alert("Please choose a PPTX presentation to upload.");
      return;
    }
    const instruction = instructionInput.value.trim();
    if (!instruction) {
      alert("Please provide an edit instruction.");
      instructionInput.focus();
      return;
    }

    btnSubmit.disabled = true;
    btnSubmit.innerHTML = '<span class="spinner" style="width:14px;height:14px;display:inline-block;margin:0 4px 0 0;vertical-align:middle;"></span> Executing...';

    // Show loading on After slide canvas
    if (afterPlaceholder) afterPlaceholder.style.display = "none";
    if (afterError) afterError.style.display = "none";
    if (afterLoading) afterLoading.style.display = "flex";
    if (afterStatusLabel) afterStatusLabel.textContent = "AI Executing...";

    const formData = new FormData();
    formData.append("template", selectedFile);
    formData.append("instruction", instruction);
    if (runtimeSelect.value) {
      formData.append("runtime", runtimeSelect.value);
    }

    const scopePayload = {
      kind: scopeState.kind,
      slide_index: scopeState.slide_index || activeSlideIndex,
      region: scopeState.kind === "region" ? scopeState.region : null,
    };
    formData.append("scope", JSON.stringify(scopePayload));

    try {
      const res = await fetch("/api/v1/jobs", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create job");
      }

      const data = await res.json();
      currentJobId = data.job_id;
      appendTimelineEvent("JOB_CREATED", `Job ${currentJobId} created (Scope: ${scopeState.kind})`);
      updateStepper("INGESTING");
      startPolling(currentJobId);
    } catch (e) {
      alert(`Error creating job: ${e.message}`);
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = '<span class="btn-icon">🚀</span><span class="btn-label">Run AI Edit</span>';
      if (afterLoading) afterLoading.style.display = "none";
      if (afterPlaceholder) afterPlaceholder.style.display = "flex";
    }
  }

  function startPolling(jobId) {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(async () => {
      try {
        const [jobRes, eventsRes] = await Promise.all([
          fetch(`/api/v1/jobs/${jobId}`),
          fetch(`/api/v1/jobs/${jobId}/events`),
        ]);

        if (jobRes.ok) {
          const job = await jobRes.json();
          updateStepper(job.state);

          if (job.state === "AWAITING_USER_APPROVAL") {
            clearInterval(pollingInterval);
            showReviewState(jobId);
          } else if (job.state === "ACCEPTED") {
            clearInterval(pollingInterval);
            showAcceptedState(jobId);
          } else if (job.state === "FAILED" || job.state === "REJECTED" || job.state === "CANCELLED") {
            clearInterval(pollingInterval);
            showTerminalState(job.state);
          }
        }

        if (eventsRes.ok) {
          const events = await eventsRes.json();
          renderEvents(events);
        }
      } catch (e) {
        console.warn("Polling error:", e);
      }
    }, 1200);
  }

  function updateStepper(state) {
    const steps = ["INGEST", "PLAN", "EXECUTE", "VERIFY", "REVIEW"];
    let activeIdx = 0;

    if (state === "INGESTING" || state === "CREATED") activeIdx = 0;
    else if (state === "PLANNING" || state === "AWAITING_PLAN_REVIEW") activeIdx = 1;
    else if (state === "EXECUTING" || state === "RENDERING") activeIdx = 2;
    else if (state === "VERIFYING" || state === "REPAIRING") activeIdx = 3;
    else if (state === "AWAITING_USER_APPROVAL" || state === "ACCEPTED") activeIdx = 4;

    document.querySelectorAll(".step-item").forEach((el, idx) => {
      el.classList.remove("active", "completed");
      if (idx < activeIdx) el.classList.add("completed");
      if (idx === activeIdx) el.classList.add("active");
    });
  }

  /* ==========================================================================
     Filmstrip & Diff Presentation
     ========================================================================== */
  async function showReviewState(jobId) {
    if (actionBar) actionBar.style.display = "flex";
    btnSubmit.disabled = false;
    btnSubmit.innerHTML = '<span class="btn-icon">🚀</span><span class="btn-label">Run AI Edit</span>';
    if (afterStatusLabel) afterStatusLabel.textContent = "Modified & Verified";

    // Load preview diff pairs & metadata
    try {
      const diffRes = await fetch(`/api/v1/jobs/${jobId}/diff`);
      if (diffRes.ok) {
        previewDiffData = await diffRes.json();
        buildSlideNavigator(previewDiffData);
        populateSlideSelector(previewDiffData.total_slides);
        renderSlideDiff(activeSlideIndex);
      } else {
        loadFallbackPreviews(jobId);
      }
    } catch (e) {
      console.warn("Diff load fallback:", e);
      loadFallbackPreviews(jobId);
    }

    // Load quality findings
    try {
      const res = await fetch(`/api/v1/jobs/${jobId}/artifacts/quality_report.json`);
      if (res.ok) {
        const report = await res.json();
        renderFindings(report.visual_result ? report.visual_result.findings : []);
        if (qaStatusTag) {
          qaStatusTag.textContent = report.overall_verdict || "Passed";
          qaStatusTag.style.color = report.overall_verdict === "FAILED" ? "var(--danger)" : "var(--success)";
        }
      }
    } catch (e) {
      console.warn("Findings load fallback:", e);
    }
  }

  function buildSlideNavigator(diffData) {
    buildFilmstrip(diffData);
  }

  function buildFilmstrip(diffData) {
    if (!filmstripTrack) return;
    filmstripTrack.innerHTML = "";

    if (!diffData || !diffData.slides || diffData.slides.length === 0) {
      if (filmstripEmpty) filmstripTrack.appendChild(filmstripEmpty);
      return;
    }

    if (filmstripCount) {
      filmstripCount.textContent = `${diffData.total_slides} Slides`;
    }

    // Build modern filmstrip items
    diffData.slides.forEach((spd) => {
      const item = document.createElement("div");
      item.className = `filmstrip-item ${spd.slide_index === activeSlideIndex ? "active" : ""}`;
      item.setAttribute("role", "tab");
      item.setAttribute("aria-selected", spd.slide_index === activeSlideIndex ? "true" : "false");

      const thumb = document.createElement("div");
      thumb.className = "filmstrip-thumb-preview";
      if (spd.after_image_url || spd.before_image_url) {
        const img = document.createElement("img");
        img.src = spd.after_image_url || spd.before_image_url;
        img.alt = `Slide ${spd.slide_index}`;
        thumb.appendChild(img);
      } else {
        thumb.textContent = `S${spd.slide_index}`;
      }

      const title = document.createElement("span");
      title.className = "filmstrip-item-title";
      title.textContent = `Slide ${spd.slide_index}`;

      item.appendChild(thumb);
      item.appendChild(title);

      if (spd.status === "modified") {
        const tag = document.createElement("span");
        tag.className = "filmstrip-modified-tag";
        tag.textContent = "Modified";
        item.appendChild(tag);
      }

      item.addEventListener("click", () => {
        selectSlide(spd.slide_index);
      });

      filmstripTrack.appendChild(item);
    });

    // Populate legacy nav-pills for backwards compatibility with tests
    if (navPills) {
      navPills.innerHTML = "";
      if (previewNavigator) previewNavigator.style.display = "flex";
      diffData.slides.forEach((spd) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `nav-pill-btn ${spd.slide_index === activeSlideIndex ? "active" : ""} ${spd.status === "modified" ? "modified" : ""}`;
        btn.textContent = `Slide ${spd.slide_index}`;
        btn.addEventListener("click", () => selectSlide(spd.slide_index));
        navPills.appendChild(btn);
      });
    }
  }

  function selectSlide(slideIndex) {
    activeSlideIndex = slideIndex;
    scopeState.slide_index = activeSlideIndex;
    if (scopeSlideSelect) scopeSlideSelect.value = String(activeSlideIndex);
    updateScopeUI();

    // Update active class in filmstrip
    document.querySelectorAll(".filmstrip-item").forEach((el, idx) => {
      const isCur = idx + 1 === activeSlideIndex;
      el.classList.toggle("active", isCur);
      el.setAttribute("aria-selected", isCur ? "true" : "false");
    });

    // Update legacy nav-pill buttons
    document.querySelectorAll(".nav-pill-btn").forEach((b, idx) => {
      b.classList.toggle("active", idx + 1 === activeSlideIndex);
    });

    renderSlideDiff(activeSlideIndex);
  }

  function populateSlideSelector(totalSlides) {
    if (!scopeSlideSelect) return;
    scopeSlideSelect.innerHTML = "";
    for (let i = 1; i <= totalSlides; i++) {
      const opt = document.createElement("option");
      opt.value = String(i);
      opt.textContent = `Slide ${i}`;
      if (i === activeSlideIndex) opt.selected = true;
      scopeSlideSelect.appendChild(opt);
    }
  }

  function renderSlideDiff(slideIndex) {
    if (!previewDiffData || !previewDiffData.slides) return;
    const spd = previewDiffData.slides.find((s) => s.slide_index === slideIndex) || previewDiffData.slides[0];
    if (!spd) return;

    if (spd.before_image_url) {
      loadPreviewImage("before", spd.before_image_url);
    }
    if (spd.after_image_url) {
      loadPreviewImage("after", spd.after_image_url);
    }

    if (diffBadge) {
      diffBadge.style.display = spd.status === "modified" ? "inline-block" : "none";
      diffBadge.textContent = spd.status === "modified" ? "● Changed" : "Unchanged";
    }

    renderOverlays(spd.overlays);
  }

  function renderOverlays(overlays) {
    if (!highlightOverlayLayer) return;
    highlightOverlayLayer.innerHTML = "";

    if (!overlays || overlays.length === 0) return;

    overlays.forEach((ov) => {
      const box = document.createElement("div");
      box.className = "diff-highlight-box";
      box.style.left = `${(ov.x * 100).toFixed(2)}%`;
      box.style.top = `${(ov.y * 100).toFixed(2)}%`;
      box.style.width = `${(ov.width * 100).toFixed(2)}%`;
      box.style.height = `${(ov.height * 100).toFixed(2)}%`;
      box.title = `${ov.shape_name || "Element"} (${ov.change_type || "modified"})`;

      const label = document.createElement("div");
      label.className = "diff-highlight-label";
      label.textContent = ov.shape_name || "Modified Element";
      box.appendChild(label);

      highlightOverlayLayer.appendChild(box);
    });
  }

  function loadFallbackPreviews(jobId) {
    loadPreviewImage("before", `/api/v1/jobs/${jobId}/artifacts/slide_001_before.png`);
    loadPreviewImage("after", `/api/v1/jobs/${jobId}/artifacts/slide_001_after.png`);
  }

  /* ==========================================================================
     Event Timeline & Quality Findings
     ========================================================================== */
  function renderEvents(events) {
    if (!eventLogs) return;
    eventLogs.innerHTML = "";

    if (!events || events.length === 0) {
      if (timelineEmpty) eventLogs.appendChild(timelineEmpty);
      return;
    }

    if (eventCounter) eventCounter.textContent = `${events.length} events`;

    events.forEach((ev) => {
      const entry = document.createElement("div");
      entry.className = "timeline-entry log-entry";

      const time = new Date(ev.timestamp).toLocaleTimeString();
      const payloadSummary = formatEventPayload(ev.payload);

      entry.innerHTML = `
        <span class="timeline-time log-time">[${time}]</span>
        <span class="timeline-event-name log-msg"><b>${ev.event_type}</b></span>
        <span class="timeline-detail">${payloadSummary}</span>
      `;
      eventLogs.appendChild(entry);
    });

    eventLogs.scrollTop = eventLogs.scrollHeight;
  }

  function formatEventPayload(payload) {
    if (!payload || typeof payload !== "object") return "";
    if (payload.message) return payload.message;
    if (payload.stage) return `Stage: ${payload.stage}`;
    if (payload.error) return `<span style="color:var(--danger)">${payload.error}</span>`;
    return JSON.stringify(payload);
  }

  function appendTimelineEvent(type, msg) {
    if (!eventLogs) return;
    if (timelineEmpty && timelineEmpty.parentNode) {
      timelineEmpty.parentNode.removeChild(timelineEmpty);
    }

    const entry = document.createElement("div");
    entry.className = "timeline-entry log-entry";
    const time = new Date().toLocaleTimeString();
    entry.innerHTML = `
      <span class="timeline-time log-time">[${time}]</span>
      <span class="timeline-event-name log-msg"><b>${type}</b></span>
      <span class="timeline-detail">${msg}</span>
    `;
    eventLogs.appendChild(entry);
    eventLogs.scrollTop = eventLogs.scrollHeight;
  }

  function renderFindings(findings) {
    if (!findingsContainer) return;
    findingsContainer.innerHTML = "";

    if (!findings || findings.length === 0) {
      findingsContainer.innerHTML = '<div style="color: var(--success); font-size: 0.85rem; padding: 0.5rem;">✨ All quality gates passed cleanly. Zero defects detected.</div>';
      return;
    }

    findings.forEach((f) => {
      const card = document.createElement("div");
      card.className = `finding-card severity-${f.severity || "INFO"}`;
      card.innerHTML = `
        <div class="finding-header">
          <span>Slide ${f.slide_index || 1} • ${f.shape_name || "Element"}</span>
          <span style="color: var(--${f.severity === 'ERROR' ? 'danger' : 'warning'});">${f.category || "Check"}</span>
        </div>
        <div class="finding-msg">${f.message}</div>
        ${f.suggested_fix ? `<div class="finding-fix">💡 ${f.suggested_fix}</div>` : ""}
      `;
      findingsContainer.appendChild(card);
    });
  }

  /* ==========================================================================
     Human Review Decision Actions
     ========================================================================== */
  async function submitDecision(decision) {
    if (!currentJobId) return;

    try {
      const res = await fetch(`/api/v1/jobs/${currentJobId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });

      if (!res.ok) throw new Error("Failed to submit decision");
      const resp = await res.json();

      if (decision === "approve") {
        if (resp.download_url) {
          window.location.href = resp.download_url;
        }
        showAcceptedState(currentJobId);
      } else if (decision === "reject") {
        showTerminalState("REJECTED");
      } else if (decision === "repair") {
        appendTimelineEvent("REPAIR", "Repair requested by user. Pipeline re-running...");
        startPolling(currentJobId);
      }
    } catch (e) {
      alert(`Decision error: ${e.message}`);
    }
  }

  function showAcceptedState(jobId) {
    updateStepper("ACCEPTED");
    if (actionBar) {
      actionBar.innerHTML = `
        <div class="action-bar-info">
          <div class="action-bar-status">
            <span class="status-indicator-dot" style="background:var(--success);box-shadow:0 0 6px var(--success)"></span>
            <span class="action-bar-title">Presentation Approved & Finalized</span>
          </div>
          <div class="action-bar-desc">Your edited PPTX presentation has been compiled and accepted.</div>
        </div>
        <div class="action-buttons">
          <a href="/api/v1/jobs/${jobId}/artifacts/presentation.pptx" class="btn-success" style="text-decoration:none;display:inline-flex;align-items:center;gap:0.4rem;" download>
            <span>📥 Download PPTX</span>
          </a>
        </div>
      `;
    }
  }

  function showTerminalState(state) {
    updateStepper(state);
    if (actionBar) {
      actionBar.innerHTML = `
        <div class="action-bar-info">
          <div class="action-bar-status">
            <span class="status-indicator-dot" style="background:var(--danger);box-shadow:0 0 6px var(--danger)"></span>
            <span class="action-bar-title">Job Ended (${state})</span>
          </div>
          <div class="action-bar-desc">This job has completed with state: ${state}.</div>
        </div>
      `;
    }
  }
})();
