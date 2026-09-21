/**
 * AutoSlide Studio Client JS — Canvas-First Architecture & Always-On Chatbot (ADS-002)
 * Pure Vanilla ES6, Zero External Dependencies.
 *
 * Features:
 * - Always-on Chatbot Rail with Multi-turn Dialogue (/api/v1/sessions)
 * - Interactive Cards: QuestionCard, PlanCard, SourceCard, ExecutionCard, ReviewCard, ErrorCard
 * - Selection Context Binding from Canvas Region Drag & Filmstrip Navigator
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
  let activeSessionId = null;
  let pollingInterval = null;
  let selectedFile = null;
  let previewDiffData = null;
  let activeSlideIndex = 1;
  let isChatBusy = false;

  // Selection Context State for Chat
  let chatSelectionContext = {
    slide_index: 1,
    object_ref: null,
    selected_text: null,
  };

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

  // Action Bar (Human Review)
  const actionBar = document.getElementById("actionBar");
  const btnApprove = document.getElementById("btnApprove");
  const btnReject = document.getElementById("btnReject");
  const btnRepair = document.getElementById("btnRepair");

  // Chatbot Rail Elements (ADS-002)
  const chatRail = document.getElementById("chatRail");
  const chatHeader = document.getElementById("chatHeader");
  const chatHeaderStatus = document.getElementById("chatHeaderStatus");
  const chatStatusText = document.getElementById("chatStatusText");
  const chatMessages = document.getElementById("chatMessages");
  const chatComposer = document.getElementById("chatComposer");
  const chatInput = document.getElementById("chatInput");
  const btnSendChat = document.getElementById("btnSendChat");
  const chatContextBadge = document.getElementById("chatContextBadge");
  const chatContextLabel = document.getElementById("chatContextLabel");
  const btnClearChatContext = document.getElementById("btnClearChatContext");

  // Dual-Column All Slides Elements (ADS-003)
  const beforeDeckList = document.getElementById("beforeDeckList");
  const afterDeckList = document.getElementById("afterDeckList");
  const beforeDeckCountBadge = document.getElementById("beforeDeckCountBadge");
  const afterDeckCountBadge = document.getElementById("afterDeckCountBadge");
  const btnModeAgent = document.getElementById("btnModeAgent");
  const btnModePlan = document.getElementById("btnModePlan");
  let chatMode = "agent";
  let currentDeckState = null;

  // Local URL caches & Retry management
  let currentBeforeUrl = null;
  let currentAfterUrl = null;
  let beforeRetryCount = 0;
  let afterRetryCount = 0;
  const MAX_IMAGE_RETRIES = 5;

  /* ==========================================================================
     Initialization
     ========================================================================== */
  document.addEventListener("DOMContentLoaded", () => {
    initRuntimes();
    setupEventListeners();
    setupRegionSelection();
    setupChatListeners();
    updateScopeUI();
    updateChatSelectionContext({ slide_index: activeSlideIndex });

    // Restore session if present in URL query param or localStorage
    const urlParams = new URLSearchParams(window.location.search);
    const sessionFromUrl = urlParams.get("session_id") || localStorage.getItem("autoslide_active_session_id");
    if (sessionFromUrl) {
      activeSessionId = sessionFromUrl;
      if (chatStatusText) chatStatusText.textContent = "Session Restored";
      loadSessionDeck(sessionFromUrl);
    }
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

  function setupChatListeners() {
    if (btnSendChat) {
      btnSendChat.addEventListener("click", () => {
        if (chatInput) sendChatMessage(chatInput.value.trim());
      });
    }

    if (chatInput) {
      chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendChatMessage(chatInput.value.trim());
        }
      });
    }

    if (btnClearChatContext) {
      btnClearChatContext.addEventListener("click", clearChatSelectionContext);
    }

    if (btnModeAgent) {
      btnModeAgent.addEventListener("click", () => {
        chatMode = "agent";
        btnModeAgent.classList.add("active");
        if (btnModePlan) btnModePlan.classList.remove("active");
      });
    }

    if (btnModePlan) {
      btnModePlan.addEventListener("click", () => {
        chatMode = "plan";
        btnModePlan.classList.add("active");
        if (btnModeAgent) btnModeAgent.classList.remove("active");
      });
    }
  }

  /* ==========================================================================
     File Selection & Session Management
     ========================================================================== */
  async function handleFileSelect(file) {
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
        ingestDeckSubtitle.textContent = `Size: ${formattedSize} • Template ready for editing. Enter a prompt or chat with Agent.`;
      }
    }

    // 3. Update Filmstrip state
    if (filmstripCount) filmstripCount.textContent = "Ready";
    if (filmstripEmpty) {
      filmstripEmpty.innerHTML = `<span><b>${file.name}</b> selected (${formattedSize}). Run AI Edit to render filmstrip.</span>`;
    }

    appendTimelineEvent("INGEST", `Template selected: ${file.name} (${formattedSize})`);

    // 4. Initialize Conversational Session (ADS-002)
    await createSessionForFile(file);
  }

  async function createSessionForFile(file) {
    const formData = new FormData();
    formData.append("template", file);

    try {
      if (chatStatusText) chatStatusText.textContent = "Creating session...";
      const res = await fetch("/api/v1/sessions", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to create conversation session");
      }

      const data = await res.json();
      activeSessionId = data.session_id;
      if (data.job_id) {
        currentJobId = data.job_id;
      }

      try {
        localStorage.setItem("autoslide_active_session_id", activeSessionId);
        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set("session_id", activeSessionId);
        window.history.replaceState(null, "", currentUrl.toString());
      } catch (e) {
        console.warn("Could not save session URL state:", e);
      }

      if (chatStatusText) chatStatusText.textContent = "Session Active";
      appendTimelineEvent("SESSION_CREATED", `Conversational session ${activeSessionId} initialized for ${file.name}`);

      // Load initial full-deck Before == After state for Dual-Column Canvas (ADS-003)
      await loadSessionDeck(activeSessionId);

      renderChatTurn({
        role: "assistant",
        content: `📁 **${file.name}** uploaded successfully. Tell me what changes or slide outcomes you'd like to achieve!`,
      });
    } catch (e) {
      console.warn("Session creation error:", e);
      if (chatStatusText) chatStatusText.textContent = "Session Error";
    }
  }

  /* ==========================================================================
     Selection Context Binding (ADS-002)
     ========================================================================== */
  function updateChatSelectionContext(ctx) {
    chatSelectionContext = { ...chatSelectionContext, ...ctx };

    if (!chatContextBadge || !chatContextLabel) return;

    if (chatSelectionContext.selected_text) {
      chatContextLabel.textContent = `Slide ${chatSelectionContext.slide_index || 1} (${chatSelectionContext.selected_text})`;
      chatContextBadge.style.display = "inline-flex";
    } else if (chatSelectionContext.slide_index) {
      chatContextLabel.textContent = `Slide ${chatSelectionContext.slide_index}`;
      chatContextBadge.style.display = "inline-flex";
    } else {
      chatContextBadge.style.display = "none";
    }
  }

  function clearChatSelectionContext() {
    chatSelectionContext = {
      slide_index: null,
      object_ref: null,
      selected_text: null,
    };
    scopeState.region = null;
    if (selectionRect) selectionRect.style.display = "none";
    if (regionBadge) regionBadge.style.display = "none";
    if (chatContextBadge) chatContextBadge.style.display = "none";
  }

  /* ==========================================================================
     Chatbot Rail Message Handling & Card Rendering (ADS-002)
     ========================================================================== */
  async function sendChatMessage(messageText, customContext = null) {
    if (!messageText || isChatBusy) return;

    if (!activeSessionId) {
      if (selectedFile) {
        await createSessionForFile(selectedFile);
      } else {
        renderChatTurn({
          role: "assistant",
          content: "⚠️ Please select or upload a .pptx presentation template first so I know which deck to edit.",
        });
        return;
      }
    }

    const payloadContext = customContext || (chatSelectionContext.slide_index ? {
      slide_index: chatSelectionContext.slide_index,
      object_ref: chatSelectionContext.object_ref || null,
      selected_text: chatSelectionContext.selected_text || null,
    } : null);

    // 1. Render User Turn
    renderChatTurn({
      role: "user",
      content: messageText,
      context: payloadContext,
    });

    if (chatInput) chatInput.value = "";
    isChatBusy = true;
    if (btnSendChat) btnSendChat.disabled = true;
    if (chatStatusText) chatStatusText.textContent = "Thinking...";

    // 2. Render Temporary Loading Turn
    const loadingTurnEl = renderLoadingTurn();

    const isLegacyHeuristic = /make the slide presentation look better/i.test(messageText);
    const hasActiveQuestionCard = document.querySelector(".card-question") !== null;

    if (chatMode === "plan" || isLegacyHeuristic || hasActiveQuestionCard) {
      // Heuristic multi-turn clarification & plan approval flow (ADS-002 compatibility)
      try {
        const res = await fetch(`/api/v1/sessions/${activeSessionId}/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: messageText,
            selection_context: payloadContext,
          }),
        });

        if (loadingTurnEl && loadingTurnEl.parentNode) {
          loadingTurnEl.parentNode.removeChild(loadingTurnEl);
        }

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Error communicating with Agent backend");
        }

        const respData = await res.json();
        if (respData.session && respData.session.state) {
          updateStepper(respData.session.state);
        }

        // 3. Render Assistant Response & Cards
        renderChatTurn({
          role: "assistant",
          content: respData.assistant_message,
          cards: respData.cards || [],
        });
      } catch (e) {
        if (loadingTurnEl && loadingTurnEl.parentNode) {
          loadingTurnEl.parentNode.removeChild(loadingTurnEl);
        }

        renderChatTurn({
          role: "assistant",
          content: "I ran into an issue while processing your request.",
          cards: [{ type: "error", message: e.message }],
        });
      } finally {
        isChatBusy = false;
        if (btnSendChat) btnSendChat.disabled = false;
        if (chatStatusText) chatStatusText.textContent = "Ready";
        if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    } else {
      // Real Local Agent Engine chat endpoint (ADS-003)
      try {
        const res = await fetch(`/api/v1/sessions/${activeSessionId}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: messageText,
            selection_context: payloadContext,
          }),
        });

        if (loadingTurnEl && loadingTurnEl.parentNode) {
          loadingTurnEl.parentNode.removeChild(loadingTurnEl);
        }

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Error communicating with Real Agent backend");
        }

        const respData = await res.json();
        if (respData.state) {
          updateStepper(respData.state);
        }

        // Render Assistant message and Tool Calling Cards
        renderChatTurn({
          role: "assistant",
          content: respData.assistant_message,
          tool_calls: respData.tool_calls || [],
        });

        // Trigger deck sync if any slide was modified
        if (respData.modified_slide_indices && respData.modified_slide_indices.length > 0) {
          appendTimelineEvent("AGENT_MUTATION", `Tool executed. Modified slide(s): ${respData.modified_slide_indices.join(", ")}`);
          await loadSessionDeck(activeSessionId);
        }
      } catch (e) {
        if (loadingTurnEl && loadingTurnEl.parentNode) {
          loadingTurnEl.parentNode.removeChild(loadingTurnEl);
        }

        renderChatTurn({
          role: "assistant",
          content: "I ran into an issue while communicating with the Agent Engine.",
          cards: [{ type: "error", message: e.message }],
        });
      } finally {
        isChatBusy = false;
        if (btnSendChat) btnSendChat.disabled = false;
        if (chatStatusText) chatStatusText.textContent = "Ready";
        if (chatMessages) chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    }
  }

  function renderLoadingTurn() {
    if (!chatMessages) return null;
    const turnEl = document.createElement("div");
    turnEl.className = "chat-turn turn-assistant";
    turnEl.innerHTML = `
      <div class="turn-avatar">🤖</div>
      <div class="turn-bubble">
        <div class="turn-loading-indicator">
          <span class="spinner" style="width:12px;height:12px;"></span> Agent is reasoning...
        </div>
      </div>
    `;
    chatMessages.appendChild(turnEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return turnEl;
  }

  function renderChatTurn(turn) {
    if (!chatMessages) return;

    const turnEl = document.createElement("div");
    turnEl.className = `chat-turn turn-${turn.role || "assistant"}`;

    if (turn.role === "user") {
      let contextHtml = "";
      if (turn.context && turn.context.selected_text) {
        contextHtml = `<div class="user-context-pill">🎯 ${turn.context.selected_text}</div>`;
      } else if (turn.context && turn.context.slide_index) {
        const msg = (turn.content || "").toLowerCase().trim();
        const isGeneralChat = ["hi", "hello", "chào", "bạn là ai", "who are you", "giúp", "help", "hướng dẫn"].some(g => msg.startsWith(g) || msg === g);
        if (!isGeneralChat) {
          contextHtml = `<div class="user-context-pill">🎯 Slide ${turn.context.slide_index}</div>`;
        }
      }

      turnEl.innerHTML = `
        <div class="turn-bubble">
          ${contextHtml}
          <div class="turn-text">${escapeHtml(turn.content)}</div>
        </div>
      `;
    } else {
      const bubbleEl = document.createElement("div");
      bubbleEl.className = "turn-bubble";

      const textEl = document.createElement("div");
      textEl.className = "turn-text";
      textEl.innerHTML = formatMarkdownText(turn.content || "");
      bubbleEl.appendChild(textEl);

      // Render tool_calls attached to this turn (Real Agent Engine ADS-003)
      if (turn.tool_calls && Array.isArray(turn.tool_calls)) {
        turn.tool_calls.forEach((tc) => {
          const callCard = renderToolCallingCard(tc);
          if (callCard) bubbleEl.appendChild(callCard);
          const resultCard = renderToolResultCard(tc);
          if (resultCard) bubbleEl.appendChild(resultCard);
        });
      }

      // Render Cards attached to this turn
      if (turn.cards && Array.isArray(turn.cards)) {
        turn.cards.forEach((c) => {
          let cardNode = null;
          const cardType = (c.type || "").toLowerCase();
          if (cardType === "question") {
            cardNode = renderQuestionCard(c);
          } else if (cardType === "plan") {
            cardNode = renderPlanCard(c);
          } else if (cardType === "source" || cardType === "sources") {
            cardNode = renderSourceCard(c);
          } else if (cardType === "execution") {
            cardNode = renderExecutionCard(c);
          } else if (cardType === "review") {
            cardNode = renderReviewCard(c);
          } else if (cardType === "tool_call" || cardType === "tool-call" || cardType === "tool") {
            cardNode = renderToolCallingCard(c);
          } else if (cardType === "tool_result" || cardType === "tool-result") {
            cardNode = renderToolResultCard(c);
          } else if (cardType === "error") {
            cardNode = renderErrorCard(c.message || c.detail || "An error occurred", () => {
              if (chatInput) sendChatMessage(chatInput.value.trim());
            });
          }

          if (cardNode) {
            bubbleEl.appendChild(cardNode);
          }
        });
      }

      turnEl.innerHTML = `<div class="turn-avatar">🤖</div>`;
      turnEl.appendChild(bubbleEl);
    }

    chatMessages.appendChild(turnEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  /* --------------------------------------------------------------------------
     Card Renderers (QuestionCard, PlanCard, SourceCard, ExecutionCard, ReviewCard, ErrorCard)
     -------------------------------------------------------------------------- */
  function renderQuestionCard(cardData) {
    const card = document.createElement("div");
    card.className = "chat-card card-question";

    const questions = cardData.questions || [];
    let questionsHtml = "";

    questions.forEach((q) => {
      let optionsHtml = "";
      if (q.options && Array.isArray(q.options) && q.options.length > 0) {
        optionsHtml = `
          <div class="question-options-list">
            ${q.options
              .map(
                (opt) => `
              <button type="button" class="question-option-btn" data-choice="${escapeHtml(opt)}">
                👉 ${escapeHtml(opt)}
              </button>
            `
              )
              .join("")}
          </div>
        `;
      }

      questionsHtml += `
        <div class="question-item">
          <div class="card-title">❓ ${escapeHtml(q.text || q.question || "Clarification needed:")}</div>
          ${optionsHtml}
        </div>
      `;
    });

    card.innerHTML = `
      <div class="card-header-row">
        <span class="card-badge">Clarification</span>
      </div>
      ${questionsHtml}
    `;

    // Wire choice buttons to send answer automatically
    card.querySelectorAll(".question-option-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const choiceText = btn.getAttribute("data-choice");
        if (choiceText) {
          sendChatMessage(choiceText);
        }
      });
    });

    return card;
  }

  function renderPlanCard(cardData) {
    const card = document.createElement("div");
    card.className = "chat-card card-plan";

    const ops = cardData.operations || [];
    const opsHtml = ops
      .map(
        (op) => `
      <div class="plan-op-item">
        <span class="plan-op-type">${escapeHtml(op.op_type || op.type || "EDIT")}</span>
        <span>Slide ${op.target_slide_index || op.slide_index || 1} • ${escapeHtml(op.description || op.rationale || "Modify element")}</span>
      </div>
    `
      )
      .join("");

    card.innerHTML = `
      <div class="card-header-row">
        <span class="card-badge">Plan Proposal</span>
        <span style="font-size:0.7rem;color:var(--text-muted)">Confidence: ${cardData.confidence ? Math.round(cardData.confidence * 100) + "%" : "High"}</span>
      </div>
      <div class="plan-summary-box">
        <strong>Goal:</strong> ${escapeHtml(cardData.summary || cardData.goal || "Execute proposed slide modifications")}
      </div>
      <div class="plan-ops-list">
        ${opsHtml || '<div style="color:var(--text-muted);font-size:0.75rem;">1 operation scheduled.</div>'}
      </div>
      <div class="plan-actions-row">
        <button type="button" class="btn-approve-plan" id="btnPlanApprove">✓ Approve & Execute</button>
        <button type="button" class="btn-revise-plan" id="btnPlanRevise">✏ Revise</button>
      </div>
    `;

    const btnApproveEl = card.querySelector("#btnPlanApprove");
    const btnReviseEl = card.querySelector("#btnPlanRevise");

    if (btnApproveEl) {
      btnApproveEl.addEventListener("click", () => {
        btnApproveEl.disabled = true;
        if (btnReviseEl) btnReviseEl.disabled = true;
        approvePlan(activeSessionId, true);
      });
    }

    if (btnReviseEl) {
      btnReviseEl.addEventListener("click", () => {
        if (chatInput) {
          chatInput.value = "Please revise the plan: ";
          chatInput.focus();
        }
      });
    }

    return card;
  }

  function renderSourceCard(cardData) {
    const card = document.createElement("div");
    card.className = "chat-card card-source";

    const sources = cardData.sources || [];
    const sourcesHtml = sources
      .map(
        (s) => `
      <div class="source-item">
        <a href="${escapeHtml(s.url || "#")}" target="_blank" rel="noopener" class="source-title-link">
          🔗 ${escapeHtml(s.title || s.url || "Web Source")}
        </a>
        <div class="source-summary">${escapeHtml(s.summary || (s.claims ? s.claims.join("; ") : "Verified reference"))}</div>
      </div>
    `
      )
      .join("");

    card.innerHTML = `
      <div class="card-header-row">
        <span class="card-badge">Web Research Provenance</span>
        <span style="font-size:0.7rem;color:var(--text-muted)">${sources.length} sources found</span>
      </div>
      <div class="sources-list" style="display:flex;flex-direction:column;gap:0.35rem;">
        ${sourcesHtml}
      </div>
      <div class="source-actions-row">
        <button type="button" class="btn-approve-sources" id="btnSourceApprove">✓ Approve Sources</button>
        <button type="button" class="btn-reject-sources" id="btnSourceReject">✕ Reject Sources</button>
      </div>
    `;

    const btnApproveEl = card.querySelector("#btnSourceApprove");
    const btnRejectEl = card.querySelector("#btnSourceReject");

    if (btnApproveEl) {
      btnApproveEl.addEventListener("click", () => {
        btnApproveEl.disabled = true;
        if (btnRejectEl) btnRejectEl.disabled = true;
        approveSources(activeSessionId, true);
      });
    }

    if (btnRejectEl) {
      btnRejectEl.addEventListener("click", () => {
        btnApproveEl.disabled = true;
        if (btnRejectEl) btnRejectEl.disabled = true;
        approveSources(activeSessionId, false);
      });
    }

    return card;
  }

  function renderExecutionCard(cardData) {
    const card = document.createElement("div");
    card.className = "chat-card card-execution";
    card.innerHTML = `
      <div class="card-header-row">
        <span class="card-badge">Execution</span>
      </div>
      <div class="execution-progress-row">
        <span class="spinner" style="width:14px;height:14px;"></span>
        <span>${escapeHtml(cardData.message || "Mutating presentation & verifying quality gates...")}</span>
      </div>
    `;
    return card;
  }

  function renderReviewCard(cardData) {
    const card = document.createElement("div");
    card.className = "chat-card card-review";

    const jobId = cardData.job_id || currentJobId;
    const downloadUrl = jobId ? `/api/v1/jobs/${jobId}/artifacts/presentation.pptx` : "#";

    card.innerHTML = `
      <div class="card-header-row">
        <span class="card-badge">Review & Download</span>
        <span style="color:var(--success);font-weight:600;font-size:0.75rem;">✓ Verified</span>
      </div>
      <div class="review-diff-summary">
        Slide modifications compiled cleanly. You can inspect the side-by-side diff on the canvas, download your PPTX, or ask follow-up questions below.
      </div>
      <div class="review-actions-row">
        <a href="${downloadUrl}" class="btn-chat-download" download>
          <span>📥 Download PPTX</span>
        </a>
      </div>
    `;
    return card;
  }

  function renderErrorCard(errorText, retryCallback) {
    const card = document.createElement("div");
    card.className = "chat-card card-error";
    card.innerHTML = `
      <div class="card-header-row">
        <span class="card-badge">Error</span>
      </div>
      <div class="error-details-text">${escapeHtml(errorText || "An unexpected error occurred.")}</div>
      ${retryCallback ? '<button type="button" class="btn-retry-chat">🔄 Retry Request</button>' : ""}
    `;

    if (retryCallback) {
      const btnRetry = card.querySelector(".btn-retry-chat");
      if (btnRetry) {
        btnRetry.addEventListener("click", () => retryCallback());
      }
    }
    return card;
  }

  /* --------------------------------------------------------------------------
     Tool Calling Cards & Dual-Column Deck Synchronization (ADS-003)
     -------------------------------------------------------------------------- */
  function renderToolCallingCard(toolCall) {
    if (!toolCall) return null;
    const card = document.createElement("div");
    card.className = "tool-calling-card card-tool-call";
    const toolName = toolCall.tool_name || "Agent Tool";
    const status = toolCall.status || (toolCall.success ? "completed" : (toolCall.error ? "error" : "executing"));
    const badgeClass = status === "completed" ? "tool-badge-success" : (status === "error" ? "tool-badge-error" : "tool-badge-executing");
    const badgeText = status === "completed" ? "COMPLETED" : (status === "error" ? "FAILED" : "RUNNING");

    let argsStr = "";
    if (toolCall.arguments) {
      argsStr = typeof toolCall.arguments === "object" ? JSON.stringify(toolCall.arguments, null, 2) : String(toolCall.arguments);
    }

    card.innerHTML = `
      <div class="tool-card-header">
        <div class="tool-card-title">
          <span>⚡</span>
          <span>${escapeHtml(toolName)}</span>
        </div>
        <span class="tool-card-badge ${badgeClass}">${badgeText}</span>
      </div>
      ${argsStr ? `<div class="tool-card-args">${escapeHtml(argsStr)}</div>` : ""}
    `;
    return card;
  }

  function renderToolResultCard(toolCall) {
    if (!toolCall || (!toolCall.result && !toolCall.modified_slide_indices && !toolCall.error)) return null;
    const card = document.createElement("div");
    card.className = "tool-result-card";

    let modifiedTag = "";
    if (toolCall.modified_slide_indices && toolCall.modified_slide_indices.length > 0) {
      modifiedTag = `<div class="modified-slides-tag">✨ Slide ${toolCall.modified_slide_indices.join(", ")} Modified</div>`;
    }

    const resultSummary = toolCall.result ? (typeof toolCall.result === "string" ? toolCall.result : JSON.stringify(toolCall.result)) : (toolCall.error || "Execution completed");

    card.innerHTML = `
      <div class="tool-result-summary">
        <span>${toolCall.error ? "⚠️" : "✅"}</span>
        <span>${escapeHtml(resultSummary)}</span>
      </div>
      ${modifiedTag}
    `;
    return card;
  }

  async function loadSessionDeck(sessionId) {
    if (!sessionId) return;
    try {
      const res = await fetch(`/api/v1/sessions/${sessionId}/deck`);
      if (!res.ok) {
        console.warn("Failed to fetch deck state:", res.status);
        return;
      }
      const deckData = await res.json();
      currentDeckState = deckData;
      renderDualColumnDeck(deckData);
    } catch (e) {
      console.warn("Error loading session deck:", e);
    }
  }

  function renderDualColumnDeck(deckData) {
    if (!deckData || !deckData.slides) return;

    if (beforePlaceholder) beforePlaceholder.style.display = "none";
    if (afterPlaceholder) afterPlaceholder.style.display = "none";
    if (beforeIngestState) beforeIngestState.style.display = "none";

    const countText = `${deckData.slide_count} Slides`;
    if (beforeDeckCountBadge) beforeDeckCountBadge.textContent = countText;
    if (afterDeckCountBadge) afterDeckCountBadge.textContent = countText;
    if (filmstripCount) filmstripCount.textContent = countText;

    const hasModifications = deckData.modified_slide_indices && deckData.modified_slide_indices.length > 0;
    if (afterStatusLabel) {
      afterStatusLabel.textContent = hasModifications ? `Modified (${deckData.modified_slide_indices.length} slides)` : "In Sync (Before == After)";
    }

    // Render Before Deck List (Original Deck)
    if (beforeDeckList) {
      beforeDeckList.innerHTML = "";
      deckData.slides.forEach((s) => {
        const card = document.createElement("div");
        card.className = `deck-slide-card ${s.index === activeSlideIndex ? "active-slide-card" : ""}`;
        card.dataset.slideIndex = String(s.index);

        card.innerHTML = `
          <div class="deck-slide-card-header">
            <span>Slide ${s.index}</span>
            <span>${escapeHtml(s.title || "")}</span>
          </div>
          <div class="deck-slide-card-thumb">
            ${s.before_url ? `<img src="${s.before_url}" alt="Slide ${s.index} (Before)">` : `<span>S${s.index}</span>`}
          </div>
        `;

        card.addEventListener("click", () => selectSlide(s.index));
        beforeDeckList.appendChild(card);
      });
    }

    // Render After Deck List (Modified Deck with Visual Change Highlights)
    if (afterDeckList) {
      afterDeckList.innerHTML = "";
      deckData.slides.forEach((s) => {
        const card = document.createElement("div");
        const isModified = s.modified || (deckData.modified_slide_indices && deckData.modified_slide_indices.includes(s.index));
        card.className = `deck-slide-card ${isModified ? "slide-modified-glow" : ""} ${s.index === activeSlideIndex ? "active-slide-card" : ""}`;
        card.dataset.slideIndex = String(s.index);

        card.innerHTML = `
          <div class="deck-slide-card-header">
            <span>Slide ${s.index}</span>
            ${isModified ? '<span class="modified-badge">MODIFIED</span>' : '<span>In Sync</span>'}
          </div>
          <div class="deck-slide-card-thumb">
            ${s.after_url ? `<img src="${s.after_url}${isModified ? '?t=' + Date.now() : ''}" alt="Slide ${s.index} (After)">` : `<span>S${s.index}</span>`}
          </div>
        `;

        card.addEventListener("click", () => selectSlide(s.index));
        afterDeckList.appendChild(card);
      });
    }

    // Populate or sync slide dropdown
    populateSlideSelector(deckData.slide_count);

    // Build or update Filmstrip
    buildFilmstripFromDeck(deckData);

    // Update active slide single frame for compatibility
    const curSlide = deckData.slides.find((s) => s.index === activeSlideIndex) || deckData.slides[0];
    if (curSlide) {
      if (curSlide.before_url) loadPreviewImage("before", curSlide.before_url);
      if (curSlide.after_url) loadPreviewImage("after", curSlide.after_url);
      if (diffBadge) {
        diffBadge.style.display = curSlide.modified ? "inline-block" : "none";
      }
    }
  }

  function buildFilmstripFromDeck(deckData) {
    if (!filmstripTrack) return;
    filmstripTrack.innerHTML = "";

    deckData.slides.forEach((s) => {
      const isModified = s.modified || (deckData.modified_slide_indices && deckData.modified_slide_indices.includes(s.index));
      const item = document.createElement("div");
      item.className = `filmstrip-item ${s.index === activeSlideIndex ? "active" : ""}`;
      item.setAttribute("role", "tab");
      item.setAttribute("aria-selected", s.index === activeSlideIndex ? "true" : "false");

      const thumb = document.createElement("div");
      thumb.className = "filmstrip-thumb-preview";
      const imgUrl = s.after_url || s.before_url;
      if (imgUrl) {
        const img = document.createElement("img");
        img.src = imgUrl;
        img.alt = `Slide ${s.index}`;
        thumb.appendChild(img);
      } else {
        thumb.textContent = `S${s.index}`;
      }

      const title = document.createElement("span");
      title.className = "filmstrip-item-title";
      title.textContent = `Slide ${s.index}`;

      item.appendChild(thumb);
      item.appendChild(title);

      if (isModified) {
        const tag = document.createElement("span");
        tag.className = "filmstrip-modified-tag";
        tag.textContent = "Modified";
        item.appendChild(tag);
      }

      item.addEventListener("click", () => {
        selectSlide(s.index);
      });

      filmstripTrack.appendChild(item);
    });
  }

  /* --------------------------------------------------------------------------
     Session Approvals & Execution Orchestration (ADS-002)
     -------------------------------------------------------------------------- */
  async function approvePlan(sessionId, isApproved, feedback = null) {
    if (!sessionId) return;

    try {
      const res = await fetch(`/api/v1/sessions/${sessionId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "plan",
          approved: isApproved,
          feedback: feedback,
        }),
      });

      if (!res.ok) throw new Error("Plan approval failed");
      const respData = await res.json();
      updateStepper(respData.state);

      if (isApproved) {
        if (respData.state === "READY_FOR_EXECUTION" || respData.state === "EXECUTING") {
          await executeSession(sessionId);
        } else if (respData.state === "RESEARCHING" || respData.state === "WAITING_SOURCE_APPROVAL") {
          renderChatTurn({
            role: "assistant",
            content: "Searching web sources for presentation data...",
            cards: [{ type: "execution", message: "Web research in progress..." }],
          });
        }
      }
    } catch (e) {
      alert(`Approval error: ${e.message}`);
    }
  }

  async function approveSources(sessionId, isApproved, feedback = null) {
    if (!sessionId) return;

    try {
      const res = await fetch(`/api/v1/sessions/${sessionId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "sources",
          approved: isApproved,
          feedback: feedback,
        }),
      });

      if (!res.ok) throw new Error("Sources approval failed");
      const respData = await res.json();
      updateStepper(respData.state);

      if (isApproved) {
        await executeSession(sessionId);
      }
    } catch (e) {
      alert(`Source approval error: ${e.message}`);
    }
  }

  async function executeSession(sessionId) {
    if (!sessionId) return;

    try {
      renderChatTurn({
        role: "assistant",
        content: "Executing approved slide operations...",
        cards: [{ type: "execution", message: "Planning & executing deterministic PPTX mutations..." }],
      });

      // Show loading on After slide canvas
      if (afterPlaceholder) afterPlaceholder.style.display = "none";
      if (afterError) afterError.style.display = "none";
      if (afterLoading) afterLoading.style.display = "flex";
      if (afterStatusLabel) afterStatusLabel.textContent = "AI Executing...";

      const res = await fetch(`/api/v1/sessions/${sessionId}/execute`, {
        method: "POST",
      });

      if (!res.ok) throw new Error("Execution initiation failed");
      const data = await res.json();
      if (data.job_id) {
        currentJobId = data.job_id;
        startPolling(currentJobId, () => {
          onSessionExecutionCompleted(sessionId, currentJobId);
        });
      }
    } catch (e) {
      renderChatTurn({
        role: "assistant",
        content: "Execution could not be completed.",
        cards: [{ type: "error", message: e.message }],
      });
    }
  }

  function onSessionExecutionCompleted(sessionId, jobId) {
    renderChatTurn({
      role: "assistant",
      content: "✨ Slide deck updated and quality gates verified!",
      cards: [{ type: "review", job_id: jobId }],
    });
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
    updateChatSelectionContext({ slide_index: activeSlideIndex, object_ref: null, selected_text: null });
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
          regionCoordsLabel.textContent = `Region S${activeSlideIndex}: [${(normX * 100).toFixed(0)}%, ${(normY * 100).toFixed(0)}%, ${(normW * 100).toFixed(0)}%, ${(normH * 100).toFixed(0)}%]`;
        }

        // Bind region into Chat selection context
        updateChatSelectionContext({
          slide_index: activeSlideIndex,
          object_ref: null,
          selected_text: `Region [${(normX * 100).toFixed(0)}%, ${(normY * 100).toFixed(0)}%, ${(normW * 100).toFixed(0)}%, ${(normH * 100).toFixed(0)}%]`,
        });
      } else {
        clearRegionSelection();
      }
    });
  }

  /* ==========================================================================
     Submit Job (Command Bar Legacy Fallback)
     ========================================================================== */
  async function submitJob() {
    if (!selectedFile) {
      alert("Please select or drop a .pptx file first.");
      return;
    }

    const instruction = instructionInput ? instructionInput.value.trim() : "";
    if (!instruction) {
      alert("Please enter a natural-language edit instruction.");
      if (instructionInput) instructionInput.focus();
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

  function startPolling(jobId, onCompleteCallback = null) {
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
            if (onCompleteCallback) onCompleteCallback();
          } else if (job.state === "ACCEPTED") {
            clearInterval(pollingInterval);
            showAcceptedState(jobId);
            if (onCompleteCallback) onCompleteCallback();
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

    if (state === "INGESTING" || state === "CREATED" || state === "NEEDS_CLARIFICATION" || state === "READY_FOR_PLAN") activeIdx = 0;
    else if (state === "PLANNING" || state === "WAITING_PLAN_APPROVAL" || state === "RESEARCHING" || state === "WAITING_SOURCE_APPROVAL") activeIdx = 1;
    else if (state === "READY_FOR_EXECUTION" || state === "EXECUTING" || state === "RENDERING") activeIdx = 2;
    else if (state === "VERIFYING" || state === "REPAIRING") activeIdx = 3;
    else if (state === "AWAITING_USER_APPROVAL" || state === "ACCEPTED" || state === "REVIEW" || state === "COMPLETED") activeIdx = 4;

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

    // Bind slide selection into Chat selection context (ADS-002)
    updateChatSelectionContext({ slide_index: activeSlideIndex });

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

    // Update active class in Before & After Deck lists and scroll into view (ADS-003)
    document.querySelectorAll("#beforeDeckList .deck-slide-card").forEach((card) => {
      const isCur = card.dataset.slideIndex === String(activeSlideIndex);
      card.classList.toggle("active-slide-card", isCur);
      if (isCur) card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });

    document.querySelectorAll("#afterDeckList .deck-slide-card").forEach((card) => {
      const isCur = card.dataset.slideIndex === String(activeSlideIndex);
      card.classList.toggle("active-slide-card", isCur);
      if (isCur) card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });

    if (previewDiffData && previewDiffData.slides) {
      renderSlideDiff(activeSlideIndex);
    } else if (currentDeckState && currentDeckState.slides) {
      const curSlide = currentDeckState.slides.find((s) => s.index === activeSlideIndex);
      if (curSlide) {
        if (curSlide.before_url) loadPreviewImage("before", curSlide.before_url);
        if (curSlide.after_url) loadPreviewImage("after", curSlide.after_url);
        if (diffBadge) diffBadge.style.display = curSlide.modified ? "inline-block" : "none";
      }
    }
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
      if (eventCounter) eventCounter.textContent = "0 events";
      return;
    }

    if (eventCounter) eventCounter.textContent = `${events.length} events`;

    events.forEach((ev) => {
      const row = document.createElement("div");
      row.className = "timeline-event-row";

      const timeStr = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : "--:--:--";
      row.innerHTML = `
        <span class="timeline-time">${timeStr}</span>
        <span class="timeline-badge">${ev.stage || ev.type || "EVENT"}</span>
        <span class="timeline-desc">${formatEventMessage(ev)}</span>
      `;
      eventLogs.appendChild(row);
    });

    eventLogs.scrollTop = eventLogs.scrollHeight;
  }

  function appendTimelineEvent(stage, message) {
    if (!eventLogs) return;
    if (timelineEmpty && timelineEmpty.parentNode) {
      timelineEmpty.parentNode.removeChild(timelineEmpty);
    }

    const row = document.createElement("div");
    row.className = "timeline-event-row";
    const timeStr = new Date().toLocaleTimeString();
    row.innerHTML = `
      <span class="timeline-time">${timeStr}</span>
      <span class="timeline-badge">${stage}</span>
      <span class="timeline-desc">${message}</span>
    `;
    eventLogs.appendChild(row);
    eventLogs.scrollTop = eventLogs.scrollHeight;
  }

  function formatEventMessage(ev) {
    if (typeof ev.payload === "string") return ev.payload;
    if (ev.payload && ev.payload.message) return ev.payload.message;
    if (ev.payload && ev.payload.instruction) return `Instruction: "${ev.payload.instruction}"`;
    return JSON.stringify(ev.payload || {});
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
     Robust Image Loading with Fallbacks & Retries
     ========================================================================== */
  function loadPreviewImage(type, url, isManualRetry = false) {
    const isBefore = type === "before";
    const imgEl = isBefore ? beforeImg : afterImg;
    const placeholderEl = isBefore ? beforePlaceholder : afterPlaceholder;
    const ingestStateEl = isBefore ? beforeIngestState : null;
    const loadingEl = isBefore ? beforeLoading : afterLoading;
    const errorEl = isBefore ? beforeError : afterError;
    const errorMsgEl = isBefore ? beforeErrorMsg : afterErrorMsg;

    if (isBefore) currentBeforeUrl = url;
    else currentAfterUrl = url;

    if (isManualRetry) {
      if (isBefore) beforeRetryCount = 0;
      else afterRetryCount = 0;
    }

    if (placeholderEl) placeholderEl.style.display = "none";
    if (ingestStateEl) ingestStateEl.style.display = "none";
    if (errorEl) errorEl.style.display = "none";
    if (loadingEl) loadingEl.style.display = "flex";
    if (imgEl) imgEl.style.display = "none";

    const testImg = new Image();
    testImg.onload = () => {
      if (loadingEl) loadingEl.style.display = "none";
      if (errorEl) errorEl.style.display = "none";
      if (imgEl) {
        imgEl.src = url;
        imgEl.style.display = "block";
        imgEl.style.zIndex = "5";
      }
      if (isBefore) beforeRetryCount = 0;
      else afterRetryCount = 0;
    };

    testImg.onerror = () => {
      const retryCount = isBefore ? ++beforeRetryCount : ++afterRetryCount;
      if (retryCount <= MAX_IMAGE_RETRIES) {
        setTimeout(() => {
          loadPreviewImage(type, url);
        }, 1000 * retryCount);
      } else {
        if (loadingEl) loadingEl.style.display = "none";
        if (errorEl) errorEl.style.display = "flex";
        if (errorMsgEl) {
          errorMsgEl.textContent = `Could not load slide preview after ${MAX_IMAGE_RETRIES} attempts.`;
        }
      }
    };

    testImg.src = url;
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

  /* ==========================================================================
     Utilities
     ========================================================================== */
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatMarkdownText(str) {
    if (!str) return "";
    let safe = escapeHtml(str);
    // bold
    safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // italic
    safe = safe.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    // linebreaks
    safe = safe.replace(/\n/g, "<br>");
    return safe;
  }
})();
