/**
 * AutoSlide Local Workbench Client JS — Vanilla ES6, Zero External Dependencies
 * Implements: Edit Scope (Current Slide, Region, All Slides), Click-Drag Region Selection,
 * Interactive Slide Diff Studio Navigator, and Changed-Region Highlight Overlays.
 */

(function () {
  let currentJobId = null;
  let pollingInterval = null;
  let selectedFile = null;
  let previewDiffData = null;
  let activeSlideIndex = 1;

  // Scope State
  let scopeState = {
    kind: "slide", // "slide", "region", "deck"
    slide_index: 1,
    region: null, // { x, y, width, height } normalized to [0, 1]
  };

  // Drag selection state
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;

  // DOM Elements
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const fileBadge = document.getElementById("fileBadge");
  const instructionInput = document.getElementById("instructionInput");
  const runtimeSelect = document.getElementById("runtimeSelect");
  const btnSubmit = document.getElementById("btnSubmit");
  const eventLogs = document.getElementById("eventLogs");
  const runtimeIndicator = document.getElementById("runtimeIndicator");
  const runtimeName = document.getElementById("runtimeName");
  const findingsContainer = document.getElementById("findingsContainer");
  const beforeImg = document.getElementById("beforeImg");
  const afterImg = document.getElementById("afterImg");
  const beforePlaceholder = document.getElementById("beforePlaceholder");
  const afterPlaceholder = document.getElementById("afterPlaceholder");
  const actionBar = document.getElementById("actionBar");
  const btnApprove = document.getElementById("btnApprove");
  const btnReject = document.getElementById("btnReject");
  const btnRepair = document.getElementById("btnRepair");

  // Scope & Diff Elements
  const scopePillSlide = document.getElementById("scopePillSlide");
  const scopePillRegion = document.getElementById("scopePillRegion");
  const scopePillDeck = document.getElementById("scopePillDeck");
  const scopeSlideSelect = document.getElementById("scopeSlideSelect");
  const slideSelectRow = document.getElementById("slideSelectRow");
  const regionBadge = document.getElementById("regionBadge");
  const regionCoordsLabel = document.getElementById("regionCoordsLabel");
  const btnClearRegion = document.getElementById("btnClearRegion");
  const previewNavigator = document.getElementById("previewNavigator");
  const navPills = document.getElementById("navPills");
  const selectionOverlayCanvas = document.getElementById("selectionOverlayCanvas");
  const selectionRect = document.getElementById("selectionRect");
  const highlightOverlayLayer = document.getElementById("highlightOverlayLayer");
  const diffBadge = document.getElementById("diffBadge");

  // Init
  window.addEventListener("DOMContentLoaded", () => {
    initRuntimes();
    setupEventListeners();
    setupRegionSelection();
  });

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
          if (!isReady) {
            opt.disabled = true;
          }
          runtimeSelect.appendChild(opt);
        });
        if (available.length > 0) {
          runtimeSelect.value = available[0].name;
        }
      }
    } catch (e) {
      console.warn("Failed to load runtimes:", e);
    }
  }

  function setupEventListeners() {
    // Dropzone
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
    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
      }
    });

    // Scope Selection Pills
    if (scopePillSlide) {
      scopePillSlide.addEventListener("click", () => setScopeKind("slide"));
    }
    if (scopePillRegion) {
      scopePillRegion.addEventListener("click", () => setScopeKind("region"));
    }
    if (scopePillDeck) {
      scopePillDeck.addEventListener("click", () => setScopeKind("deck"));
    }

    if (scopeSlideSelect) {
      scopeSlideSelect.addEventListener("change", (e) => {
        scopeState.slide_index = parseInt(e.target.value, 10) || 1;
        activeSlideIndex = scopeState.slide_index;
        if (previewDiffData) {
          renderSlideDiff(activeSlideIndex);
        }
      });
    }

    if (btnClearRegion) {
      btnClearRegion.addEventListener("click", clearRegionSelection);
    }

    // Submit Job
    btnSubmit.addEventListener("click", submitJob);

    // Decision Actions
    if (btnApprove) btnApprove.addEventListener("click", () => submitDecision("approve"));
    if (btnReject) btnReject.addEventListener("click", () => submitDecision("reject"));
    if (btnRepair) btnRepair.addEventListener("click", () => submitDecision("repair"));
  }

  function setScopeKind(kind) {
    scopeState.kind = kind;
    [scopePillSlide, scopePillRegion, scopePillDeck].forEach((pill) => {
      if (pill) pill.classList.remove("active");
    });

    if (kind === "slide") {
      if (scopePillSlide) scopePillSlide.classList.add("active");
      if (slideSelectRow) slideSelectRow.style.display = "flex";
      if (regionBadge) regionBadge.style.display = "none";
    } else if (kind === "region") {
      if (scopePillRegion) scopePillRegion.classList.add("active");
      if (slideSelectRow) slideSelectRow.style.display = "flex";
      if (regionBadge) regionBadge.style.display = "flex";
    } else if (kind === "deck") {
      if (scopePillDeck) scopePillDeck.classList.add("active");
      if (slideSelectRow) slideSelectRow.style.display = "none";
      if (regionBadge) regionBadge.style.display = "none";
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

      // Only accept selection if width and height are significant (> 10px)
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

  function handleFileSelect(file) {
    if (!file.name.toLowerCase().endsWith(".pptx")) {
      alert("Please select a valid PowerPoint (.pptx) file.");
      return;
    }
    selectedFile = file;
    fileBadge.style.display = "block";
    fileBadge.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  }

  async function submitJob() {
    if (!selectedFile) {
      alert("Please choose a PPTX presentation to upload.");
      return;
    }
    const instruction = instructionInput.value.trim();
    if (!instruction) {
      alert("Please provide an edit instruction.");
      return;
    }

    btnSubmit.disabled = true;
    btnSubmit.textContent = "Creating Job...";

    const formData = new FormData();
    formData.append("template", selectedFile);
    formData.append("instruction", instruction);
    if (runtimeSelect.value) {
      formData.append("runtime", runtimeSelect.value);
    }

    // Pass structured edit scope
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
      appendLog("System", `Job created: ${currentJobId} (scope: ${scopeState.kind})`);
      updateStepper("INGESTING");

      startPolling(currentJobId);
    } catch (e) {
      alert(`Error creating job: ${e.message}`);
      btnSubmit.disabled = false;
      btnSubmit.textContent = "🚀 Start AI Slide Edit";
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
    }, 1500);
  }

  function updateStepper(state) {
    const steps = ["INGESTING", "PLANNING", "EXECUTING", "VERIFYING", "AWAITING_USER_APPROVAL", "ACCEPTED"];
    const stepIdx = steps.indexOf(state);

    document.querySelectorAll(".step-item").forEach((el, idx) => {
      el.classList.remove("active", "completed");
      if (idx < stepIdx) el.classList.add("completed");
      if (idx === stepIdx) el.classList.add("active");
    });
  }

  function renderEvents(events) {
    eventLogs.innerHTML = "";
    events.forEach((ev) => {
      const entry = document.createElement("div");
      entry.className = "log-entry";
      entry.innerHTML = `<span class="log-time">[${new Date(ev.timestamp).toLocaleTimeString()}]</span> <span class="log-msg"><b>${ev.event_type}</b>: ${JSON.stringify(ev.payload)}</span>`;
      eventLogs.appendChild(entry);
    });
    eventLogs.scrollTop = eventLogs.scrollHeight;
  }

  function appendLog(type, msg) {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML = `<span class="log-time">[${new Date().toLocaleTimeString()}]</span> <span class="log-msg"><b>${type}</b>: ${msg}</span>`;
    eventLogs.appendChild(entry);
    eventLogs.scrollTop = eventLogs.scrollHeight;
  }

  async function showReviewState(jobId) {
    actionBar.style.display = "flex";
    btnSubmit.disabled = false;
    btnSubmit.textContent = "🚀 Start AI Slide Edit";

    // Load preview diff pairs & metadata
    try {
      const diffRes = await fetch(`/api/v1/jobs/${jobId}/diff`);
      if (diffRes.ok) {
        previewDiffData = await diffRes.json();
        buildSlideNavigator(previewDiffData);
        populateSlideSelector(previewDiffData.total_slides);
        renderSlideDiff(activeSlideIndex);
      } else {
        // Fallback to slide 1 direct artifacts
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
        renderFindings(report.visual_result.findings);
      }
    } catch (e) {
      console.warn("Findings load fallback:", e);
    }
  }

  function buildSlideNavigator(diffData) {
    if (!previewNavigator || !navPills) return;
    navPills.innerHTML = "";

    if (!diffData || !diffData.slides || diffData.slides.length === 0) {
      previewNavigator.style.display = "none";
      return;
    }

    previewNavigator.style.display = "flex";
    diffData.slides.forEach((spd) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `nav-pill-btn ${spd.slide_index === activeSlideIndex ? "active" : ""} ${spd.status === "modified" ? "modified" : ""}`;
      btn.textContent = `Slide ${spd.slide_index}`;
      btn.addEventListener("click", () => {
        activeSlideIndex = spd.slide_index;
        scopeState.slide_index = activeSlideIndex;
        if (scopeSlideSelect) scopeSlideSelect.value = String(activeSlideIndex);
        document.querySelectorAll(".nav-pill-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        renderSlideDiff(activeSlideIndex);
      });
      navPills.appendChild(btn);
    });
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

    beforeImg.src = spd.before_image_url;
    beforeImg.style.display = "block";
    beforePlaceholder.style.display = "none";

    afterImg.src = spd.after_image_url;
    afterImg.style.display = "block";
    afterPlaceholder.style.display = "none";

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
      box.title = `${ov.shape_name} (${ov.change_type})`;

      const label = document.createElement("div");
      label.className = "diff-highlight-label";
      label.textContent = ov.shape_name || "Modified Element";
      box.appendChild(label);

      highlightOverlayLayer.appendChild(box);
    });
  }

  function loadFallbackPreviews(jobId) {
    beforeImg.src = `/api/v1/jobs/${jobId}/artifacts/slide_001_before.png`;
    beforeImg.style.display = "block";
    beforePlaceholder.style.display = "none";

    afterImg.src = `/api/v1/jobs/${jobId}/artifacts/slide_001_after.png`;
    afterImg.style.display = "block";
    afterPlaceholder.style.display = "none";
  }

  function renderFindings(findings) {
    findingsContainer.innerHTML = "";
    if (!findings || findings.length === 0) {
      findingsContainer.innerHTML = '<div style="color: var(--success); font-size: 0.9rem;">✨ Zero visual or structural defects detected. Perfect pass!</div>';
      return;
    }

    findings.forEach((f) => {
      const card = document.createElement("div");
      card.className = `finding-card severity-${f.severity}`;
      card.innerHTML = `
        <div class="finding-header">
          <span>Slide ${f.slide_index} • ${f.shape_name}</span>
          <span style="color: var(--${f.severity === 'ERROR' ? 'danger' : 'warning'});">${f.category}</span>
        </div>
        <div class="finding-msg">${f.message}</div>
        ${f.suggested_fix ? `<div class="finding-fix">💡 ${f.suggested_fix}</div>` : ''}
      `;
      findingsContainer.appendChild(card);
    });
  }

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
        alert("Presentation approved! Starting download...");
        if (resp.download_url) {
          window.location.href = resp.download_url;
        }
        showAcceptedState(currentJobId);
      } else if (decision === "reject") {
        alert("Changes rejected and discarded.");
        showTerminalState("REJECTED");
      } else if (decision === "repair") {
        alert("Repair requested. Restarting pipeline...");
        startPolling(currentJobId);
      }
    } catch (e) {
      alert(`Decision error: ${e.message}`);
    }
  }

  function showAcceptedState(jobId) {
    updateStepper("ACCEPTED");
    actionBar.innerHTML = `
      <div style="color: var(--success); font-weight: 600;">✅ Job Accepted & Finalized</div>
      <a href="/api/v1/jobs/${jobId}/artifacts/presentation.pptx" class="btn-success" style="text-decoration: none;">Download PPTX</a>
    `;
  }

  function showTerminalState(state) {
    updateStepper(state);
    actionBar.innerHTML = `<div style="color: var(--danger); font-weight: 600;">Job Ended with status: ${state}</div>`;
  }
})();
