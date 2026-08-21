/* ============================================================================
   VentureMind AI — Dashboard Controller
   Links plain HTML UI components to the FastAPI backend REST API.
   Handles: Auth checks, Tab views, History fetches, Analysis execution,
   Document upload, and deep-dive Interactive Memo reports.
   ============================================================================ */

const API_BASE = (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1'))
  ? 'http://localhost:8000/api/v1'
  : '/api/v1';

// Direct redirect to login if no active mock account exists
function checkAuth() {
  const account = AccountStore.getActiveAccount();
  if (!account) {
    location.href = 'login.html';
  } else {
    // Populate profile widgets in nav
    const initial = account.name.trim()[0].toUpperCase();
    document.getElementById('profileInitial').textContent = initial;
    document.getElementById('profileMenuAvatar').textContent = initial;
    document.getElementById('profileMenuName').textContent = account.name;
    document.getElementById('profileMenuEmail').textContent = account.email;
    document.getElementById('profileMenuTag').textContent = account.type === 'business' ? 'Business' : 'Personal';
    document.getElementById('navProfile').classList.remove('hidden');
    const loginBtn = document.getElementById('navLoginBtn');
    if (loginBtn) loginBtn.classList.add('hidden');
  }
}

// Nav dropdown toggle
function toggleProfileMenu(e) {
  e.stopPropagation();
  document.getElementById('profileMenu').classList.toggle('open');
}

function logoutAllFromNav() {
  document.getElementById('profileMenu').classList.remove('open');
  AccountStore.clear();
  location.href = 'login.html';
}

document.addEventListener('click', function(e) {
  const menu = document.getElementById('profileMenu');
  if (menu && menu.classList.contains('open') && !e.target.closest('.nav-profile')) {
    menu.classList.remove('open');
  }
});

// Tab switching controller
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

  const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  if (activeBtn) activeBtn.classList.add('active');
  const activeContent = document.getElementById(tabId);
  if (activeContent) activeContent.classList.add('active');

  // Load contextual data
  if (tabId === 'overview' || tabId === 'history') {
    loadHistoryData();
  }
}

// Local cache for fetched analysis history
let analysisHistory = [];

async function loadHistoryData() {
  const errorAlert = document.getElementById('historyError');
  if (errorAlert) errorAlert.classList.remove('show');

  try {
    const res = await fetch(`${API_BASE}/analysis/history`);
    if (!res.ok) throw new Error('Failed to load history');
    analysisHistory = await res.json();
    
    renderOverviewStats();
    renderHistoryTable();
    renderOverviewList();
  } catch (err) {
    console.error(err);
    if (errorAlert) {
      errorAlert.textContent = 'Unable to connect to the backend server. Make sure the FastAPI service is running on port 8000.';
      errorAlert.classList.add('show');
    }
  }
}

/**
 * Normalizes verdict strings across historical data ("BUY") and canonical outputs ("INVEST", "WATCH", "PASS").
 * Historical "BUY" values are mapped to "INVEST" for statistics and rendering.
 */
function normalizeVerdict(verdict) {
  const val = String(verdict || '').trim().toUpperCase();
  if (val === 'BUY' || val === 'INVEST') return 'INVEST';
  if (val === 'WATCH') return 'WATCH';
  if (val === 'PASS') return 'PASS';
  if (val) {
    console.warn(`[VentureMind UI] Unrecognized verdict encountered: '${verdict}'. Defaulting to 'WATCH'.`);
  }
  return 'WATCH';
}

function renderOverviewStats() {
  const count = analysisHistory.length;
  document.getElementById('statTotalAnalyses').textContent = count;

  let totalScore = 0;
  let buyCount = 0;
  let watchCount = 0;
  let passCount = 0;

  analysisHistory.forEach(item => {
    const dec = item.final_decision || {};
    const score = dec.final_score || item.final_score || 0;
    const rawVerdict = dec.verdict || item.verdict || '';
    const verdict = normalizeVerdict(rawVerdict);

    totalScore += score;
    if (verdict === 'INVEST') buyCount++;
    else if (verdict === 'WATCH') watchCount++;
    else if (verdict === 'PASS') passCount++;
  });

  const avgScore = count > 0 ? (totalScore / count).toFixed(1) : '0';
  document.getElementById('statAvgScore').textContent = avgScore;
  document.getElementById('statBuy').textContent = buyCount;
  document.getElementById('statWatch').textContent = watchCount;
  document.getElementById('statPass').textContent = passCount;
}

