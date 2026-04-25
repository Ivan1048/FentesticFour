/* ═══════════════════════════════════════════
   LoanAI — Frontend Logic
   UMHackathon 2026 · FentesticFour
   ═══════════════════════════════════════════ */

// ─── State ───────────────────────────────────
const state = {
    currentUser: null,
    isProcessing: false,
    selectedFile: null,
};

const AGENT_KEYS = ["extraction", "validation", "financial", "credit", "legal", "contract", "decision"];

const SCENARIOS = {
    good:    "I would like to apply for a home loan. My monthly salary is RM8,000 and I've been working as a permanent employee at Maybank for 7 years. I'm looking at a property worth RM450,000 in Selangor. I have existing monthly debt commitments of RM500 for my car loan.",
    partial: "Hi, I want to buy a house worth RM350,000. My salary is RM5,000 per month.",
    risky:   "I need a home loan urgently. I earn RM3,000 per month as a contract worker for 1 year. The property costs RM500,000 and I have existing debts of RM1,500 monthly.",
};

// ─── DOM refs ────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ─── Screen Navigation ──────────────────────
function showScreen(id) {
    $$(".screen").forEach((s) => s.classList.remove("active"));
    const target = $(`#${id}`);
    if (target) target.classList.add("active");
}

// ─── Init ────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // Landing → Auth
    $("#get-started-btn").addEventListener("click", () => showScreen("auth-screen"));

    // Auth → Landing (back button + logo)
    $("#auth-back-btn").addEventListener("click", () => showScreen("landing-screen"));
    $("#auth-logo-link").addEventListener("click", () => showScreen("landing-screen"));

    // Auth tabs
    $$(".auth-tab").forEach((tab) => {
        tab.addEventListener("click", () => {
            $$(".auth-tab").forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");
            $$(".auth-form").forEach((f) => f.classList.remove("active"));
            $(`#${tab.dataset.tab}-form`).classList.add("active");
            hideAuthMsg();
        });
    });

    // Auth forms
    $("#login-form").addEventListener("submit", handleLogin);
    $("#register-form").addEventListener("submit", handleRegister);

    // Chat
    $("#send-btn").addEventListener("click", sendMessage);
    $("#chat-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // File Upload
    $("#upload-btn").addEventListener("click", () => $("#file-input").click());
    $("#file-input").addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) handleFileUpload(file);
    });
    // Auto-resize textarea
    $("#chat-input").addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });

    // Scenarios
    $$(".scenario-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const key = btn.dataset.scenario;
            if (SCENARIOS[key]) {
                $("#chat-input").value = SCENARIOS[key];
                $("#chat-input").focus();
                $("#chat-input").dispatchEvent(new Event("input"));
            }
        });
    });

    // Settings modal
    $("#settings-btn").addEventListener("click", () => $("#settings-modal").classList.remove("hidden"));
    $("#menu-toggle").addEventListener("click", () => $("#agent-sidebar").classList.toggle("open"));
    $("#close-settings").addEventListener("click", () => $("#settings-modal").classList.add("hidden"));
    $("#close-settings-2").addEventListener("click", () => $("#settings-modal").classList.add("hidden"));
    $("#modal-overlay").addEventListener("click", () => $("#settings-modal").classList.add("hidden"));
    $("#save-api-key").addEventListener("click", saveApiKey);

    // New application
    $("#new-application-btn").addEventListener("click", resetApplication);

    // Logout
    $("#logout-btn").addEventListener("click", () => {
        state.currentUser = null;
        showScreen("auth-screen");
    });

    // Password visibility toggle
    $$(".pw-toggle").forEach((btn) => {
        btn.addEventListener("click", () => {
            const input = $(`#${btn.dataset.target}`);
            const isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";
            btn.querySelector(".eye-open").classList.toggle("hidden", !isPassword);
            btn.querySelector(".eye-closed").classList.toggle("hidden", isPassword);
            btn.title = isPassword ? "Hide password" : "Show password";
        });
    });

    // File upload
    $("#upload-btn").addEventListener("click", () => $("#file-input").click());
    $("#file-input").addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;
        state.selectedFile = file;
        $("#file-name-display").textContent = file.name;
        $("#file-preview-container").classList.remove("hidden");
    });
    $("#remove-file-btn").addEventListener("click", clearSelectedFile);

    // Check Gemini status on load
    checkGeminiStatus();
});

