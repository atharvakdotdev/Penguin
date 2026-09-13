// Shared Penguin frontend script
const pageType = document.body?.dataset?.page || "";
const isChatPage = pageType === "chat";
const isSettingsPage = pageType === "settings";
const sidebar = document.querySelector(".sidebar");
const sidebarToggle = document.getElementById("sidebarToggle");
const knowledgeBaseModal = document.getElementById("knowledgeBaseModal");
function toggleSidebar() {
  if (!sidebar) return;
  const isCollapsed = sidebar.classList.toggle("is-collapsed");
  if (sidebarToggle) {
    sidebarToggle.classList.toggle("is-closed", isCollapsed);
    sidebarToggle.setAttribute("aria-label", isCollapsed ? "Open sidebar" : "Collapse sidebar");
  }
}
function openKnowledgeBaseDialog() {
  if (!knowledgeBaseModal) return;
  knowledgeBaseModal.classList.remove("hidden");
  knowledgeBaseModal.setAttribute("aria-hidden", "false");
}
function closeKnowledgeBaseDialog() {
  if (!knowledgeBaseModal) return;
  knowledgeBaseModal.classList.add("hidden");
  knowledgeBaseModal.setAttribute("aria-hidden", "true");
}
function attachKnowledgeBaseDialogHandlers() {
  document.querySelectorAll('[data-role="knowledge-base-nav"]').forEach((navItem) => {
    navItem.addEventListener('click', (event) => {
      event.preventDefault();
      openKnowledgeBaseDialog();
    });

    navItem.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openKnowledgeBaseDialog();
      }
    });
  });

  const closeButton = document.getElementById('knowledgeBaseCloseButton');
  if (closeButton) {
    closeButton.addEventListener('click', closeKnowledgeBaseDialog);
  }

  if (knowledgeBaseModal) {
    knowledgeBaseModal.addEventListener('click', (event) => {
      if (event.target === knowledgeBaseModal) {
        closeKnowledgeBaseDialog();
      }
    });
  }

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeKnowledgeBaseDialog();
    }
  });
}

function navigateToPage(pageName, apiMethodName) {
  const targetUrl = new URL(pageName, window.location.href).href;
  window.location.assign(targetUrl);
}