function renderHistoryTable() {
  const tbody = document.getElementById('historyTbody');
  if (!tbody) return;
  tbody.innerHTML = '';

  if (analysisHistory.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-row">No evaluation runs recorded. Run an analysis to get started.</td></tr>';
    return;
  }

  // Sort by date descending
  const sorted = [...analysisHistory].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  sorted.forEach(item => {
    const dec = item.final_decision || {};
    const rawVerdict = dec.verdict || item.verdict || 'WATCH';
    const verdict = normalizeVerdict(rawVerdict);
    const score = (dec.final_score || item.final_score || 0).toFixed(1);
    const category = dec.category || item.category || 'HYBRID';
    const date = new Date(item.created_at).toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });

    const tr = document.createElement('tr');
    tr.onclick = () => viewReportDetails(item.id);
    tr.innerHTML = `
      <td><b>${item.company_name}</b></td>
      <td>${date}</td>
      <td><span class="badge badge-outline">${category}</span></td>
      <td><span class="score-pill">${score}</span></td>
      <td><span class="verdict-tag verdict-${verdict.toLowerCase()}">${verdict}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderOverviewList() {
  const container = document.getElementById('overviewRecentList');
  if (!container) return;
  container.innerHTML = '';

  if (analysisHistory.length === 0) {
    container.innerHTML = '<div class="empty-state-msg">No evaluations yet. Submitting a company in the "Analyze Startup" section will run our multi-agent pipeline and generate a report.</div>';
    return;
  }

  const sorted = [...analysisHistory].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 4);

  sorted.forEach(item => {
    const dec = item.final_decision || {};
    const rawVerdict = dec.verdict || item.verdict || 'WATCH';
    const verdict = normalizeVerdict(rawVerdict);
    const score = (dec.final_score || item.final_score || 0).toFixed(1);
    const narrative = dec.narrative || item.narrative || 'No synthesis narrative provided.';

    const div = document.createElement('div');
    div.className = 'recent-card';
    div.onclick = () => viewReportDetails(item.id);
    div.innerHTML = `
      <div class="rc-header">
        <div>
          <h3>${item.company_name}</h3>
          <span class="badge-mini">${dec.category || item.category || 'HYBRID'}</span>
        </div>
        <div class="rc-badges">
          <span class="score-pill">${score}</span>
          <span class="verdict-tag verdict-${verdict.toLowerCase()}">${verdict}</span>
        </div>
      </div>
      <p class="rc-desc">${narrative.length > 140 ? narrative.slice(0, 140) + '...' : narrative}</p>
    `;
    container.appendChild(div);
  });
}

// Submit a startup for evaluation
async function handleAnalysisSubmit(e) {
  e.preventDefault();
  const form = document.getElementById('analyzeForm');
  const errorEl = document.getElementById('analyzeFormError');
  errorEl.classList.remove('show');

  const payload = {
    company: form.companyName.value.trim(),
    industry: form.industry.value.trim() || 'AI',
    funding: parseFloat(form.funding.value) || 0,
    employees: parseInt(form.employees.value, 10) || 0,
    age: parseInt(form.age.value, 10) || 0,
    revenue: parseFloat(form.revenue.value) || 0,
    growth: parseFloat(form.growth.value) || 0,
    github_repo: form.githubRepo.value.trim() || null,
    founder_names: form.founderNames.value.trim() || null
  };

  if (!payload.company) {
    errorEl.textContent = 'Company Name is required.';
    errorEl.classList.add('show');
    return;
  }

  // Swap views: show live pipeline running screen
  document.getElementById('analysisInputView').classList.add('hidden');
  const runningView = document.getElementById('analysisRunningView');
  runningView.classList.remove('hidden');

  // Trigger agent step-by-step progress simulation
  runPipelineProgressSimulator(payload.company);

  try {
    const res = await fetch(`${API_BASE}/analysis/startup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(`Server returned error: ${res.status}`);
    }

    const data = await res.json();
    
    // Complete simulator and jump to detailed report view
    stopPipelineSimulator();
    setTimeout(() => {
      runningView.classList.add('hidden');
      document.getElementById('analysisInputView').classList.remove('hidden');
      form.reset();
      
      // Open report tab and load the returned analysis details
      switchTab('history');
      renderReportMarkup(data);
      document.getElementById('reportDetailPane').classList.add('open');
    }, 1500);

  } catch (err) {
    console.error(err);
    stopPipelineSimulator();
    runningView.classList.add('hidden');
    document.getElementById('analysisInputView').classList.remove('hidden');
    errorEl.textContent = 'Error executing workflow. Check connection to uvicorn backend.';
    errorEl.classList.add('show');
  }
}