// ─── Auth ────────────────────────────────────
async function handleLogin(e) {
    e.preventDefault();
    const username = $("#login-username").value.trim();
    const password = $("#login-password").value;
    if (!username || !password) return;

    try {
        const res = await api("/auth/login", { username, password });
        state.currentUser = username;
        enterMainScreen();
    } catch (err) {
        showAuthMsg(err.message, "error");
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = $("#register-username").value.trim();
    const password = $("#register-password").value;
    if (!username || !password) return;

    try {
        const res = await api("/auth/register", { username, password });
        showAuthMsg(res.message + " Switching to login...", "success");
        setTimeout(() => {
            // Switch to login tab
            $$(".auth-tab").forEach((t) => t.classList.remove("active"));
            $("#tab-login").classList.add("active");
            $$(".auth-form").forEach((f) => f.classList.remove("active"));
            $("#login-form").classList.add("active");
            $("#login-username").value = username;
            $("#login-password").focus();
            hideAuthMsg();
        }, 1500);
    } catch (err) {
        showAuthMsg(err.message, "error");
    }
}

function showAuthMsg(msg, type) {
    const el = $("#auth-message");
    el.textContent = msg;
    el.className = `auth-message ${type}`;
    el.classList.remove("hidden");
}
function hideAuthMsg() {
    $("#auth-message").classList.add("hidden");
}

function enterMainScreen() {
    showScreen("main-screen");
    $("#username-text").textContent = state.currentUser;
    $("#chat-messages").innerHTML = "";
    addSystemMessage("Welcome! 👋 I'm your AI Loan Processing Agent.\n\nDescribe your loan application in natural language — I'll extract the details, validate your information, calculate your DSR, check your credit profile, and deliver a decision.\n\nTry a quick scenario from the sidebar, or type your own request.");
    checkGeminiStatus();
    resetAgents();
}

// ─── File Upload ─────────────────────────────
async function handleFileUpload(file) {
    if (state.isProcessing) return;
    
    const input = $("#chat-input");
    const userText = input.value.trim() || "Analyze document";
    
    addUserMessage(`📄 Uploading: ${file.name}\n${userText}`);
    addTypingIndicator();
    state.isProcessing = true;
    resetAgents();
    input.value = "";
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("username", state.currentUser);
    formData.append("text", userText);
    
    try {
        console.log(`[Upload] Starting for ${file.name}...`);
        const agentAnimPromise = animateAgents();
        
        const res = await fetch("/loan/upload", {
            method: "POST",
            body: formData
        });
        
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Server error");
        }
        
        const result = await res.json();
        console.log("[Upload] Success:", result);
        
        await agentAnimPromise;
        removeTypingIndicator();
        updateAgentStatuses(result);
        
        if (result.user_message) addSystemMessage(result.user_message);
        addResultCard(result);
        
    } catch (err) {
        console.error("[Upload] Failed:", err);
        removeTypingIndicator();
        resetAgents();
        addSystemMessage(`❌ Upload failed: ${err.message}. Please try again.`);
    } finally {
        state.isProcessing = false;
        $("#file-input").value = "";
        $("#send-btn").disabled = false;
    }
}

// ─── Chat ────────────────────────────────────
function addSystemMessage(text) {
    const wrapper = document.createElement("div");
    wrapper.className = "chat-msg system";
    wrapper.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-body">${escapeHtml(text).replace(/\n/g, "<br>")}</div>
    `;
    $("#chat-messages").appendChild(wrapper);
    scrollChat();
}

function addUserMessage(text) {
    const wrapper = document.createElement("div");
    wrapper.className = "chat-msg user";
    wrapper.innerHTML = `
        <div class="msg-avatar">👤</div>
        <div class="msg-body">${escapeHtml(text).replace(/\n/g, "<br>")}</div>
    `;
    $("#chat-messages").appendChild(wrapper);
    scrollChat();
}

function addTypingIndicator() {
    const wrapper = document.createElement("div");
    wrapper.className = "chat-msg system";
    wrapper.id = "typing-msg";
    wrapper.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-body">
            <div class="typing-indicator"><span></span><span></span><span></span></div>
        </div>
    `;
    $("#chat-messages").appendChild(wrapper);
    scrollChat();
}

