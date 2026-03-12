/* ============================
   DRAFTS PAGE
============================ */
const DraftsPage = {
  _draftId: null,
  _tab: 'create',
  _pendingMsgId: null,

  render() {
    return `
      <div class="page-header animate-in">
        <div class="page-header-text">
          <h1 class="page-title">AI Drafts</h1>
          <p class="page-desc">Generate, review and send AI-powered email replies</p>
        </div>
      </div>

      <div class="tabs">
        <div class="tab-item active" data-tab="create">✍️ Create Draft</div>
        <div class="tab-item" data-tab="history">🗂 Draft History</div>
      </div>

      <div id="tabContent">
        ${this._createTabHtml()}
      </div>
    `;
  },

  _createTabHtml() {
    return `
      <div class="grid-2" style="align-items:start">
        <!-- Left: Form -->
        <div class="card">
          <div class="card-header">
            <span class="card-title">Draft Settings</span>
          </div>
          <div class="card-body">
            <div class="form-group">
              <label class="form-label">Email Message ID</label>
              <input type="number" class="form-input" id="draftMsgId" placeholder="e.g. 42" min="1" />
              <div class="form-hint">Database ID of the email you want to reply to</div>
            </div>

            <div class="form-group">
              <label class="form-label">Tone</label>
              <select class="form-select" id="draftTone">
                <option value="professional" selected>Professional</option>
                <option value="formal">Formal</option>
                <option value="casual">Casual</option>
                <option value="friendly">Friendly</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Length</label>
              <select class="form-select" id="draftLength">
                <option value="short">Short (1-2 sentences)</option>
                <option value="medium" selected>Medium (1-2 paragraphs)</option>
                <option value="detailed">Detailed (multiple paragraphs)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">
                Custom Instructions
                <span style="font-weight:400;color:var(--text-4);margin-left:4px">(optional)</span>
              </label>
              <textarea
                class="form-textarea"
                id="draftInstructions"
                placeholder="e.g. Thank them and confirm the meeting for Thursday at 2pm..."></textarea>
            </div>

            <button class="btn btn-primary" id="generateBtn" style="width:100%">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M12 20h9"/>
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
              </svg>
              Generate AI Draft
            </button>
          </div>
        </div>

        <!-- Right: Preview -->
        <div class="card" style="min-height:380px;display:flex;flex-direction:column">
          <div class="card-header">
            <span class="card-title">Draft Preview</span>
            <div id="safetyBadge"></div>
          </div>
          <div class="card-body" id="draftPreview" style="flex:1">
            <div class="empty-state">
              <span class="empty-icon">✍️</span>
              <div class="empty-title">No draft generated yet</div>
              <div class="empty-desc">Fill in the settings on the left and click "Generate"</div>
            </div>
          </div>
          <div class="card-footer" id="draftActions" style="display:none">
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <button class="btn btn-success" id="approveBtn">✓ Approve &amp; Send</button>
              <button class="btn btn-danger"  id="rejectBtn">✕ Reject</button>
              <button class="btn btn-secondary" id="regenBtn" style="margin-left:auto">↺ Regenerate</button>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  init() {
    this._tab = 'create';
    this._draftId = null;

    document.querySelectorAll('.tab-item').forEach(t => {
      t.addEventListener('click', () => {
        document.querySelectorAll('.tab-item').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        this._tab = t.dataset.tab;
        const content = document.getElementById('tabContent');
        if (this._tab === 'create') {
          content.innerHTML = this._createTabHtml();
          this._bindCreateTab();
        } else {
          content.innerHTML = `<div style="display:flex;justify-content:center;padding:40px"><div class="spinner"></div></div>`;
          this._loadHistory();
        }
      });
    });

    this._bindCreateTab();

    // Auto-fill message ID if navigated here from Emails/Search
    if (this._pendingMsgId) {
      const input = document.getElementById('draftMsgId');
      if (input) {
        input.value = this._pendingMsgId;
        input.focus();
      }
      this._pendingMsgId = null;
    }
  },

  _bindCreateTab() {
    const btn = document.getElementById('generateBtn');
    if (btn) btn.addEventListener('click', () => this._generate());
  },

  async _generate() {
    const msgId = parseInt(document.getElementById('draftMsgId')?.value);
    if (!msgId || msgId < 1) { Toast.warning('Please enter a valid Message ID'); return; }

    const tone         = document.getElementById('draftTone').value;
    const length       = document.getElementById('draftLength').value;
    const instructions = document.getElementById('draftInstructions').value.trim();

    const btn     = document.getElementById('generateBtn');
    const preview = document.getElementById('draftPreview');

    btn.disabled = true;
    btn.innerHTML = '<div class="spinner spinner-sm"></div> Generating...';
    preview.innerHTML = `
      <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:40px;color:var(--text-3)">
        <div class="spinner"></div>
        <div>AI is drafting your reply<span id="dotAnim">...</span></div>
      </div>`;

    // Animate dots
    let dots = 0;
    const dotInterval = setInterval(() => {
      const el = document.getElementById('dotAnim');
      if (el) el.textContent = '.'.repeat((dots++ % 3) + 1);
    }, 500);

    try {
      const result = await API.createDraft(msgId, instructions, tone, length);
      clearInterval(dotInterval);
      this._draftId = result.draft_id;

      // Safety badge
      const safetyEl = document.getElementById('safetyBadge');
      if (safetyEl) {
        safetyEl.innerHTML = result.safety_check?.is_safe
          ? '<span class="badge badge-success">✓ Safe</span>'
          : '<span class="badge badge-warning">⚠ Review</span>';
      }

      const hasErrors = result.errors && result.errors.length > 0;
      const hasFlags  = result.safety_check?.flagged_content?.length > 0;

      preview.innerHTML = `
        <div style="margin-bottom:14px">
          <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.6px;color:var(--text-4);margin-bottom:4px">Subject</div>
          <div style="font-size:14px;font-weight:600;color:var(--text)">${this._esc(result.draft_subject || '(No subject)')}</div>
        </div>
        <div style="height:1px;background:var(--border);margin-bottom:14px"></div>
        <div style="font-size:13.5px;line-height:1.75;color:var(--text-2);white-space:pre-wrap;word-break:break-word">${this._esc(result.draft_text || '')}</div>
        ${hasFlags ? `
          <div class="alert alert-warning" style="margin-top:16px">
            ⚠ Flagged: ${result.safety_check.flagged_content.join(', ')}
          </div>` : ''}
        ${hasErrors ? `
          <div class="alert alert-error" style="margin-top:12px">
            ${this._esc(result.errors[0])}
          </div>` : ''}
        <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--border);display:flex;gap:6px;font-size:12px;color:var(--text-4)">
          <span>Draft ID: ${result.draft_id ?? '—'}</span>
          <span>&middot;</span>
          <span>${result.processing_time ?? 0}s</span>
          <span>&middot;</span>
          <span>${tone} / ${length}</span>
        </div>
      `;

      document.getElementById('draftActions').style.display = '';
      this._bindActions(result);

    } catch (e) {
      clearInterval(dotInterval);
      preview.innerHTML = `<div class="alert alert-error">Generation failed: ${e.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M12 20h9"/>
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
        </svg>
        Generate AI Draft`;
    }
  },

  _bindActions(result) {
    const approveBtn = document.getElementById('approveBtn');
    const rejectBtn  = document.getElementById('rejectBtn');
    const regenBtn   = document.getElementById('regenBtn');

    if (approveBtn) {
      approveBtn.onclick = async () => {
        if (!this._draftId) return;
        approveBtn.disabled = true;
        approveBtn.innerHTML = '<div class="spinner spinner-sm"></div>';
        try {
          await API.approveDraft(this._draftId);
          Toast.success('Draft approved and email sent!');
          document.getElementById('draftActions').style.display = 'none';
          document.getElementById('draftPreview').innerHTML += `
            <div class="alert alert-success" style="margin-top:14px">✓ Email sent successfully!</div>`;
        } catch (e) {
          Toast.error('Approve failed: ' + e.message);
          approveBtn.disabled = false;
          approveBtn.innerHTML = '✓ Approve &amp; Send';
        }
      };
    }

    if (rejectBtn) {
      rejectBtn.onclick = async () => {
        if (!this._draftId) return;
        rejectBtn.disabled = true;
        try {
          await API.rejectDraft(this._draftId);
          Toast.warning('Draft rejected');
          document.getElementById('draftActions').style.display = 'none';
          document.getElementById('draftPreview').innerHTML = `
            <div class="empty-state">
              <span class="empty-icon">🗑</span>
              <div class="empty-title">Draft Rejected</div>
              <div class="empty-desc">Generate a new draft with different settings</div>
            </div>`;
        } catch (e) {
          Toast.error(e.message);
          rejectBtn.disabled = false;
        }
      };
    }

    if (regenBtn) regenBtn.onclick = () => this._generate();
  },

  async _loadHistory() {
    const content = document.getElementById('tabContent');
    if (!content) return;

    try {
      const data   = await API.getDrafts();
      const drafts = data.drafts || (Array.isArray(data) ? data : []);

      if (!drafts.length) {
        content.innerHTML = `
          <div class="empty-state">
            <span class="empty-icon">📝</span>
            <div class="empty-title">No drafts yet</div>
            <div class="empty-desc">Create your first AI-powered draft reply</div>
          </div>`;
        return;
      }

      const statusBadge = {
        pending:        'badge-warning',
        approved:       'badge-success',
        rejected:       'badge-error',
        needs_revision: 'badge-info'
      };

      content.innerHTML = drafts.map(d => `
        <div class="draft-card">
          <div class="draft-header">
            <span class="draft-subject">${this._esc(d.subject || '(No subject)')}</span>
            <span class="badge ${statusBadge[d.approval_status] || 'badge-gray'}">
              ${d.approval_status || 'pending'}
            </span>
          </div>
          <div class="draft-meta">
            To: ${this._esc(d.recipient_email || 'Unknown')}
            &middot; ${d.tone || ''} &middot; ${d.length || ''}
            &middot; ${formatDate(d.created_at)}
          </div>
          <div class="draft-preview">${this._esc(d.body_text || '')}</div>
          <div class="draft-actions">
            ${d.approval_status === 'pending' ? `
              <button class="btn btn-success btn-sm" onclick="DraftsPage._histApprove(${d.id})">✓ Approve</button>
              <button class="btn btn-danger btn-sm"  onclick="DraftsPage._histReject(${d.id})">✕ Reject</button>
            ` : ''}
            <span class="badge ${d.is_sent ? 'badge-success' : 'badge-gray'}" style="margin-left:auto">
              ${d.is_sent ? '✓ Sent' : 'Not sent'}
            </span>
          </div>
        </div>
      `).join('');
    } catch (e) {
      const content = document.getElementById('tabContent');
      if (content) content.innerHTML = `<div class="alert alert-error">Failed to load drafts: ${e.message}</div>`;
    }
  },

  async _histApprove(id) {
    try {
      await API.approveDraft(id);
      Toast.success('Draft approved!');
      this._loadHistory();
    } catch (e) { Toast.error(e.message); }
  },

  async _histReject(id) {
    try {
      await API.rejectDraft(id);
      Toast.warning('Draft rejected');
      this._loadHistory();
    } catch (e) { Toast.error(e.message); }
  },

  // Called from Search and Emails pages
  _openWithId(messageId) {
    this._pendingMsgId = messageId;
    App.navigate('drafts');
  },

  _esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
};