// Multi-agent execution steps simulation
let pipelineInterval = null;
const agentSteps = [
  { id: 'step-research', text: 'Research Agent: Scanning public metadata & startup info...' },
  { id: 'step-classify', text: 'Classifier Agent: Profiling company tech taxonomy...' },
  { id: 'step-market', text: 'Market Agent: Modeling TAM, SAM & CAGR forecasts...' },
  { id: 'step-competitor', text: 'Competitor Agent: Mapping defensive moats & rivals...' },
  { id: 'step-founder', text: 'Founder Agent: Scoring team execution capability...' },
  { id: 'step-finance', text: 'Finance Agent: Crunching revenue lines & economics...' },
  { id: 'step-github', text: 'GitHub Agent: Performing deep repository audits...' },
  { id: 'step-risk', text: 'Risk Agent: Listing compliance & downside flags...' },
  { id: 'step-predict', text: 'Prediction Agent: Synthesizing machine learning projection signals...' },
  { id: 'step-committee', text: 'Committee Agent: Resolving conflicting scores...' }
];

function runPipelineProgressSimulator(companyName) {
  document.getElementById('pipelineRunningCompany').textContent = companyName;
  
  // Reset nodes styling
  agentSteps.forEach(step => {
    const el = document.getElementById(step.id);
    if (el) {
      el.className = 'progress-step';
      const spinner = el.querySelector('.ps-spinner');
      if (spinner) {
        spinner.className = 'ps-spinner';
        spinner.textContent = '';
      }
    }
  });

  let index = 0;
  
  function nextStep() {
    if (index > 0) {
      // Mark previous step as done
      const prevEl = document.getElementById(agentSteps[index - 1].id);
      if (prevEl) {
        prevEl.className = 'progress-step done';
        const spinner = prevEl.querySelector('.ps-spinner');
        if (spinner) {
          spinner.className = 'ps-spinner check-icon';
          spinner.textContent = '✓';
        }
      }
    }

    if (index < agentSteps.length) {
      const curEl = document.getElementById(agentSteps[index].id);
      if (curEl) {
        curEl.className = 'progress-step active';
        const spinner = curEl.querySelector('.ps-spinner');
        if (spinner) {
          spinner.className = 'ps-spinner active-spinner';
        }
      }
      index++;
    }
  }

  nextStep();
  pipelineInterval = setInterval(nextStep, 2500);
}

function stopPipelineSimulator() {
  clearInterval(pipelineInterval);
  agentSteps.forEach(step => {
    const el = document.getElementById(step.id);
    if (el && !el.classList.contains('done')) {
      el.className = 'progress-step done';
      const spinner = el.querySelector('.ps-spinner');
      if (spinner) {
        spinner.className = 'ps-spinner check-icon';
        spinner.textContent = '✓';
      }
    }
  });
}