function removeTypingIndicator() {
    const el = $("#typing-msg");
    if (el) el.remove();
}

function addResultCard(result) {
    const wrapper = document.createElement("div");
    wrapper.className = "chat-msg system";

    const statusClass = getStatusClass(result.loan_status);
    const statusLabel = result.loan_status || "Processing";
    const dsrValue = parseFloat(result.dsr) || 0;
    const dsrClass = dsrValue >= 60 ? "high" : dsrValue >= 40 ? "medium" : "";
    const dsrWidth = Math.min(dsrValue, 100);

    let financialRows = "";
    const ed = result.extracted_data || {};
    if (ed.income) financialRows += row("Monthly Income", `RM ${fmt(ed.income)}`);
    if (ed.property_price) financialRows += row("Property Price", `RM ${fmt(ed.property_price)}`);
    if (ed.loan_amount) financialRows += row("Loan Amount (90%)", `RM ${fmt(ed.loan_amount)}`);
    if (ed.monthly_installment) financialRows += row("Est. Monthly Installment", `RM ${fmt(ed.monthly_installment)}`);
    if (ed.existing_debt !== undefined) financialRows += row("Existing Debt", `RM ${fmt(ed.existing_debt)}`);
    if (ed.loan_type) financialRows += row("Loan Type", capitalize(ed.loan_type));
    if (ed.employment_status) financialRows += row("Employment", capitalize(ed.employment_status));
    if (ed.employment_duration) financialRows += row("Employment Duration", `${ed.employment_duration} years`);
    if (ed.country) financialRows += row("Jurisdiction", ed.country);

    // Agent trace HTML
    let traceHtml = "";
    (result.agent_trace || []).forEach((a) => {
        traceHtml += `
            <div class="trace-item">
                <div class="trace-dot s-${a.status}"></div>
                <div>
                    <span class="trace-agent">${escapeHtml(a.agent_name)}</span> —
                    <span class="trace-msg">${escapeHtml(a.message)}</span>
                </div>
                <span class="trace-time">${a.duration_ms}ms</span>
            </div>`;
    });

    // JSON output
    const jsonStr = syntaxHighlightJson(JSON.stringify(result, null, 2));

    wrapper.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-body" style="padding:0; border:none; background:none;">
            <div class="result-card">
                <div class="result-header">
                    <span class="result-title">📋 Loan Assessment Result</span>
                    <span class="status-badge ${statusClass}">${escapeHtml(statusLabel)}</span>
                </div>
                <div class="result-body">
                    ${result.loan_status !== "Incomplete" ? `
                    <!-- Risk & DSR -->
                    <div class="result-section">
                        <div class="result-section-title">Risk Assessment</div>
                        ${row("Risk Level", result.risk_level)}
                        ${row("Valuation", capitalize(result.valuation_result || "—"))}
                        ${row("Compliance", result.legal_status || "—")}
                        ${row("Safe Check", result.contract_safe_check || "—")}
                        <div class="dsr-bar-container">
                            <div class="dsr-label-row">
                                <span>Debt Service Ratio</span>
                                <span style="font-weight:700; color: var(--text-primary)">${result.dsr || "—"}</span>
                            </div>
                            <div class="dsr-bar">
                                <div class="dsr-fill ${dsrClass}" style="width: 0%;" data-target="${dsrWidth}"></div>
                            </div>
                        </div>
                    </div>
                    ` : ""}

                    <!-- Financial Details -->
                    ${financialRows ? `
                    <div class="result-section">
                        <div class="result-section-title">Extracted Data</div>
                        ${financialRows}
                    </div>` : ""}

                    <!-- Missing Fields -->
                    ${result.missing_fields && result.missing_fields.length > 0 ? `
                    <div class="result-section">
                        <div class="result-section-title">⚠️ Missing Information</div>
                        <div style="font-size:0.85rem; color:var(--warning); line-height:1.5;">
                            ${result.missing_fields.map(f => `• ${escapeHtml(f)}`).join("<br>")}
                        </div>
                    </div>` : ""}

                    <!-- Next Action -->
                    ${result.next_action ? `
                    <div class="result-section">
                        <div class="result-section-title">Next Action</div>
                        <div class="next-action">${escapeHtml(result.next_action)}</div>
                    </div>` : ""}
                </div>

                <!-- Agent Trace -->
                ${traceHtml ? `
                <button class="trace-toggle" onclick="this.nextElementSibling.classList.toggle('open')">
                    <span>🤖 Agent Trace (${result.agent_trace.length} agents)</span>
                    <span>▾</span>
                </button>
                <div class="trace-content">${traceHtml}</div>` : ""}

                <!-- JSON -->
                <button class="json-toggle" onclick="this.nextElementSibling.classList.toggle('open')">
                    <span>{ }</span> View Raw JSON
                </button>
                <div class="json-content"><pre>${jsonStr}</pre></div>
            </div>
        </div>
    `;

    $("#chat-messages").appendChild(wrapper);
    scrollChat();

    // Animate DSR bar after render
    requestAnimationFrame(() => {
        setTimeout(() => {
            const fill = wrapper.querySelector(".dsr-fill");
            if (fill) fill.style.width = fill.dataset.target + "%";
        }, 200);
    });
}

// ─── Send & Process ──────────────────────────
async function sendMessage() {
    const input = $("#chat-input");
    const text = input.value.trim();
    if (!text || state.isProcessing) return;
    const file = state.selectedFile;

    if (!text && !file) return;
    if (state.isProcessing) return;

    state.isProcessing = true;
    input.value = "";
    input.style.height = "auto";
    $("#send-btn").disabled = true;

    if (file) {
        addUserMessage(`${text ? text + "\n" : ""}📎 Uploaded: ${file.name}`);
    } else {
        addUserMessage(text);
    }
    addTypingIndicator();
    resetAgents();

    try {
        // Start agent animation
        const agentAnimPromise = animateAgents();

        let result;
        if (file) {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("username", state.currentUser);
            formData.append("text", text);
            
            const res = await fetch("/loan/upload", {
                method: "POST",
                body: formData,
            });
            result = await res.json();
            if (!res.ok) throw new Error(result.detail || "Upload failed");
            clearSelectedFile();
        } else {
            result = await api("/loan/process", {
                username: state.currentUser,
                text: text,
            });
        }

        // Wait for animation to catch up
        await agentAnimPromise;

        removeTypingIndicator();

        // Update agent statuses from trace
        updateAgentStatuses(result);

        // System message
        if (result.user_message) {
            addSystemMessage(result.user_message);
        }

        // Result card
        addResultCard(result);

    } catch (err) {
        removeTypingIndicator();
        resetAgents();
        addSystemMessage(`❌ Error: ${err.message}`);
    }

    state.isProcessing = false;
    $("#send-btn").disabled = false;
    input.focus();
}

// ─── Agent Animation ─────────────────────────
function resetAgents() {
    AGENT_KEYS.forEach((key) => {
        const el = $(`#agent-${key}`);
        if (el) el.className = "agent-item";
    });
    $$(".agent-connector").forEach((c) => c.classList.remove("active"));
}

