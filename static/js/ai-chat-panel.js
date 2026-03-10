/**
 * AI Chat Panel - Reusable component for context-aware AI project management chat.
 * Embeds in milestone modals, risk views, and schedule pages.
 * Supports conversation continuity across tabs, action proposals, and token tracking.
 */
class AIChatPanel {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.contextType = options.contextType || 'general';
        this.contextId = options.contextId || '';
        this.projectCode = options.projectCode || '';
        this.programName = options.programName || '';
        this.tableId = options.tableId || '';
        this.conversationId = null;
        this.totalTokens = 0;
        this.contextWindow = 200000;
        this.isLoading = false;
        this.onActionExecuted = options.onActionExecuted || null;

        this._render();
        this._bindEvents();
        this._checkStatus();
    }

    // ── Render ────────────────────────────────────────────────

    _render() {
        this.container.innerHTML = `
        <div class="ai-chat-panel" id="aiChatPanelRoot">
            <!-- Toggle Button -->
            <button class="ai-chat-toggle" id="aiChatToggle" title="AI Assistant">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
                </svg>
                <span>AI Assistant</span>
            </button>

            <!-- Chat Body (collapsed by default) -->
            <div class="ai-chat-body hidden" id="aiChatBody">
                <!-- Header -->
                <div class="ai-chat-header">
                    <div class="ai-chat-header-left">
                        <span class="ai-chat-title">🤖 AI Assistant</span>
                        <span class="ai-chat-token-text" id="aiTokenText">–</span>
                    </div>
                    <div class="ai-chat-header-right">
                        <button class="ai-chat-btn-sm" id="aiNewConvBtn" title="Start new conversation" style="display:none;">
                            ↻ New
                        </button>
                        <button class="ai-chat-btn-sm ai-chat-collapse-btn" id="aiCollapseBtn" title="Collapse">
                            ▾
                        </button>
                    </div>
                </div>

                <!-- Token Bar -->
                <div class="ai-chat-token-bar">
                    <div class="ai-chat-token-fill" id="aiTokenFill" style="width:0%"></div>
                </div>

                <!-- Staleness Warning -->
                <div class="ai-chat-staleness hidden" id="aiStaleness">
                    ⚠️ Context getting full. Consider starting a new conversation.
                </div>

                <!-- Quick Actions -->
                <div class="ai-chat-quick-actions" id="aiQuickActions"></div>

                <!-- Messages -->
                <div class="ai-chat-messages" id="aiChatMessages">
                    <div class="ai-chat-welcome">
                        <p>Ask me about risks, timelines, dependencies, critical paths, or tell me to add tasks and update tables.</p>
                    </div>
                </div>

                <!-- Not Configured Banner -->
                <div class="ai-chat-not-configured hidden" id="aiNotConfigured">
                    <p>⚙️ AI chat not configured. Set <code>ANTHROPIC_API_KEY</code> environment variable.</p>
                </div>

                <!-- Input -->
                <div class="ai-chat-input-area">
                    <input type="text" class="ai-chat-input" id="aiChatInput"
                           placeholder="Ask about this item..."
                           autocomplete="off">
                    <button class="ai-chat-send-btn" id="aiChatSendBtn" title="Send">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>`;

        this._setupQuickActions();
    }

    _setupQuickActions() {
        const container = this.container.querySelector('#aiQuickActions');
        if (!container) return;

        const actions = this._getQuickActions();
        container.innerHTML = actions.map(a =>
            `<button class="ai-quick-action-btn" data-prompt="${this._escapeAttr(a.prompt)}" title="${a.label}">
                ${a.icon} ${a.label}
            </button>`
        ).join('');

        container.querySelectorAll('.ai-quick-action-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const prompt = btn.dataset.prompt;
                this._setInput(prompt);
                this.sendMessage(prompt);
            });
        });
    }

    _getQuickActions() {
        switch (this.contextType) {
            case 'milestone':
                return [
                    { icon: '📋', label: 'Suggest Subtasks', prompt: 'Suggest subtasks for this milestone and propose adding them.' },
                    { icon: '⚠️', label: 'Analyze Risks', prompt: 'Analyze the risks related to this milestone. What could go wrong and what should we mitigate?' },
                    { icon: '📅', label: 'Review Timeline', prompt: 'Review the timeline for this milestone. Is it realistic? Are there any scheduling conflicts or dependencies to watch?' },
                    { icon: '🔗', label: 'Check Dependencies', prompt: 'What are the dependencies for this milestone? Are there any critical path items?' },
                ];
            case 'risk':
                return [
                    { icon: '🛡️', label: 'Suggest Mitigations', prompt: 'Suggest mitigation strategies for this risk.' },
                    { icon: '📦', label: 'Create Work Package', prompt: 'Create a mitigation work package - propose milestone tasks that when completed will mitigate this risk.' },
                    { icon: '📊', label: 'Risk Assessment', prompt: 'Provide a detailed risk assessment including impact analysis and likelihood evaluation.' },
                ];
            case 'schedule':
                return [
                    { icon: '➕', label: 'Add Item', prompt: 'I want to add a new item to this table. Ask me for the details.' },
                    { icon: '📊', label: 'Analyze Table', prompt: 'Analyze this schedule table. What items are overdue? What needs attention?' },
                    { icon: '📋', label: 'Suggest Columns', prompt: 'Based on the table structure, suggest any additional columns that would improve tracking.' },
                ];
            default:
                return [
                    { icon: '📊', label: 'Project Status', prompt: 'Give me a status overview of this project including key risks and upcoming milestones.' },
                    { icon: '⚠️', label: 'Key Risks', prompt: 'What are the top risks across the portfolio?' },
                ];
        }
    }

    // ── Events ────────────────────────────────────────────────

    _bindEvents() {
        const toggle = this.container.querySelector('#aiChatToggle');
        const collapse = this.container.querySelector('#aiCollapseBtn');
        const input = this.container.querySelector('#aiChatInput');
        const sendBtn = this.container.querySelector('#aiChatSendBtn');
        const newConvBtn = this.container.querySelector('#aiNewConvBtn');

        if (toggle) toggle.addEventListener('click', () => this._togglePanel());
        if (collapse) collapse.addEventListener('click', () => this._togglePanel());
        if (input) input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage(input.value);
            }
        });
        if (sendBtn) sendBtn.addEventListener('click', () => {
            const input = this.container.querySelector('#aiChatInput');
            if (input) this.sendMessage(input.value);
        });
        if (newConvBtn) newConvBtn.addEventListener('click', () => this.startNewConversation());
    }

    _togglePanel() {
        const body = this.container.querySelector('#aiChatBody');
        const toggle = this.container.querySelector('#aiChatToggle');
        if (!body) return;

        const isHidden = body.classList.contains('hidden');
        body.classList.toggle('hidden');
        if (toggle) toggle.style.display = isHidden ? 'none' : 'flex';

        if (isHidden) {
            this._loadExistingConversation();
            const input = this.container.querySelector('#aiChatInput');
            if (input) setTimeout(() => input.focus(), 100);
        }
    }

    // ── API Calls ─────────────────────────────────────────────

    async _checkStatus() {
        try {
            const resp = await fetch('/api/ai/status');
            const data = await resp.json();
            if (!data.configured) {
                const banner = this.container.querySelector('#aiNotConfigured');
                const inputArea = this.container.querySelector('.ai-chat-input-area');
                if (banner) banner.classList.remove('hidden');
                if (inputArea) inputArea.style.display = 'none';
            }
            this.contextWindow = data.context_window || 200000;
        } catch (e) {
            console.warn('AI status check failed:', e);
        }
    }

    async _loadExistingConversation() {
        if (this.conversationId) return;
        if (!this.contextId) return;

        try {
            const params = new URLSearchParams({
                context_type: this.contextType,
                context_id: this.contextId,
            });
            const resp = await fetch(`/api/ai/conversations?${params}`);
            const data = await resp.json();

            if (data.conversations && data.conversations.length > 0) {
                const conv = data.conversations[0];
                // If it has an id and messages, load full conversation
                const convId = conv.id;
                const fullResp = await fetch(`/api/ai/conversations/${convId}`);
                const fullConv = await fullResp.json();

                this.conversationId = convId;
                this.totalTokens = fullConv.total_tokens || 0;
                this._renderHistory(fullConv.messages || []);
                this._updateTokenCounter();
            }
        } catch (e) {
            console.warn('Failed to load existing conversation:', e);
        }
    }

    async sendMessage(text) {
        text = (text || '').trim();
        if (!text || this.isLoading) return;

        this.isLoading = true;
        this._setInput('');
        this._appendMessage('user', text);
        this._showTypingIndicator();

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
                       || document.getElementById('csrfToken')?.value || '';

        try {
            const resp = await fetch('/api/ai/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-csrf-token': csrfToken,
                },
                body: JSON.stringify({
                    conversation_id: this.conversationId,
                    message: text,
                    context_type: this.contextType,
                    context_id: this.contextId,
                    project_code: this.projectCode,
                    program_name: this.programName,
                    table_id: this.tableId,
                }),
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }

            const data = await resp.json();
            this.conversationId = data.conversation_id;
            this.totalTokens = data.total_tokens_used || 0;

            this._removeTypingIndicator();
            this._appendMessage('assistant', data.reply);

            // Show action proposals if any
            if (data.proposed_actions && data.proposed_actions.length > 0) {
                this._renderActionProposals(data.proposed_actions);
            }

            // Update token counter and staleness
            this._updateTokenCounter();
            if (data.staleness && data.staleness.staleness_warning) {
                this._showStaleness(data.staleness.suggest_new_conversation);
            }
        } catch (e) {
            this._removeTypingIndicator();
            this._appendMessage('error', `Error: ${e.message}`);
        } finally {
            this.isLoading = false;
        }
    }

    async executeActions(actions) {
        if (!this.conversationId || !actions.length) return;

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content
                       || document.getElementById('csrfToken')?.value || '';

        try {
            const resp = await fetch('/api/ai/actions/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-csrf-token': csrfToken,
                },
                body: JSON.stringify({
                    conversation_id: this.conversationId,
                    actions: actions,
                }),
            });

            const data = await resp.json();
            this._appendMessage('assistant',
                '✅ Actions executed:\n' + data.results.map(r =>
                    `${r.success ? '✓' : '✗'} ${r.message}`
                ).join('\n')
            );

            if (this.onActionExecuted) {
                this.onActionExecuted(data.results);
            }

            return data.results;
        } catch (e) {
            this._appendMessage('error', `Failed to execute actions: ${e.message}`);
        }
    }

    async startNewConversation() {
        this.conversationId = null;
        this.totalTokens = 0;
        const msgs = this.container.querySelector('#aiChatMessages');
        if (msgs) {
            msgs.innerHTML = `<div class="ai-chat-welcome">
                <p>New conversation started. Ask me anything about this item.</p>
            </div>`;
        }
        this._updateTokenCounter();
        this._hideStaleness();
        const newBtn = this.container.querySelector('#aiNewConvBtn');
        if (newBtn) newBtn.style.display = 'none';
    }

    // ── Update Context (for switching entities within same panel) ──

    updateContext(options) {
        this.contextType = options.contextType || this.contextType;
        this.contextId = options.contextId || this.contextId;
        this.projectCode = options.projectCode || this.projectCode;
        this.programName = options.programName || this.programName;
        this.tableId = options.tableId || this.tableId;
        this.conversationId = null;
        this.totalTokens = 0;

        const msgs = this.container.querySelector('#aiChatMessages');
        if (msgs) {
            msgs.innerHTML = `<div class="ai-chat-welcome">
                <p>Ask me about risks, timelines, dependencies, critical paths, or tell me to add tasks and update tables.</p>
            </div>`;
        }
        this._updateTokenCounter();
        this._hideStaleness();
        this._setupQuickActions();

        // Auto-load existing conversation for new context
        const body = this.container.querySelector('#aiChatBody');
        if (body && !body.classList.contains('hidden')) {
            this._loadExistingConversation();
        }
    }

    // ── Rendering Helpers ─────────────────────────────────────

    _appendMessage(role, content) {
        const msgs = this.container.querySelector('#aiChatMessages');
        if (!msgs) return;

        // Remove welcome message on first real message
        const welcome = msgs.querySelector('.ai-chat-welcome');
        if (welcome) welcome.remove();

        const div = document.createElement('div');
        div.className = `ai-chat-msg ai-chat-msg-${role}`;

        if (role === 'assistant') {
            div.innerHTML = this._renderMarkdown(content);
        } else if (role === 'error') {
            div.innerHTML = `<span class="ai-chat-error">${this._escapeHtml(content)}</span>`;
        } else {
            div.textContent = content;
        }

        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
    }

    _renderHistory(messages) {
        const msgs = this.container.querySelector('#aiChatMessages');
        if (!msgs) return;
        msgs.innerHTML = '';

        if (messages.length === 0) {
            msgs.innerHTML = `<div class="ai-chat-welcome">
                <p>Ask me about risks, timelines, dependencies, critical paths, or tell me to add tasks and update tables.</p>
            </div>`;
            return;
        }

        for (const m of messages) {
            this._appendMessage(m.role, m.content);
        }
    }

    _renderActionProposals(actions) {
        const msgs = this.container.querySelector('#aiChatMessages');
        if (!msgs) return;

        const div = document.createElement('div');
        div.className = 'ai-chat-action-proposal';

        const actionDescriptions = actions.map((a, i) => {
            const params = a.params || {};
            let desc = `<strong>${a.action}</strong>`;
            if (params.name) desc += `: ${this._escapeHtml(params.name)}`;
            if (params.title) desc += `: ${this._escapeHtml(params.title)}`;
            return `<div class="ai-action-item">${desc}</div>`;
        }).join('');

        div.innerHTML = `
            <div class="ai-action-header">📋 Proposed Actions (${actions.length})</div>
            ${actionDescriptions}
            <div class="ai-action-buttons">
                <button class="ai-action-accept" data-actions='${JSON.stringify(actions).replace(/'/g, "&#39;")}'>
                    ✓ Accept & Execute
                </button>
                <button class="ai-action-reject">✗ Dismiss</button>
            </div>`;

        div.querySelector('.ai-action-accept').addEventListener('click', (e) => {
            const actionsData = JSON.parse(e.target.dataset.actions);
            this.executeActions(actionsData);
            div.remove();
        });

        div.querySelector('.ai-action-reject').addEventListener('click', () => {
            div.remove();
            this._appendMessage('assistant', 'Actions dismissed.');
        });

        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
    }

    _showTypingIndicator() {
        const msgs = this.container.querySelector('#aiChatMessages');
        if (!msgs) return;
        const div = document.createElement('div');
        div.className = 'ai-chat-typing';
        div.id = 'aiTypingIndicator';
        div.innerHTML = '<span></span><span></span><span></span>';
        msgs.appendChild(div);
        msgs.scrollTop = msgs.scrollHeight;
    }

    _removeTypingIndicator() {
        const el = this.container.querySelector('#aiTypingIndicator');
        if (el) el.remove();
    }

    _updateTokenCounter() {
        const text = this.container.querySelector('#aiTokenText');
        const fill = this.container.querySelector('#aiTokenFill');
        const newBtn = this.container.querySelector('#aiNewConvBtn');
        if (!text || !fill) return;

        const ratio = this.totalTokens / this.contextWindow;
        const pct = Math.min(100, ratio * 100);
        const k = Math.round(this.totalTokens / 1000);

        text.textContent = `${k}k / ${Math.round(this.contextWindow / 1000)}k tokens`;
        fill.style.width = `${pct}%`;

        // Color coding
        fill.classList.remove('token-green', 'token-amber', 'token-red');
        if (ratio < 0.5) fill.classList.add('token-green');
        else if (ratio < 0.75) fill.classList.add('token-amber');
        else fill.classList.add('token-red');

        if (newBtn) newBtn.style.display = ratio >= 0.75 ? 'inline-flex' : 'none';
    }

    _showStaleness(critical) {
        const el = this.container.querySelector('#aiStaleness');
        if (el) {
            el.classList.remove('hidden');
            if (critical) {
                el.textContent = '🔴 Context window nearly full. Start a new conversation for best results.';
                el.classList.add('ai-staleness-critical');
            }
        }
    }

    _hideStaleness() {
        const el = this.container.querySelector('#aiStaleness');
        if (el) {
            el.classList.add('hidden');
            el.classList.remove('ai-staleness-critical');
        }
    }

    _setInput(val) {
        const input = this.container.querySelector('#aiChatInput');
        if (input) input.value = val;
    }

    // ── Markdown Rendering (lightweight) ──────────────────────

    _renderMarkdown(text) {
        let html = this._escapeHtml(text);

        // Code blocks (```...```)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Bold
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // Italic
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        // Bullet lists
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
        // Numbered lists
        html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
        // Headers
        html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
        // Line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    _escapeAttr(str) {
        return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
}

// Make globally available
window.AIChatPanel = AIChatPanel;