// Renders the detailed deep-dive evaluation report
function renderReportMarkup(item) {
  const dec = item.final_decision || item;
  const company = item.company_name || dec.company || 'Company';
  const score = (dec.final_score || 0).toFixed(1);
  const verdict = normalizeVerdict(dec.verdict || item.verdict);
  const category = dec.category || 'HYBRID';
  const date = new Date(item.created_at || new Date()).toLocaleDateString(undefined, {
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  });

  // Basic info
  document.getElementById('repCompanyName').textContent = company;
  document.getElementById('repDate').textContent = date;
  document.getElementById('repCategory').textContent = category;
  document.getElementById('repScoreVal').textContent = score;

  // Render SVG score wheel
  const circumference = 2 * Math.PI * 45; // radius is 45
  const offset = circumference - (dec.final_score / 100) * circumference;
  document.getElementById('repScoreCircle').style.strokeDashoffset = offset;

  // Verdict design class
  const badge = document.getElementById('repVerdictBadge');
  badge.textContent = verdict;
  badge.className = `verdict-tag verdict-${verdict.toLowerCase()}`;

  // Disagreement banner logic
  const diagBanner = document.getElementById('repDisagreementBanner');
  const diagNote = document.getElementById('repDisagreementNote');
  const isDisagreement = item.significant_disagreement || dec.significant_disagreement || false;
  const disagreementNote = item.disagreement_note || dec.disagreement_note || '';

  if (diagBanner && diagNote) {
    if (isDisagreement) {
      diagNote.textContent = disagreementNote || "The committee detected scoring variance between specialist agents.";
      diagBanner.classList.remove('hidden');
    } else {
      diagBanner.classList.add('hidden');
    }
  }

  // Confidence badge logic
  let confVal = dec.overall_confidence !== undefined ? dec.overall_confidence : (item.overall_confidence !== undefined ? item.overall_confidence : 0.0);
  if (confVal > 1) confVal = confVal / 100.0;
  const confBadge = document.getElementById('repConfidenceBadge');
  if (confBadge) {
    confBadge.textContent = `Confidence: ${(confVal * 100).toFixed(0)}%`;
    confBadge.className = 'badge-confidence';
    if (confVal >= 0.70) {
      confBadge.classList.add('conf-high');
    } else if (confVal >= 0.40) {
      confBadge.classList.add('conf-med');
    } else {
      confBadge.classList.add('conf-low');
    }
  }

  // Narrative summary
  document.getElementById('repNarrative').textContent = dec.narrative || 'No synthesis narrative provided.';

  // Opportunities and Risks
  const oppsList = document.getElementById('repOppsList');
  oppsList.innerHTML = '';
  const opps = dec.key_opportunities || [];
  if (opps.length === 0) {
    oppsList.innerHTML = '<li>No major opportunities highlighted.</li>';
  } else {
    opps.forEach(opp => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="bullet-icon font-glow-green">✦</span> ${opp}`;
      oppsList.appendChild(li);
    });
  }

  const risksList = document.getElementById('repRisksList');
  risksList.innerHTML = '';
  const risks = dec.key_risks || [];
  if (risks.length === 0) {
    risksList.innerHTML = '<li>No critical risks flags raised.</li>';
  } else {
    risks.forEach(risk => {
      const li = document.createElement('li');
      li.innerHTML = `<span class="bullet-icon font-glow-red">⚠</span> ${risk}`;
      risksList.appendChild(li);
    });
  }

  // Agent cards rendering
  const results = item.agent_results || dec.agent_results || {};
  const agentGrid = document.getElementById('repAgentGrid');
  agentGrid.innerHTML = '';

  const showableAgents = [
    { key: 'Research Agent', label: 'Research Agent', icon: '🔍' },
    { key: 'Market Agent', label: 'Market Agent', icon: '📈' },
    { key: 'Competitor Agent', label: 'Competitor Agent', icon: '🥊' },
    { key: 'Founder Agent', label: 'Founder Agent', icon: '👥' },
    { key: 'Finance Agent', label: 'Finance Agent', icon: '💰' },
    { key: 'GitHub Agent', label: 'GitHub Agent', icon: '💻' },
    { key: 'Risk Agent', label: 'Risk Modifier', icon: '⚠' },
    { key: 'Prediction Agent', label: 'Prediction Signal', icon: '🔮' }
  ];

  showableAgents.forEach(agent => {
    const data = results[agent.key];
    if (!data) return;

    const aScore = data.score !== undefined ? data.score : 'N/A';
    const confPct = Math.round((data.confidence || 0) * 100);
    const reasoning = data.reasoning || data.explanation || 'No notes.';
    const evidence = data.evidence || [];

    const card = document.createElement('div');
    card.className = 'agent-card';
    
    let scoreDisplay = `<div class="ac-score">${aScore}</div>`;
    if (aScore === 'N/A') {
      scoreDisplay = `<div class="ac-score na">--</div>`;
    }

    let evidenceHtml = '';
    if (evidence.length > 0) {
      evidenceHtml = `
        <div class="ac-evidence">
          <h4>Evidence Cited</h4>
          <ul>
            ${evidence.slice(0, 3).map(ev => `<li>• ${ev}</li>`).join('')}
          </ul>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="ac-header">
        <span class="ac-icon">${agent.icon}</span>
        <div>
          <h3>${agent.label}</h3>
          <div class="ac-conf">Confidence: ${confPct}%</div>
        </div>
        ${scoreDisplay}
      </div>
      <div class="ac-progress"><div class="ac-progress-bar" style="width: ${confPct}%"></div></div>
      <p class="ac-reason">${reasoning}</p>
      ${evidenceHtml}
    `;
    agentGrid.appendChild(card);
  });
}

function viewReportDetails(analysisId) {
  const item = analysisHistory.find(x => x.id === parseInt(analysisId, 10));
  if (!item) return;
  renderReportMarkup(item);
  document.getElementById('reportDetailPane').classList.add('open');
}

function closeReportDetails() {
  document.getElementById('reportDetailPane').classList.remove('open');
}

// Drag & drop file uploads
function initFileUpload() {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const progressContainer = document.getElementById('uploadProgressContainer');
  const progressText = document.getElementById('uploadProgressText');
  const successEl = document.getElementById('uploadSuccessMsg');
  const errorEl = document.getElementById('uploadErrorMsg');

  if (!dropZone) return;

  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });

  dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
  });

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      uploadFile(e.target.files[0]);
    }
  });

  async function uploadFile(file) {
    if (!successEl || !errorEl) return;
    successEl.classList.remove('show');
    errorEl.classList.remove('show');

    if (file.type !== 'application/pdf') {
      errorEl.textContent = 'Only PDF pitch decks are supported.';
      errorEl.classList.add('show');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    progressContainer.classList.remove('hidden');
    progressText.textContent = `Uploading ${file.name}...`;

    try {
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) throw new Error('Upload request failed.');
      const data = await res.json();
      
      progressContainer.classList.add('hidden');
      successEl.innerHTML = `<strong>Success!</strong> ${file.name} uploaded and indexed into Vector DB.`;
      successEl.classList.add('show');
      fileInput.value = '';
    } catch (err) {
      console.error(err);
      progressContainer.classList.add('hidden');
      errorEl.textContent = 'Server connection failed. Could not upload document.';
      errorEl.classList.add('show');
      fileInput.value = '';
    }
  }
}

// ============================================================================
// AI Chat Bot Controller
// ============================================================================

let chatHistory = [
  { role: 'assistant', content: 'Hello! I am your AI Investment Assistant. Ask me any questions about startup metrics, uploaded specifications, or due diligence rubric criteria.' }
];

function initChatBot() {
  const form = document.getElementById('chatInputForm');
  if (!form) return;
  
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = document.getElementById('chatInputText');
    const text = input.value.trim();
    if (!text) return;
    
    input.value = '';
    
    // Render user message bubble
    appendChatBubble('user', text);
    chatHistory.push({ role: 'user', content: text });
    
    // Add typing visual indicators
    const loader = appendTypingIndicator();
    
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: 'user_dashboard_session' })
      });
      
      if (loader) loader.remove();
      
      if (!res.ok) {
        let errMessage = `Server error (${res.status})`;
        try {
          const rawText = await res.text();
          if (rawText && rawText.trim()) {
            try {
              const errData = JSON.parse(rawText);
              if (errData && errData.detail) {
                errMessage = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
              }
            } catch (_) {
              // If plain text error, suppress raw string syntax error messages
              if (!rawText.includes('is not valid JSON')) {
                errMessage = rawText.trim();
              }
            }
          }
        } catch (_) {}
        throw new Error(errMessage);
      }

      const bubbleObj = createChatBubble('assistant', '');
      let fullText = '';
      
      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const data = await res.json();
        fullText = data.response || data.content || data.detail || JSON.stringify(data);
        bubbleObj.updateText(fullText);
      } else {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunkText = decoder.decode(value, { stream: true });
          fullText += chunkText;
          bubbleObj.updateText(fullText);
        }
      }

      if (!fullText.trim()) {
        bubbleObj.updateText('No response content returned.');
      }

      chatHistory.push({ role: 'assistant', content: fullText });
    } catch (err) {
      console.error(err);
      if (loader) loader.remove();
      const rawErrMsg = (err && err.message) ? err.message : '';
      if (rawErrMsg && !rawErrMsg.includes('is not valid JSON') && !rawErrMsg.includes('JSON at position')) {
        appendChatBubble('assistant', rawErrMsg);
      } else {
        appendChatBubble('assistant', 'Unable to fetch response from backend service. Please check server logs or refresh page.');
      }
    }
  });
}

function createChatBubble(role, content) {
  const area = document.getElementById('chatMessagesArea');
  if (!area) return { element: null, updateText: () => {}, setStatus: () => {} };
  
  const bubble = document.createElement('div');
  bubble.className = `chat-bubble ${role}`;
  
  const sender = role === 'user' ? 'Investor' : 'VentureMind AI Co-Pilot';

  const statusDiv = document.createElement('div');
  statusDiv.className = 'cb-status-badge';
  statusDiv.style.fontSize = '0.8rem';
  statusDiv.style.opacity = '0.8';
  statusDiv.style.fontStyle = 'italic';
  statusDiv.style.marginBottom = '6px';
  statusDiv.style.display = 'none';

  const textDiv = document.createElement('div');
  textDiv.className = 'cb-text';
  textDiv.textContent = content;

  bubble.innerHTML = `<div class="cb-sender">${sender}</div>`;
  bubble.appendChild(statusDiv);
  bubble.appendChild(textDiv);
  
  area.appendChild(bubble);
  area.scrollTop = area.scrollHeight;

  return {
    element: bubble,
    setStatus: (statusText) => {
      if (statusText) {
        statusDiv.textContent = `⚡ ${statusText}`;
        statusDiv.style.display = 'block';
      } else {
        statusDiv.style.display = 'none';
      }
      area.scrollTop = area.scrollHeight;
    },
    updateText: (newContent) => {
      statusDiv.style.display = 'none';
      textDiv.textContent = newContent;
      area.scrollTop = area.scrollHeight;
    }
  };
}

function appendChatBubble(role, content) {
  createChatBubble(role, content);
}

function appendTypingIndicator() {
  const area = document.getElementById('chatMessagesArea');
  if (!area) return null;
  
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble assistant';
  bubble.id = 'chatTypingIndicator';
  bubble.innerHTML = `
    <div class="cb-sender">VentureMind AI Co-Pilot</div>
    <div class="typing-dots">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
  area.appendChild(bubble);
  area.scrollTop = area.scrollHeight;
  return bubble;
}

function sendSuggestedChat(text) {
  const textarea = document.getElementById('chatInputText');
  if (!textarea) return;
  textarea.value = text;
  
  const form = document.getElementById('chatInputForm');
  if (form) {
    const event = new Event('submit', { cancelable: true });
    form.dispatchEvent(event);
  }
}

// Sidebar toggle collapse logic
function initSidebarToggle() {
  const collapseBtn = document.getElementById('sidebarCollapseBtn');
  const expandBtn = document.getElementById('sidebarExpandBtn');
  const container = document.querySelector('.dashboard-container');
  
  if (collapseBtn && container) {
    collapseBtn.addEventListener('click', () => {
      container.classList.add('sidebar-collapsed');
      if (expandBtn) expandBtn.classList.remove('hidden');
    });
  }
  
  if (expandBtn && container) {
    expandBtn.addEventListener('click', () => {
      container.classList.remove('sidebar-collapsed');
      expandBtn.classList.add('hidden');
    });
  }
}

// Theme logic integration
function initThemeSync() {
  const saved = localStorage.getItem('vm-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = saved === 'dark' ? '☼' : '☾';
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('vm-theme', next);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = next === 'dark' ? '☼' : '☾';
}

// Initial bootstrapper
window.addEventListener('DOMContentLoaded', () => {
  initThemeSync();
  checkAuth();
  initFileUpload();
  initChatBot();
  initSidebarToggle();

  // Tab switching links
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Run initial history fetch
  loadHistoryData();

  // Analyze Form Submit Listener
  const analyzeForm = document.getElementById('analyzeForm');
  if (analyzeForm) {
    analyzeForm.addEventListener('submit', handleAnalysisSubmit);
  }
});