async function animateAgents() {
    const delays = [600, 400, 500, 500, 400, 400, 400];
    const connectors = $$(".agent-connector");

    for (let i = 0; i < AGENT_KEYS.length; i++) {
        const el = $(`#agent-${AGENT_KEYS[i]}`);
        if (el) {
            el.className = "agent-item processing";
            if (connectors[i - 1]) connectors[i - 1].classList.add("active");
        }
        await sleep(delays[i]);
    }
}

function updateAgentStatuses(result) {
    const trace = result.agent_trace || [];
    const connectors = $$(".agent-connector");

    // Reset all first
    AGENT_KEYS.forEach((key) => {
        const el = $(`#agent-${key}`);
        if (el) el.className = "agent-item";
    });
    $$(".agent-connector").forEach((c) => c.classList.remove("active"));

    // Map trace names to our keys
    const nameMap = {
        "Extraction Agent": "extraction",
        "Validation Agent": "validation",
        "Financial Analysis Agent": "financial",
        "Credit Check Agent": "credit",
        "Legal Compliance Agent": "legal",
        "Contract Analysis Agent": "contract",
        "Decision Agent": "decision"
    };

    trace.forEach((t, i) => {
        const key = nameMap[t.agent_name];
        if (key) {
            const el = $(`#agent-${key}`);
            if (el) el.className = `agent-item ${t.status}`;
            
            // Activate connectors up to this agent
            const agentIdx = AGENT_KEYS.indexOf(key);
            for (let j = 0; j < agentIdx; j++) {
                if (connectors[j]) connectors[j].classList.add("active");
            }
        }
    });
}

