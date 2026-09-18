/**
 * AutoSlide Local Workbench Client JS — Vanilla ES6, Zero External Dependencies
 */

(function () {
  let currentJobId = null;
  let pollingInterval = null;
  let selectedFile = null;

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

  // Init
  window.addEventListener("DOMContentLoaded", () => {
    initRuntimes();
    setupEventListeners();
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

    // Submit Job
    btnSubmit.addEventListener("click", submitJob);

    // Decision Actions
    if (btnApprove) btnApprove.addEventListener("click", () => submitDecision("approve"));
    if (btnReject) btnReject.addEventListener("click", () => submitDecision("reject"));
    if (btnRepair) btnRepair.addEventListener("click", () => submitDecision("repair"));
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
      appendLog("System", `Job created: ${currentJobId}`);
      updateStepper("INGESTING");

      startPolling(currentJobId);
    } catch (e) {
      alert(`Error creating job: ${e.message}`);
      btnSubmit.disabled = false;
      btnSubmit.textContent = "Start AI Slide Edit";
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
    btnSubmit.textContent = "Start AI Slide Edit";

    // Load previews
    try {
      beforeImg.src = `/api/v1/jobs/${jobId}/artifacts/slide_001_before.png`;
      beforeImg.style.display = "block";
      beforePlaceholder.style.display = "none";

      afterImg.src = `/api/v1/jobs/${jobId}/artifacts/slide_001_after.png`;
      afterImg.style.display = "block";
      afterPlaceholder.style.display = "none";
    } catch (e) {
      console.warn("Preview load fallback:", e);
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