attachKnowledgeBaseDialogHandlers();
if (isChatPage) {
  (function () {
    const chatInput = document.getElementById('chatInput');
    const chatMessages = document.getElementById('chatMessages');
    const sendButton = document.getElementById('sendButton');

    const attachLogButton = document.getElementById('attachLogButton');
    const logFileInput = document.getElementById('logFileInput');
    const attachmentStatus = document.getElementById('attachmentStatus');
    const attachmentLabel = document.getElementById('attachmentLabel');
    const attachmentClear = document.getElementById('attachmentClear');
    const stopAgentButton = document.getElementById('stopAgentButton');
    const terminalWindow = document.querySelector('.terminal-window');
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const rightPanel = document.querySelector('.right-panel');
    const rightPanelResizer = document.getElementById('rightPanelResizer');
    const modelSelect = document.getElementById('modelSelect');
    const newSessionButton = document.getElementById('newSessionButton');
    const sessionsButton = document.querySelector('[data-role="sessions-toggle"]');
    const closeSessionsButton = document.getElementById('closeSessionsButton');
    const sessionList = document.getElementById('sessionList');
    const sessionTitle = document.querySelector('[data-session-title]');
    const planSteps = Array.from(document.querySelectorAll('.plan-item'));
    const settingsNav = document.querySelector('[data-role="settings-nav"]');

    let currentCommand = null;
    let currentInvestigation = null;
    let awaitingNextStep = false;
    let pendingContextPrompt = null;
    let sessionsOpen = false;
    let autoAllowEnabled = false;
    let activeSessionId = null;
    let isReplayingHistory = false;
    let chat_history = [];
    const displayedTerminalOutputs = new Set();
    window.chat_history = chat_history;

    function formatTime() {
      return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function formatRelativeTime(dateValue) {
      if (!dateValue) return '';
      const date = new Date(dateValue);
      if (isNaN(date.getTime())) return String(dateValue);

      const now = new Date();
      const diffMs = now - date;
      const diffSec = Math.floor(diffMs / 1000);
      const diffMin = Math.floor(diffSec / 60);
      const diffHours = Math.floor(diffMin / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffSec < 60) return 'Just now';
      if (diffMin < 60) return `${diffMin}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays}d ago`;

      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    }

    function setSessionTitle(title) {
      if (sessionTitle) {
        sessionTitle.textContent = title || 'Live Session';
      }
    }

    function updateAutoAllowUI(enabled) {
      autoAllowEnabled = Boolean(enabled);
    }

    document.addEventListener('click', () => {
      document.querySelectorAll('.split-dropdown-menu:not(.hidden)').forEach((menu) => {
        menu.classList.add('hidden');
      });
    });

    function clearChatView() {
      chatMessages.innerHTML = '';
      chat_history = [];
      window.chat_history = chat_history;
      currentCommand = null;
      currentInvestigation = null;
      awaitingNextStep = false;
      pendingContextPrompt = null;
      renderHypotheses([]);
      renderPlanState(null);
    }

    function clearTerminalView() {
      terminalWindow.innerHTML = '';
      displayedTerminalOutputs.clear();
    }




    function renderTerminalHistory() {
      clearTerminalView();
      const executedCommands = Array.isArray(window.investigating_obj?.executed_commands)
        ? window.investigating_obj.executed_commands
        : [];

      executedCommands.forEach((entry) => {
        if (!entry || typeof entry.command !== 'string') {
          return;
        }
        const historyKey = `history:${entry.timestamp || Date.now()}:${entry.command}:${entry.output || ''}:${entry.success === false}`;
        addTerminalOutput(entry.command, entry.output || '', entry.success === false, historyKey);
      });
    }

    function replayChatHistory(history) {
      const safeHistory = Array.isArray(history) ? history : [];
      if (!safeHistory.length) {
        return;
      }

      safeHistory.forEach((entry) => {
        if (!entry || typeof entry !== 'object') {
          return;
        }

        let event = entry;
        if (!event.type && typeof entry.content === 'string') {
          try {
            const parsed = JSON.parse(entry.content);
            if (parsed && typeof parsed === 'object' && parsed.type) {
              event = parsed;
            }
          } catch (error) {
            event = null;
          }
        }

        if (
          event &&
          event.type === 'testing_hypothesis' &&
          event.data &&
          Array.isArray(event.data.tests) &&
          event.data.tests.length === 0
        ) {
          return;
        }

        if (event && event.type && typeof window.handleInvestigationEvent === 'function') {
          window.handleInvestigationEvent(event);
        }
      });
    }

    function renderPlanState(decision) {
      const checkSvg = `<svg fill="currentColor" style="margin-left: auto; color: var(--accent-green);" viewBox="0 0 24 24"><circle cx="12" cy="12" opacity="0.2" r="10"></circle><path d="m9 12 2 2 4-4" fill="none" stroke="currentColor" stroke-width="2"></path></svg>`;
      const circleSvg = `<svg fill="none" stroke="currentColor" stroke-width="1" style="margin-left: auto; color: var(--text-dim);" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle></svg>`;

      if (!decision) {
        planSteps.forEach((step) => {
          step.classList.remove('done', 'active');
          const lastSvg = step.querySelector('svg:last-child');
          if (lastSvg) lastSvg.outerHTML = circleSvg;
        });
        return;
      }

      const normalizedDecision = decision.toString().toLowerCase();
      const phaseIndex = {
        understand: 0,
        diagnose: 1,
        solve: 2,
        verify: 4,
        finished: 5,
      }[normalizedDecision] ?? -1;

      planSteps.forEach((step, index) => {
        const lastSvg = step.querySelector('svg:last-child');
        if (phaseIndex !== -1 && index < phaseIndex) {
          step.classList.add('done');
          step.classList.remove('active');
          if (lastSvg) lastSvg.outerHTML = checkSvg;
        } else if (phaseIndex !== -1 && index === phaseIndex) {
          step.classList.remove('done');
          step.classList.add('active');
          if (lastSvg) lastSvg.outerHTML = circleSvg;
        } else {
          step.classList.remove('done', 'active');
          if (lastSvg) lastSvg.outerHTML = circleSvg;
        }
      });
    }

    function getHypothesisIconMarkup(status) {
      const normalizedStatus = String(status || 'untested').trim().toLowerCase();

      if (normalizedStatus === 'testing') {
        return `
          <svg class="status-spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-label="Testing">
            <circle cx="12" cy="12" r="8" stroke="currentColor" stroke-opacity="0.35" fill="none"></circle>
            <path d="M12 4a8 8 0 0 1 8 8"></path>
          </svg>
        `;
      }

      if (normalizedStatus === 'supported') {
        return `
          <svg viewBox="0 0 24 24" fill="currentColor" style="color: var(--accent-green);" aria-label="Supported">
            <circle cx="12" cy="12" opacity="0.2" r="10"></circle>
            <path d="m9 12 2 2 4-4" fill="none" stroke="currentColor" stroke-width="2"></path>
          </svg>
        `;
      }

      if (normalizedStatus === 'rejected') {
        return `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-label="Rejected">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-opacity="0.25" fill="none"></circle>
            <path d="M8.5 8.5 15.5 15.5"></path>
            <path d="M15.5 8.5 8.5 15.5"></path>
          </svg>
        `;
      }

      if (normalizedStatus === 'uncertain') {
        return `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-label="Uncertain">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-opacity="0.25" fill="none"></circle>
            <path d="M9.5 9.5a2.5 2.5 0 1 1 4.2 1.8c-.9.8-1.7 1.2-1.7 2.7"></path>
            <circle cx="12" cy="16.5" r="0.9" fill="currentColor" stroke="none"></circle>
          </svg>
        `;
      }

      return `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" aria-label="Untested">
          <circle cx="12" cy="12" r="10"></circle>
        </svg>
      `;
    }

    function renderHypotheses(hypotheses) {
      const hypothesisList = document.getElementById('hypothesisList');
      if (!hypothesisList) {
        return;
      }

      const list = Array.isArray(hypotheses)
        ? hypotheses
        : (hypotheses && Array.isArray(hypotheses.hypotheses) ? hypotheses.hypotheses : []);

      hypothesisList.innerHTML = '';

      if (!list.length) {
        const emptyRow = document.createElement('div');
        emptyRow.className = 'hypothesis-empty';
        emptyRow.textContent = 'No active hypotheses.';
        hypothesisList.appendChild(emptyRow);
        return;
      }

      list.forEach((entry, index) => {
        const hypothesisText = entry && typeof entry.hypothesis === 'string'
          ? entry.hypothesis
          : (typeof entry === 'string' ? entry : 'Unknown hypothesis');

        const status = entry && typeof entry.status === 'string'
          ? entry.status.toLowerCase()
          : 'untested';

        const item = document.createElement('div');
        item.className = `plan-item${status === 'testing' ? ' active' : ''}${status === 'supported' ? ' done' : ''}`;
        item.dataset.status = status;

        const leftIcon = document.createElement('div');
        leftIcon.innerHTML = `
          <svg fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"></path>
          </svg>
        `;

        const text = document.createElement('span');
        text.className = 'hypothesis-text';
        text.textContent = `${index + 1}. ${hypothesisText}`;
        item.dataset.hypothesis = hypothesisText;

        const statusWrap = document.createElement('div');
        statusWrap.className = 'status-indicator';
        statusWrap.innerHTML = getHypothesisIconMarkup(status);

        item.appendChild(leftIcon.firstElementChild);
        item.appendChild(text);
        item.appendChild(statusWrap);
        hypothesisList.appendChild(item);
      });
    }

    function getDisplayTextFromPayload(payload) {
      if (payload == null) {
        return '';
      }
      if (typeof payload === 'string') {
        return payload;
      }
      if (typeof payload === 'number' || typeof payload === 'boolean') {
        return String(payload);
      }
      if (Array.isArray(payload)) {
        return payload.map((item) => getDisplayTextFromPayload(item)).filter(Boolean).join('\n\n');
      }
      if (typeof payload === 'object') {
        if (typeof payload.problem_statement === 'string') return payload.problem_statement;
        if (typeof payload.summary === 'string') return payload.summary;
        if (typeof payload.issue === 'string') return payload.issue;
        if (typeof payload.message === 'string') return payload.message;
        if (typeof payload.description === 'string') return payload.description;
        if (typeof payload.content === 'string') return payload.content;
        if (typeof payload.text === 'string') return payload.text;
        return JSON.stringify(payload, null, 2);
      }
      return '';
    }

    function renderSessionList() {
      if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.list_sessions !== 'function') {
        return;
      }
      window.pywebview.api.list_sessions().then((sessions) => {
        sessionList.innerHTML = '';
        if (!Array.isArray(sessions) || !sessions.length) {
          const empty = document.createElement('div');
          empty.className = 'session-item';
          empty.style.justifyContent = 'center';
          empty.style.color = 'var(--text-dim)';
          empty.style.fontSize = '0.8rem';
          empty.textContent = 'No saved sessions yet';
          sessionList.appendChild(empty);
          return;
        }
        sessions.forEach((session) => {
          const sessionId = session.session_id ?? session.id;
          const isActive = activeSessionId !== null && String(sessionId) === String(activeSessionId);

          const wrapper = document.createElement('div');
          wrapper.className = `session-item${isActive ? ' active' : ''}`;

          const content = document.createElement('div');
          content.className = 'session-item-content';

          const title = document.createElement('div');
          title.className = 'session-item-title';
          title.textContent = session.title || `Session ${sessionId}`;

          const meta = document.createElement('div');
          meta.className = 'session-item-time';
          const rawTime = session.updated_at || session.modified || session.created_at || session.created;
          meta.textContent = formatRelativeTime(rawTime);

          content.appendChild(title);
          content.appendChild(meta);

          const deleteBtn = document.createElement('button');
          deleteBtn.type = 'button';
          deleteBtn.className = 'session-delete-btn';
          deleteBtn.textContent = 'Delete';
          deleteBtn.addEventListener('click', async (event) => {
            event.stopPropagation();
            try {
              const result = await window.pywebview.api.delete_session(sessionId);
              if (result && result.status === 'deleted') {
                if (String(sessionId) === String(activeSessionId)) {
                  activeSessionId = null;
                }
                renderSessionList();
                addLogOutput(`Deleted session ${sessionId}.`);
              }
            } catch (error) {
              addLogOutput(`Unable to delete session: ${error.message || error}`, true);
            }
          });

          wrapper.addEventListener('click', async () => {
            try {
              const result = await window.pywebview.api.open_session(sessionId);
              if (result && result.status === 'opened') {
                activeSessionId = sessionId;
                const runtimeState = result.runtime_state || {};
                window.investigating_obj = result.investigating_obj || result.investigation || runtimeState.investigation || {};
                setSessionTitle(result.title || 'Loaded Session');
                updateAutoAllowUI(result.auto_allow || runtimeState.auto_allow || false);
                clearChatView();
                clearTerminalView();
                isReplayingHistory = true;
                replayChatHistory(result.chat_history || runtimeState.chat_history || []);
                isReplayingHistory = false;
                renderTerminalHistory();
                sidebar.classList.remove('is-session-mode');
                sessionsOpen = false;
                renderSessionList();
                window.pywebview.api.controller()
              }
            } catch (error) {
              addLogOutput(`Unable to open session: ${error.message || error}`, true);
            }
          });

          wrapper.appendChild(content);
          wrapper.appendChild(deleteBtn);
          sessionList.appendChild(wrapper);
        });
      }).catch((error) => {
        addLogOutput(`Unable to load sessions: ${error.message || error}`, true);
      });
    }

    let modelsLoadInProgress = false;

    async function loadAvailableModels(retries = 40) {
      if (!modelSelect) {
        return;
      }

      if (modelsLoadInProgress) {
        return;
      }

      if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.list_models !== 'function') {
        if (retries > 0) {
          setTimeout(() => loadAvailableModels(retries - 1), 250);
        } else {
          modelSelect.innerHTML = '<option value="">Desktop API unavailable</option>';
          modelSelect.disabled = true;
        }
        return;
      }

      modelsLoadInProgress = true;
      modelSelect.innerHTML = '<option>Loading models...</option>';

      try {
        const models = await window.pywebview.api.list_models();
        const normalizedModels = Array.isArray(models)
          ? models
          : (models && Array.isArray(models.models) ? models.models : []);

        modelSelect.innerHTML = '';
        if (!normalizedModels.length) {
          const option = document.createElement('option');
          option.value = '';
          option.textContent = 'No models found';
          modelSelect.appendChild(option);
          return;
        }

        normalizedModels.forEach((modelName) => {
          const option = document.createElement('option');
          option.value = modelName;
          option.textContent = modelName;
          modelSelect.appendChild(option);
        });

        if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_settings === 'function') {
          const settings = await window.pywebview.api.get_settings();
          if (settings && typeof settings.current_chat_model === 'string' && settings.current_chat_model) {
            modelSelect.value = settings.current_chat_model;
          } else if (settings && typeof settings.default_model === 'string' && settings.default_model) {
            modelSelect.value = settings.default_model;
          }
          if (settings && settings.chat_started) {
            modelSelect.disabled = true;
            modelSelect.classList.add('locked');
          } else {
            modelSelect.disabled = false;
            modelSelect.classList.remove('locked');
          }
          updateAutoAllowUI(Boolean(settings && settings.auto_allow));
        }
      } catch (error) {
        modelSelect.innerHTML = '<option value="">Unable to load models</option>';
        addLogOutput(`Unable to load Ollama models: ${error.message || error}`, true);
      } finally {
        modelsLoadInProgress = false;
      }
    }

    function toggleSidebar() {
      const isCollapsed = sidebar.classList.toggle('is-collapsed');
      if (sidebarToggle) {
        sidebarToggle.classList.toggle('is-closed', isCollapsed);
        sidebarToggle.setAttribute('aria-label', isCollapsed ? 'Open sidebar' : 'Collapse sidebar');
      }
    }

    function startRightPanelResize(event) {
      if (!rightPanel) return;
      event.preventDefault();

      const onMove = (moveEvent) => {
        const width = Math.max(260, Math.min(700, window.innerWidth - moveEvent.clientX));
        rightPanel.style.width = `${width}px`;
        document.documentElement.style.setProperty('--right-panel-width', `${width}px`);
      };

      const onUp = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      };

      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    }

    function toggleSessionsPanel() {
      sessionsOpen = !sessionsOpen;
      sidebar.classList.toggle('is-session-mode', sessionsOpen);
      if (sessionsOpen) {
        renderSessionList();
      }
    }

    function addTerminalOutput(command, output, isError = false, dedupeKey = null) {
      const outputKey = dedupeKey || JSON.stringify([command, output, isError]);
      if (displayedTerminalOutputs.has(outputKey)) {
        return;
      }
      displayedTerminalOutputs.add(outputKey);

      const cmdDiv = document.createElement('div');
      cmdDiv.className = 'terminal-cmd';
      cmdDiv.textContent = `$ ${command}`;
      terminalWindow.appendChild(cmdDiv);

      if (output) {
        const resDiv = document.createElement('div');
        resDiv.className = 'terminal-res';
        if (isError) {
          resDiv.style.color = '#f85149';
        }
        resDiv.textContent = output;
        terminalWindow.appendChild(resDiv);
      }

      const timeDiv = document.createElement('span');
      timeDiv.className = 'terminal-time';
      timeDiv.textContent = formatTime();
      terminalWindow.appendChild(timeDiv);

      terminalWindow.scrollTop = terminalWindow.scrollHeight;
    }

    function addLogOutput(message, isError = false) {
      if (isError) {
        console.error(message);
      } else {
        console.log(message);
      }
    }

    function populateAgentContent(container, response) {
      container.innerHTML = '';
      if (response && typeof response === 'object') {
        if (response.auto_allow !== undefined) {
          updateAutoAllowUI(response.auto_allow);
        }
        if (response.reply) {
          const reply = document.createElement('div');
          reply.className = 'card-body';
          reply.style.whiteSpace = 'pre-wrap';
          reply.textContent = response.reply;
          container.appendChild(reply);
        }


        if (Array.isArray(response.steps) && response.steps.length) {
          const list = document.createElement('div');
          list.className = 'card-list';
          let autoTriggered = false;
          response.steps.forEach((step) => {
            const card = document.createElement('div');
            card.className = step.command ? 'command-step' : 'card';
            const title = document.createElement('div');
            title.className = 'card-header gathering';
            title.textContent = step.title || 'Step';
            const description = document.createElement('div');
            description.className = 'card-body';
            description.textContent = step.description || '';
            if (!step.command) {
              card.appendChild(title);
              card.appendChild(description);
            }

            if (step.command) {
              const commandWrapper = document.createElement('div');
              commandWrapper.className = 'command-container';

              const commandDisplay = document.createElement('div');
              commandDisplay.className = 'command-display';
              commandDisplay.textContent = `$ ${step.command}`;
              commandWrapper.appendChild(commandDisplay);

              const commandAlreadyExecuted = false;

              if (commandAlreadyExecuted) {
                const splitContainer = document.createElement('div');
                splitContainer.className = 'split-btn-container';

                const mainBtn = document.createElement('button');
                mainBtn.className = 'btn-allow-command split-main';
                mainBtn.textContent = '✓ Ran';
                mainBtn.disabled = true;

                const toggleBtn = document.createElement('button');
                toggleBtn.className = 'btn-allow-command split-toggle';
                toggleBtn.setAttribute('title', 'More options');
                toggleBtn.innerHTML = `
                  <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor">
                    <path d="M0 0l5 6 5-6z"/>
                  </svg>`;

                const dropdown = document.createElement('div');
                dropdown.className = 'split-dropdown-menu hidden';

                const optOnce = document.createElement('div');
                optOnce.className = 'dropdown-item';
                optOnce.textContent = 'Allow Once';
                optOnce.addEventListener('click', (e) => {
                  e.stopPropagation();
                  dropdown.classList.add('hidden');
                });

                const optAlways = document.createElement('div');
                optAlways.className = 'dropdown-item primary';
                optAlways.textContent = 'Always Allow in This Chat';
                optAlways.addEventListener('click', async (e) => {
                  e.stopPropagation();
                  dropdown.classList.add('hidden');
                });

                dropdown.appendChild(optOnce);
                dropdown.appendChild(optAlways);

                toggleBtn.addEventListener('click', (e) => {
                  e.stopPropagation();
                  document.querySelectorAll('.split-dropdown-menu').forEach((d) => {
                    if (d !== dropdown) d.classList.add('hidden');
                  });
                  dropdown.classList.toggle('hidden');
                });

                splitContainer.appendChild(mainBtn);
                splitContainer.appendChild(toggleBtn);
                splitContainer.appendChild(dropdown);

                const actionsRow1 = document.createElement('div');
                actionsRow1.className = 'command-actions-row';
                actionsRow1.appendChild(splitContainer);

                const copyBtn1 = document.createElement('button');
                copyBtn1.className = 'copy-command-btn';
                copyBtn1.setAttribute('title', 'Copy command');
                copyBtn1.innerHTML = `<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
                copyBtn1.addEventListener('click', () => {
                  navigator.clipboard.writeText(step.command).then(() => {
                    copyBtn1.innerHTML = `<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`;
                    setTimeout(() => {
                      copyBtn1.innerHTML = `<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
                    }, 1500);
                  });
                });
                actionsRow1.appendChild(copyBtn1);
                commandWrapper.appendChild(actionsRow1);
              } else if (autoAllowEnabled) {
                card.hidden = true;
                if (!autoTriggered) {
                  autoTriggered = true;
                  const virtualBtn = document.createElement('button');
                  virtualBtn.className = 'btn-allow-command';
                  setTimeout(() => {
                    executeCommand(virtualBtn, step.command, step.requires_sudo || false, step.command_id);
                  }, 300);
                }
              } else {
                const splitContainer = document.createElement('div');
                splitContainer.className = 'split-btn-container';

                const mainBtn = document.createElement('button');
                mainBtn.className = 'btn-allow-command split-main';
                mainBtn.textContent = '▶ Allow';
                mainBtn.addEventListener('click', () => {
                  executeCommand(mainBtn, step.command, step.requires_sudo || false, step.command_id);
                });

                const toggleBtn = document.createElement('button');
                toggleBtn.className = 'btn-allow-command split-toggle';
                toggleBtn.setAttribute('title', 'More options');
                toggleBtn.innerHTML = `
                  <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor">
                    <path d="M0 0l5 6 5-6z"/>
                  </svg>`;

                const dropdown = document.createElement('div');
                dropdown.className = 'split-dropdown-menu hidden';

                const optOnce = document.createElement('div');
                optOnce.className = 'dropdown-item';
                optOnce.textContent = 'Allow Once';
                optOnce.addEventListener('click', (e) => {
                  e.stopPropagation();
                  dropdown.classList.add('hidden');
                  executeCommand(mainBtn, step.command, step.requires_sudo || false, step.command_id);
                });

                const optAlways = document.createElement('div');
                optAlways.className = 'dropdown-item primary';
                optAlways.textContent = 'Always Allow in This Chat';
                optAlways.addEventListener('click', async (e) => {
                  e.stopPropagation();
                  dropdown.classList.add('hidden');
                  updateAutoAllowUI(true);
                  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.set_auto_allow === 'function') {
                    try {
                      await window.pywebview.api.set_auto_allow(true);
                      addLogOutput('Auto Allow mode enabled for this chat.');
                    } catch (error) {
                      addLogOutput(`Failed to set Auto Allow mode: ${error.message || error}`, true);
                    }
                  }
                  executeCommand(mainBtn, step.command, step.requires_sudo || false, step.command_id);
                });

                dropdown.appendChild(optOnce);
                dropdown.appendChild(optAlways);

                toggleBtn.addEventListener('click', (e) => {
                  e.stopPropagation();
                  document.querySelectorAll('.split-dropdown-menu').forEach((d) => {
                    if (d !== dropdown) d.classList.add('hidden');
                  });
                  dropdown.classList.toggle('hidden');
                });

                splitContainer.appendChild(mainBtn);
                splitContainer.appendChild(toggleBtn);
                splitContainer.appendChild(dropdown);

                const actionsRow3 = document.createElement('div');
                actionsRow3.className = 'command-actions-row';
                actionsRow3.appendChild(splitContainer);

                const copyBtn3 = document.createElement('button');
                copyBtn3.className = 'copy-command-btn';
                copyBtn3.setAttribute('title', 'Copy command');
                copyBtn3.innerHTML = `<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
                copyBtn3.addEventListener('click', () => {
                  navigator.clipboard.writeText(step.command).then(() => {
                    copyBtn3.innerHTML = `<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`;
                    setTimeout(() => {
                      copyBtn3.innerHTML = `<svg fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
                    }, 1500);
                  });
                });
                actionsRow3.appendChild(copyBtn3);
                commandWrapper.appendChild(actionsRow3);
              }

              card.appendChild(commandWrapper);
            }
            list.appendChild(card);
          });
          container.appendChild(list);
        }
        if (response.error) {
          const errorLine = document.createElement('div');
          errorLine.textContent = `Error: ${response.error}`;
          errorLine.style.color = '#f85149';
          container.appendChild(errorLine);
        }
      } else {
        container.textContent = response || 'No response received.';
      }
    }

    // Helper: return true if any step contains an executable command
    function hasExecutableCommand(steps) {
      if (!Array.isArray(steps)) return false;
      return steps.some((s) => s && s.command);
    }

    // Process a single agent response and auto-continue if `is_continue` is true
    // and there are no executable commands in the returned steps.
    async function processAgentResponse(agentMessage, response) {
      if (!response) return;

      // Expose the latest investigation object for potential use by the page
      if (response.investigation_update && typeof response.investigation_update === 'object') {
        window.investigating_obj = response.investigation_update;
      }

      const agentContent = agentMessage.querySelector('.message-content');
      renderPlanState(response.decision || 'understand');
      populateAgentContent(agentContent, response);

      // If backend asked to continue, and there are no executable commands, call respond()
      let loopCount = 0;
      while (response && response.is_continue) {
        // If any step contains a command, stop auto-continuation to wait for user permission
        if (hasExecutableCommand(response.steps)) {
          break;
        }

        // No investigation update to continue with — stop
        if (!response.investigation_update) break;

        loopCount += 1;
        if (loopCount > 10) break; // safety to avoid infinite loops

        try {
          setBusy(true);
          addLogOutput('Auto-continuation: sending investigation object to agent.');
          const nextPrompt = JSON.stringify(response.investigation_update);
          const nextResponse = await window.pywebview.api.respond(nextPrompt);
          response = nextResponse;

          if (response.investigation_update && typeof response.investigation_update === 'object') {
            window.investigating_obj = response.investigation_update;
          }

          populateAgentContent(agentContent, response);
        } catch (err) {
          addLogOutput(`Auto-continue error: ${err.message || err}`, true);
          break;
        } finally {
          setBusy(false);
        }
      }
    }


    async function executeCommand(button, command, useSudo, commandId) {
      let commandCompleted = false;
      try {
        button.disabled = true;
        const toggleSibling = button.closest('.split-btn-container')?.querySelector('.split-toggle');
        if (toggleSibling) {
          toggleSibling.disabled = true;
        }
        button.textContent = 'Running...';
        currentCommand = command;

        if (!window.pywebview || !window.pywebview.api) {
          throw new Error('The desktop API is not available.');
        }

        const runApiCommand = window.pywebview.api.run_command_flag;
        if (typeof runApiCommand !== 'function') {
          throw new Error('The desktop API is not available.');
        }

        const result = await runApiCommand(commandId || command, useSudo);
        commandCompleted = true;
        if (result && typeof result === 'object') {
          if (result.success) {
            button.style.borderColor = 'var(--accent-green)';
            button.textContent = '✓ Ran';
          } else {
            button.style.borderColor = '#f85149';
            button.textContent = '✗ Failed';
          }
        }

        button.disabled = true;
        if (toggleSibling) {
          toggleSibling.disabled = true;
        }
        awaitingNextStep = true;

        // Proceed to next step which will call respond and handle is_continue
        // setTimeout(() => proceedToNextStep(), 1000);
      } catch (error) {
        addTerminalOutput(command, `Error: ${error.message || error}`, true);
        button.style.borderColor = '#f85149';
        button.textContent = '✗ Error';
        button.disabled = true;
      } finally {
        if (commandCompleted) {
          const commandStep = button.closest('.command-step');
          const investigationDropdown = commandStep?.closest('.investigation-dropdown');
          commandStep?.remove();

          if (investigationDropdown && investigationDropdown.dataset.pendingCommands) {
            const remainingCommands = Number(investigationDropdown.dataset.pendingCommands) - 1;
            investigationDropdown.dataset.pendingCommands = String(Math.max(remainingCommands, 0));
            if (remainingCommands <= 0) {
              investigationDropdown.hidden = true;
            }
          }
        }
      }
    }

    function appendMessage(role, text) {
      if (role === 'agent') {
        const existingAgentBlock = chatMessages.querySelector('.message-block.agent-message:last-of-type');
        if (existingAgentBlock) {
          const content = existingAgentBlock.querySelector('.message-content');
          if (!content) {
            return existingAgentBlock;
          }

          if (typeof text === 'string') {
            const trimmed = text.trim();
            if (trimmed) {
              const existingText = content.textContent ? content.textContent.trim() : '';
              content.textContent = existingText ? `${existingText}\n${trimmed}` : trimmed;
            }
          } else if (text && typeof text === 'object') {
            const payload = text.role === 'assistant' || text.role === 'user'
              ? text.content
              : text;

            if (typeof payload === 'string') {
              const trimmed = payload.trim();
              if (trimmed) {
                const existingText = content.textContent ? content.textContent.trim() : '';
                content.textContent = existingText ? `${existingText}\n${trimmed}` : trimmed;
              }
            } else if (payload && typeof payload === 'object') {
              populateAgentContent(content, payload);
            }
          }

          chatMessages.scrollTop = chatMessages.scrollHeight;
          return existingAgentBlock;
        }
      }

      const wrapper = document.createElement('div');
      wrapper.className = `message-block ${role === 'user' ? 'user-message' : 'agent-message'}`;

      const header = document.createElement('div');
      header.className = 'message-header';

      const label = document.createElement('span');
      label.className = role === 'user' ? 'user-label' : 'agent-label';
      if (role === 'user') {
        label.textContent = 'YOU';
      } else {
        label.innerHTML = `
          <svg fill="none" height="14" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
            stroke-width="2" viewbox="0 0 24 24" width="14" xmlns="http://www.w3.org/2000/svg">
            <path d="m16 18 6-6-6-6"></path>
            <path d="m8 6-6 6 6 6"></path>
            <path d="m14.5 4-5 16"></path>
          </svg>
          LINUX AGENT`;
      }

      const timestamp = document.createElement('span');
      timestamp.className = 'timestamp';
      const timestampValue = text && typeof text === 'object' && (text.timestamp || text.created || text.modified)
        ? text.timestamp || text.created || text.modified
        : null;
      timestamp.textContent = timestampValue ? new Date(timestampValue).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : formatTime();

      header.appendChild(label);
      header.appendChild(timestamp);

      const content = document.createElement('div');
      content.className = 'message-content';

      if (typeof text === 'string') {
        const trimmed = text.trim();
        if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
          try {
            const parsed = JSON.parse(trimmed);
            populateAgentContent(content, parsed);
          } catch (error) {
            content.textContent = text;
          }
        } else {
          content.textContent = text;
        }
      } else if (text && typeof text === 'object') {
        const payload = text.role === 'assistant' || text.role === 'user'
          ? text.content
          : text;

        if (role === 'agent') {
          if (typeof payload === 'string') {
            const trimmed = payload.trim();
            if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
              try {
                const parsed = JSON.parse(trimmed);
                populateAgentContent(content, parsed);
              } catch (error) {
                content.textContent = payload;
              }
            } else {
              content.textContent = payload;
            }
          } else if (payload && typeof payload === 'object') {
            populateAgentContent(content, payload);
          } else {
            content.textContent = '';
          }
        } else if (role === 'user') {
          content.textContent = typeof payload === 'string' ? payload : (payload && payload.content) || '';
        }
      }

      wrapper.appendChild(header);
      wrapper.appendChild(content);
      chatMessages.appendChild(wrapper);
      chatMessages.scrollTop = chatMessages.scrollHeight;
      return wrapper;
    }

    let pendingAttachment = null;

    function updateAttachmentStatus(fileName) {
      if (!attachmentStatus || !attachmentLabel) {
        return;
      }

      if (!fileName) {
        attachmentStatus.classList.remove('is-visible');
        attachmentLabel.textContent = 'No file attached';
        return;
      }

      attachmentStatus.classList.add('is-visible');
      attachmentLabel.textContent = fileName;
    }

    function clearPendingAttachment() {
      pendingAttachment = null;
      if (logFileInput) {
        logFileInput.value = '';
      }
      updateAttachmentStatus(null);
    }

    async function pickLogFile() {
      if (!logFileInput) {
        return;
      }

      logFileInput.click();
    }

    function setBusy(isBusy) {
      chatInput.disabled = isBusy;
      sendButton.disabled = isBusy;
      sendButton.style.opacity = isBusy ? '0.6' : '1';
      sendButton.style.cursor = isBusy ? 'wait' : 'pointer';
      if (attachLogButton) {
        attachLogButton.disabled = isBusy;
        attachLogButton.style.opacity = isBusy ? '0.6' : '1';
      }
      if (stopAgentButton) {
        stopAgentButton.disabled = !isBusy;
        stopAgentButton.style.opacity = isBusy ? '1' : '0.55';
      }
    }

    async function stopAgent() {
      if (!stopAgentButton || stopAgentButton.disabled) {
        return;
      }

      stopAgentButton.disabled = true;
      stopAgentButton.textContent = 'Stopping...';
      try {
        if (!window.pywebview?.api || typeof window.pywebview.api.stop_agent !== 'function') {
          throw new Error('The desktop API is not available.');
        }
        await window.pywebview.api.stop_agent();
        if (currentInvestigation) {
          currentInvestigation.text.textContent = 'Agent stopped. Progress saved.';
          updateInvestigationTitle(currentInvestigation, 'Agent Stopped');
        }
      } catch (error) {
        addLogOutput(`Unable to stop agent: ${error.message || error}`, true);
      } finally {
        setBusy(false);
        stopAgentButton.textContent = '⏹ Stop Agent';
      }
    }

    async function sendMessage() {
      const text = chatInput.value.trim();

      if (!text && !pendingAttachment) {
        return;
      }

      const attachedFileName = pendingAttachment
        ? pendingAttachment.name
        : null;

      const userMessage =
        text || `Attached log: ${attachedFileName || 'selected file'}`;

      // Add user message
      appendMessage('user', userMessage);

      // Create investigation placeholder immediately
      currentInvestigation = createInvestigationPlaceholder(
        'Understanding the problem',
        ''
      );

      chatInput.value = '';
      setBusy(true);

      try {
        if (
          !window.pywebview ||
          !window.pywebview.api ||
          typeof window.pywebview.api.StartInvetigation !== 'function'
        ) {
          throw new Error('The desktop API is not available.');
        }

        await window.pywebview.api.StartInvetigation(
          userMessage,
          attachedFileName || null,
          pendingAttachment ? pendingAttachment.text : null
        );

      } catch (error) {
        investigation.text.textContent =
          `Sorry, the agent could not respond: ${error.message || error}`;

      } finally {
        clearPendingAttachment();
        setBusy(false);
        chatInput.focus();
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    }
    function createInvestigationPlaceholder(title, initialText = "") {
      const message = appendMessage("agent", "");
      const content = message.querySelector(".message-content");

      const details = document.createElement("details");
      details.className = "investigation-dropdown";
      details.open = true;

      const summary = document.createElement("summary");
      summary.textContent = title;

      const text = document.createElement("div");
      text.className = "investigation-content";
      text.textContent = initialText;

      details.append(summary, text);
      content.appendChild(details);

      return {
        message,
        details,
        summary,
        text
      };
    }

    function updateInvestigationTitle(investigation, newTitle) {
      if (!investigation || !investigation.summary) return;
      investigation.summary.textContent = newTitle;
      investigation.summary.classList.add('identified');
    }


    function handleProblemStatement(data) {
      if (!currentInvestigation) {
        currentInvestigation = createInvestigationPlaceholder('Understanding the problem', '');
      }

      const payload = data && typeof data === 'object' && !Array.isArray(data) ? data : { problem_statement: data };
      const problemText = getDisplayTextFromPayload(payload.problem_statement ?? payload.issue ?? payload.summary ?? payload);
      currentInvestigation.text.textContent = problemText || 'Problem statement received.';
      updateInvestigationTitle(currentInvestigation, "Problem Identified");
    }

    function handleHypotheses(data) {
      const hypothesisList = data && Array.isArray(data.hypotheses) ? data.hypotheses : (Array.isArray(data) ? data : (data && typeof data === 'object' ? [data] : []));
      renderHypotheses(hypothesisList);

      if (!currentInvestigation) return;

      currentInvestigation.text.textContent = '';
      updateInvestigationTitle(currentInvestigation, "Hypotheses Generated");
    }


    function handleTestingHypothesis(data) {
      if (!currentInvestigation) return;

      const payload = data && typeof data === 'object' ? data : {};
      if (payload.auto_allow !== undefined) {
        updateAutoAllowUI(payload.auto_allow);
      }

      const hypothesisObject = payload.hypothesis && typeof payload.hypothesis === 'object' ? payload.hypothesis : null;
      const testingHypothesis = hypothesisObject && typeof hypothesisObject.hypothesis === 'string'
        ? hypothesisObject.hypothesis
        : (typeof payload.hypothesis === 'string' ? payload.hypothesis : '');

      document.querySelectorAll('#hypothesisList .plan-item').forEach((item) => {
        const isTesting = Boolean(testingHypothesis) && item.dataset.hypothesis === testingHypothesis;
        item.classList.toggle('active', isTesting);
        const statusIndicator = item.querySelector('.status-indicator');
        if (isTesting) {
          item.dataset.status = 'testing';
          if (statusIndicator) {
            statusIndicator.innerHTML = getHypothesisIconMarkup('testing');
          }
        } else if (item.dataset.status === 'testing') {
          item.dataset.status = 'untested';
          if (statusIndicator) {
            statusIndicator.innerHTML = getHypothesisIconMarkup('untested');
          }
        }
      });

      const tests = Array.isArray(payload.tests) ? payload.tests : [];
      if (tests.length) {
        const response = {
          steps: tests.map((test, index) => ({
            title: `Test ${index + 1}`,
            description: test && typeof test.rationale === 'string' ? test.rationale : 'Testing the current hypothesis.',
            command: test && typeof test.command === 'string' ? test.command : '',
            command_id: test && typeof test.command_id === 'string' ? test.command_id : null
          }))
        };
        currentInvestigation.text.innerHTML = '';
        currentInvestigation.details.dataset.pendingCommands = String(
          response.steps.filter((step) => step.command).length
        );
        if (autoAllowEnabled) {
          currentInvestigation.text.textContent = 'Running diagnostic tests...';
        } else {
          populateAgentContent(currentInvestigation.text, response);
        }
      } else {
        currentInvestigation.text.textContent = 'No test commands generated.';
      }
      updateInvestigationTitle(currentInvestigation, "Testing Hypotheses");
    }

    function handleHypothesisTested(data) {
      const testedHypothesis = data && typeof data.hypothesis === 'object'
        ? data.hypothesis.hypothesis
        : (data && typeof data.hypothesis === 'string' ? data.hypothesis : '');
      if (!testedHypothesis) return;

      document.querySelectorAll('#hypothesisList .plan-item').forEach((item) => {
        if (item.dataset.hypothesis !== testedHypothesis) return;

        item.classList.remove('active');
        item.classList.add('done');
        item.dataset.status = 'tested';
        const statusIndicator = item.querySelector('.status-indicator');
        if (statusIndicator) {
          statusIndicator.innerHTML = getHypothesisIconMarkup('supported');
        }
      });
    }


    function handleCommandOutputs(data) {
      const commandEntries = Array.isArray(data)
        ? data
        : (data && typeof data === 'object' && typeof data.command === 'string' ? [data] : []);

      commandEntries.forEach((entry) => {
        if (!entry || typeof entry.command !== 'string') {
          return;
        }

        const outputText = (entry.output || entry.error || '').trim() || (entry.success ? '(Command executed)' : 'Command failed');
        const liveKey = `live:${entry.timestamp || Date.now()}:${entry.command}:${outputText}:${entry.success === false}`;
        addTerminalOutput(entry.command, outputText, entry.success === false, liveKey);
      });

      // Keep command output in the terminal only; do not wipe the active investigation card.
    }

    function formatSolution(solutionData) {
      if (!solutionData) {
        return 'No solution generated.';
      }

      if (typeof solutionData === 'string') {
        return solutionData;
      }

      const solutionStep = solutionData.step || {};
      const command = typeof solutionStep.command === 'string' ? solutionStep.command : '';
      const rationale = typeof solutionStep.rationale === 'string'
        ? solutionStep.rationale
        : (typeof solutionStep.reason === 'string' ? solutionStep.reason : '');
      const summary = typeof solutionData.summary === 'string'
        ? solutionData.summary
        : (typeof solutionData.explanation === 'string' ? solutionData.explanation : '');

      return [summary, command ? `Command: ${command}` : '', rationale ? `Reason: ${rationale}` : '']
        .filter(Boolean)
        .join('\n\n');
    }

    function handleVerification(data) {


      const payload = data && typeof data === 'object' && !Array.isArray(data) ? data : { step: { command: '', rationale: getDisplayTextFromPayload(data) } };
      const step = payload && typeof payload === 'object' && payload.step && typeof payload.step === 'object'
        ? payload.step
        : (payload && typeof payload === 'object' ? payload : {});
      const command = typeof step.command === 'string' ? step.command : '';
      const description = typeof step.rationale === 'string'
        ? step.rationale
        : (typeof step.description === 'string' ? step.description : (typeof step.reason === 'string' ? step.reason : 'Review and approve the verification command to validate the fix.'));

      if (command) {
        const response = {
          steps: [{
            title: step.title || 'Verification Command',
            description,
            command,
            command_id: typeof step.command_id === 'string' ? step.command_id : null,
            requires_sudo: Boolean(step.requires_sudo || payload.requires_sudo),
          }]
        };

        currentInvestigation.text.innerHTML = '';
        currentInvestigation.details.dataset.pendingCommands = '1';
        populateAgentContent(currentInvestigation.text, response);
        updateInvestigationTitle(currentInvestigation, 'Verify Fix');
        return;
      }

      currentInvestigation.text.textContent = 'No verification command generated.';
      updateInvestigationTitle(currentInvestigation, 'Verification');
    }

    function handleSolution(data) {
      if (!currentInvestigation) {
        currentInvestigation = createInvestigationPlaceholder('Review Solution', '');
      }

      const payload = data && typeof data === 'object' && !Array.isArray(data) ? data : { step: { command: '', rationale: getDisplayTextFromPayload(data) } };
      const step = payload && typeof payload === 'object' && payload.step && typeof payload.step === 'object'
        ? payload.step
        : (payload && typeof payload === 'object' ? payload : {});
      const command = typeof step.command === 'string' ? step.command : '';
      const description = typeof step.rationale === 'string'
        ? step.rationale
        : (typeof step.description === 'string' ? step.description : (typeof step.reason === 'string' ? step.reason : 'Review and approve the recommended remediation command.'));

      if (command) {
        const response = {
          steps: [{
            title: step.title || 'Proposed Solution',
            description,
            command,
            command_id: typeof step.command_id === 'string' ? step.command_id : null,
            requires_sudo: Boolean(step.requires_sudo || payload.requires_sudo),
          }]
        };

        currentInvestigation.text.innerHTML = '';
        currentInvestigation.details.dataset.pendingCommands = '1';
        populateAgentContent(currentInvestigation.text, response);
        updateInvestigationTitle(currentInvestigation, 'Review Solution');
        return;
      }

      currentInvestigation.text.textContent = formatSolution(payload);
      updateInvestigationTitle(currentInvestigation, 'Proposed Solution');
    }

    function handleIssueResolved(data) {
      if (!currentInvestigation) {
        currentInvestigation = createInvestigationPlaceholder('Issue Resolved', '');
      }

      const payload = data && typeof data === 'object' ? data : { message: 'The issue has been resolved.' };
      const message = typeof payload.message === 'string' ? payload.message : 'The issue has been resolved.';
      const summary = payload.summary && typeof payload.summary === 'object' ? formatSolution(payload.summary) : '';

      currentInvestigation.text.textContent = summary || message;
      updateInvestigationTitle(currentInvestigation, 'Issue Resolved');
    }

    function formatFacts(factsData) {
      if (!factsData || !factsData.facts || !Array.isArray(factsData.facts)) {
        return "No facts discovered.";
      }

      return factsData.facts
        .map((fact, idx) => `${idx + 1}. ${fact.fact || fact}`)
        .join("\n\n");
    }

    function handleFacts(data) {
      if (!currentInvestigation) return;

      const formatted = formatFacts(data);
      currentInvestigation.text.textContent = formatted;
      updateInvestigationTitle(currentInvestigation, "Facts Discovered");
    }

    window.handleInvestigationEvent = function (event) {
      console.log("Investigation event:", event);

      if (!event?.type) return;

      if (event.type === 'command_outputs') {
        handleCommandOutputs(event.data);
        return;
      }

      const hasActiveSession = activeSessionId !== null && activeSessionId !== undefined && activeSessionId !== '';
      const hasEventSession = event.session_id !== null && event.session_id !== undefined && event.session_id !== '';

      if (!isReplayingHistory && hasActiveSession && hasEventSession && String(event.session_id) !== String(activeSessionId)) {
        return;
      }

      switch (event.type) {
        case "investigation_started":
          if (currentInvestigation) {
            currentInvestigation.text.textContent = event.data?.message || 'Understanding the problem...';
          }
          break;
        case "user":
          appendMessage('user', event.data);
          break;
        case "problem_statement":
          handleProblemStatement(event.data);
          if (!isReplayingHistory) {
            currentInvestigation = createInvestigationPlaceholder("Hypothesizing", "");
          }
          break;
        case "hypotheses_started":
          if (currentInvestigation) {
            currentInvestigation.text.textContent = event.data?.message || 'Hypothesizing';
          }
          break;
        case "hypotheses":
          if (isReplayingHistory) {
            currentInvestigation = createInvestigationPlaceholder("Hypothesized", "");
          }
          handleHypotheses(event.data);
          if (!isReplayingHistory) {
            currentInvestigation = createInvestigationPlaceholder("Testing Hypotheses", "");
          }
          break;
        case "testing_hypothesis":
          if (isReplayingHistory) {
            currentInvestigation = createInvestigationPlaceholder("Testing Hypotheses", "");
          }
          handleTestingHypothesis({
            ...(event.data || {}),
            _history_event_id: event.event_id,
          });
          if (!isReplayingHistory) {
            currentInvestigation = currentInvestigation || createInvestigationPlaceholder("Executing Tests", "");
            if (autoAllowEnabled) {
              currentInvestigation.text.textContent = 'Running diagnostic tests...';
              updateInvestigationTitle(currentInvestigation, 'Executing Tests');
            } else {
              currentInvestigation = createInvestigationPlaceholder("Executing Tests", "");
            }
          }
          break;
        case "hypothesis_tested":
          handleHypothesisTested(event.data);
          break;
        case "command_outputs":
          handleCommandOutputs(event.data);
          break;
        case "solution":
           if (!isReplayingHistory) {
            currentInvestigation = createInvestigationPlaceholder('solving', '');
          }

          handleSolution({
            ...(event.data || {}),
            _history_event_id: event.event_id,
            _history_command_id: event.data?.step?.command_id || null,
          });
          // if (!isReplayingHistory) {
          //   currentInvestigation = currentInvestigation || createInvestigationPlaceholder("Executing Tests", "");
          //   if (autoAllowEnabled) {
          //     currentInvestigation.text.textContent = 'sds diagnostic tests...';
          //     updateInvestigationTitle(currentInvestigation, 'sdsd Tests');
          //   } else {
          //     currentInvestigation = createInvestigationPlaceholder("sd Tests", "");
          //   }
          // }
          break;
        case "verification":
          if (!isReplayingHistory) {
            currentInvestigation = createInvestigationPlaceholder('Verify Fix', '');
          }

          handleVerification({
            ...(event.data || {}),
            _history_event_id: event.event_id,
            _history_command_id: event.data?.step?.command_id || null,
          });
          // if (!isReplayingHistory) {
          //   currentInvestigation = currentInvestigation || createInvestigationPlaceholder("Executing Tests", "");
          //   if (autoAllowEnabled) {
          //     currentInvestigation.text.textContent = 'Verifing the fix';
          //     updateInvestigationTitle(currentInvestigation, 'Verify Fix');
          //   } 
          // }
          break;
        case "issue_resolved":
          handleIssueResolved(event.data);
          break;
        case "facts":
          if (isReplayingHistory) {
            currentInvestigation = createInvestigationPlaceholder("Facts Discovered", "");
          }
          handleFacts(event.data);
          if (!isReplayingHistory) {
            currentInvestigation = createInvestigationPlaceholder("Generating Solution", "");
          }
          break;
        case "investigation_error":
          if (currentInvestigation) {
            currentInvestigation.text.textContent = `Investigation failed: ${event.data?.message || 'Unknown error'}`;
            updateInvestigationTitle(currentInvestigation, "Investigation Failed");
          }
          break;
        case "investigation_complete":
          renderSessionList();
          break;
      }
    };

    if (attachLogButton) {
      attachLogButton.addEventListener('click', pickLogFile);
    }

    if (logFileInput) {
      logFileInput.addEventListener('change', async (event) => {
        const [file] = event.target.files || [];
        if (!file) {
          clearPendingAttachment();
          return;
        }

        const isTextFile = /\.txt$/i.test(file.name) || file.type === 'text/plain';
        if (!isTextFile) {
          addLogOutput('Please select a .txt file to attach.', true);
          clearPendingAttachment();
          return;
        }

        pendingAttachment = {
          name: file.name,
          text: await file.text(),
        };
        updateAttachmentStatus(file.name);
      });
    }

    if (attachmentClear) {
      attachmentClear.addEventListener('click', clearPendingAttachment);
    }

    chatInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        sendMessage();
      }
    });

    sendButton.addEventListener('click', sendMessage);

    if (stopAgentButton) {
      stopAgentButton.addEventListener('click', stopAgent);
      stopAgentButton.disabled = true;
      stopAgentButton.style.opacity = '0.55';
    }

    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', toggleSidebar);
    }

    if (rightPanelResizer) {
      rightPanelResizer.addEventListener('mousedown', startRightPanelResize);
    }

    if (modelSelect) {
      modelSelect.addEventListener('change', async () => {
        if (modelSelect.disabled) {
          return;
        }
        if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.set_model !== 'function') {
          return;
        }

        try {
          const result = await window.pywebview.api.set_model(modelSelect.value);
          if (result && result.status === 'ok') {
            addLogOutput(`Model switched to ${result.model}.`);
            modelSelect.value = result.model;
          } else if (result && result.status === 'error') {
            addLogOutput(result.message || 'Unable to switch model.', true);
            modelSelect.value = result.model;
          }
        } catch (error) {
          addLogOutput(`Unable to switch model: ${error.message || error}`, true);
        }
      });
    }

    sessionsButton.addEventListener('click', toggleSessionsPanel);
    closeSessionsButton.addEventListener('click', toggleSessionsPanel);

    if (settingsNav) {
      settingsNav.addEventListener('click', (event) => {
        event.preventDefault();
        navigateToPage('settings.html', 'open_settings');
      });
    }

    newSessionButton.addEventListener('click', async (event) => {
      event.preventDefault();
      if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.create_new_session !== 'function') {
        addLogOutput('The desktop API is not available.', true);
        return;
      }
      try {
        const result = await window.pywebview.api.create_new_session();
        activeSessionId = result && result.session_id ? result.session_id : null;
        sidebar.classList.remove('is-session-mode');
        sessionsOpen = false;
        window.investigating_obj = null;
        clearChatView();
        clearTerminalView();
        updateAutoAllowUI(false);
        appendMessage('agent', 'I’m ready to help with Linux troubleshooting. Ask me anything.');
        setSessionTitle('Live Session');
        if (modelSelect) {
          modelSelect.disabled = false;
          modelSelect.classList.remove('locked');
          if (result && typeof result.current_chat_model === 'string' && result.current_chat_model) {
            modelSelect.value = result.current_chat_model;
          } else if (result && typeof result.default_model === 'string' && result.default_model) {
            modelSelect.value = result.default_model;
          }
        }
        addLogOutput(result && result.status ? `New ${result.status} created.` : 'New session created.');
        renderSessionList();
      } catch (error) {
        addLogOutput(`Unable to create a new session: ${error.message || error}`, true);
      }
    });

    window.addEventListener('load', () => loadAvailableModels());
    window.addEventListener('pywebviewready', () => loadAvailableModels());
    setTimeout(loadAvailableModels, 100);

    document.querySelectorAll('.control-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (btn.innerText === '✕') {
          if (confirm('Close application?')) window.close();
        }
      });
    });
  })();
}
if (isSettingsPage) {
  (function () {
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const defaultModelSelect = document.getElementById('defaultModelSelect');
    const modeButtons = Array.from(document.querySelectorAll('.mode-option'));
    const cancelButton = document.getElementById('cancelSettingsButton');
    const saveButton = document.getElementById('saveSettingsButton');
    const newSessionButton = document.getElementById('newSessionButton');
    const sessionsButton = document.querySelector('[data-role="sessions-toggle"]');

    function toggleSidebar() {
      const isCollapsed = sidebar.classList.toggle('is-collapsed');
      if (sidebarToggle) {
        sidebarToggle.classList.toggle('is-closed', isCollapsed);
        sidebarToggle.setAttribute('aria-label', isCollapsed ? 'Open sidebar' : 'Collapse sidebar');
      }
    }

    function setSelectedMode(mode) {
      modeButtons.forEach((button) => {
        const isSelected = button.dataset.mode === mode;
        button.classList.toggle('is-selected', isSelected);
        button.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
      });
    }

    async function loadAvailableModels(retries = 12) {
      if (!defaultModelSelect) {
        return;
      }
      if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.list_models !== 'function') {
        if (retries > 0) {
          setTimeout(() => loadAvailableModels(retries - 1), 250);
        }
        return;
      }

      defaultModelSelect.innerHTML = '<option>Loading models...</option>';

      try {
        const models = await window.pywebview.api.list_models();
        const normalizedModels = Array.isArray(models) ? models : (models && Array.isArray(models.models) ? models.models : []);

        defaultModelSelect.innerHTML = '';
        if (!normalizedModels.length) {
          const option = document.createElement('option');
          option.value = '';
          option.textContent = 'No models found';
          defaultModelSelect.appendChild(option);
          return;
        }

        normalizedModels.forEach((modelName) => {
          const option = document.createElement('option');
          option.value = modelName;
          option.textContent = modelName;
          defaultModelSelect.appendChild(option);
        });

        const settings = await window.pywebview.api.get_settings();
        if (settings && typeof settings.default_model === 'string' && settings.default_model) {
          defaultModelSelect.value = settings.default_model;
        }
        const selectedMode = settings && settings.permission_mode === 'auto_confirm' ? 'auto_confirm' : 'ask_before_running';
        setSelectedMode(selectedMode);
      } catch (error) {
        defaultModelSelect.innerHTML = '<option>No models found</option>';
        console.error(error);
      }
    }

    async function saveSettings() {
      if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.save_settings !== 'function') {
        return;
      }
      const selectedMode = modeButtons.find((button) => button.classList.contains('is-selected'))?.dataset.mode || 'ask_before_running';
      const payload = {
        default_model: defaultModelSelect.value,
        permission_mode: selectedMode,
      };
      try {
        await window.pywebview.api.save_settings(payload);
        navigateToPage('index.html', 'open_main');
      } catch (error) {
        console.error(error);
      }
    }

    modeButtons.forEach((button) => {
      button.addEventListener('click', () => {
        setSelectedMode(button.dataset.mode);
      });
    });

    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', toggleSidebar);
    }

    if (cancelButton) {
      cancelButton.addEventListener('click', (event) => {
        event.preventDefault();
        navigateToPage('index.html', 'open_main');
      });
    }

    if (saveButton) {
      saveButton.addEventListener('click', saveSettings);
    }

    if (newSessionButton) {
      newSessionButton.addEventListener('click', async (event) => {
        event.preventDefault();
        if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.create_new_session !== 'function') {
          console.error('The desktop API is not available.');
          return;
        }

        try {
          await window.pywebview.api.create_new_session();
        } catch (error) {
          console.error(error);
        }
        navigateToPage('index.html', 'open_main');
      });
    }

    if (sessionsButton) {
      sessionsButton.addEventListener('click', (event) => {
        event.preventDefault();
        navigateToPage('index.html', 'open_main');
      });
    }

    document.querySelectorAll('[data-role="settings-nav"]').forEach((nav) => {
      nav.addEventListener('click', (event) => {
        event.preventDefault();
        navigateToPage('settings.html', 'open_settings');
      });
    });

    window.addEventListener('load', () => loadAvailableModels());
    setTimeout(loadAvailableModels, 100);
  })();
}