// ─── New Application ─────────────────────────
async function resetApplication() {
    if (state.currentUser) {
        try {
            await api("/loan/reset", { username: state.currentUser });
        } catch (_) {}
    }
    $("#chat-messages").innerHTML = "";
    resetAgents();
    addSystemMessage("🔄 New application started. Describe your loan request below.");
    $("#chat-input").focus();
}

// ─── API Key ─────────────────────────────────
async function saveApiKey() {
    const key = $("#api-key-input").value.trim();
    if (!key) return;

    const statusEl = $("#api-key-status");
    try {
        await api("/config/api-key", { api_key: key });
        statusEl.className = "api-status success";
        statusEl.textContent = "✓ API key saved successfully!";
        $("#gemini-indicator").classList.add("active");
        $("#gemini-indicator").title = "Gemini API configured";
        setTimeout(() => $("#settings-modal").classList.add("hidden"), 1200);
    } catch (err) {
        statusEl.className = "api-status error";
        statusEl.textContent = `✗ ${err.message}`;
    }
}

async function checkGeminiStatus() {
    try {
        const res = await fetch("/config/status");
        const data = await res.json();
        if (data.gemini_configured) {
            $("#gemini-indicator").classList.add("active");
            $("#gemini-indicator").title = "Gemini API configured";
        } else {
            $("#gemini-indicator").classList.remove("active");
            $("#gemini-indicator").title = "Gemini API not configured — click ⚙️ to set up";
        }
    } catch (_) {}
}

// ─── API Helper ──────────────────────────────
async function api(path, body) {
    const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || "Request failed");
    }
    return data;
}

function clearSelectedFile() {
    state.selectedFile = null;
    $("#file-input").value = "";
    $("#file-preview-container").classList.add("hidden");
}

// ─── Utilities ───────────────────────────────
function scrollChat() {
    const el = $("#chat-messages");
    requestAnimationFrame(() => (el.scrollTop = el.scrollHeight));
}

function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function fmt(n) {
    return Number(n).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function capitalize(s) {
    if (!s) return "—";
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function row(label, value) {
    return `<div class="result-row"><span class="result-label">${escapeHtml(label)}</span><span class="result-value">${escapeHtml(String(value))}</span></div>`;
}

function getStatusClass(status) {
    if (!status) return "incomplete";
    const s = status.toLowerCase();
    if (s.includes("pre-approved") || s.includes("approved")) return "approved";
    if (s.includes("conditional")) return "conditional";
    if (s.includes("rejected")) return "rejected";
    if (s.includes("review")) return "review";
    return "incomplete";
}

function syntaxHighlightJson(json) {
    return escapeHtml(json)
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/: "([^"]*)"/g, ': <span class="json-string">"$1"</span>')
        .replace(/: (\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
        .replace(/: (true|false|null)/g, ': <span class="json-bool">$1</span>');
}
