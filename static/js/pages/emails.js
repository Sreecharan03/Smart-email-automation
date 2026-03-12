/* ============================
   EMAILS PAGE
============================ */
const EmailsPage = {

  render() {
    return `
      <div class="page-header animate-in">
        <div class="page-header-text">
          <h1 class="page-title">Recent Emails</h1>
          <p class="page-desc">Your latest synced emails</p>
        </div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <select class="form-select" id="limitSelect" style="width:auto">
            <option value="25">25 emails</option>
            <option value="50" selected>50 emails</option>
            <option value="100">100 emails</option>
          </select>
          <button class="btn btn-primary" id="loadBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 .49-3.47"/>
            </svg>
            Reload
          </button>
        </div>
      </div>

      <div class="card" id="emailsContainer">
        <div style="display:flex;justify-content:center;padding:48px">
          <div class="spinner"></div>
        </div>
      </div>
    `;
  },

  async init() {
    await this._loadEmails(50);

    document.getElementById('loadBtn').addEventListener('click', () => {
      const limit = parseInt(document.getElementById('limitSelect').value);
      this._loadEmails(limit);
    });
  },

  async _loadEmails(limit = 50) {
    const container = document.getElementById('emailsContainer');
    if (!container) return;

    container.innerHTML = `
      <div style="display:flex;justify-content:center;padding:48px">
        <div class="spinner"></div>
      </div>`;

    try {
      let raw = await API.getRecentEmails(limit);
      // Handle both list and dict responses
      let emails = Array.isArray(raw) ? raw : (raw.emails || raw.data || []);

      if (emails.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <span class="empty-icon">📭</span>
            <div class="empty-title">No emails yet</div>
            <div class="empty-desc">Sync your Gmail first to see emails here</div>
          </div>`;
        return;
      }

      container.innerHTML = `
        <div style="padding:12px 20px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:12px;color:var(--text-3)">
          Showing ${emails.length} email${emails.length !== 1 ? 's' : ''}
        </div>
        <div class="email-list">
          ${emails.map((e, i) => this._renderRow(e, i)).join('')}
        </div>`;

      // Click to open draft
      container.querySelectorAll('.email-row').forEach(row => {
        row.addEventListener('click', () => {
          const idx = parseInt(row.dataset.idx);
          this._onEmailClick(emails[idx]);
        });
      });

    } catch (e) {
      container.innerHTML = `
        <div class="card-body">
          <div class="alert alert-error">Failed to load emails: ${e.message}</div>
        </div>`;
    }
  },

  _renderRow(e, i) {
    const sender    = e.sender_name || e.sender_email || e.from || 'Unknown';
    const email     = e.sender_email || e.from || '';
    const subject   = e.subject || '(No subject)';
    const snippet   = e.snippet || e.preview || '';
    const date      = e.date_sent || e.date || '';
    const labels    = Array.isArray(e.labels) ? e.labels : [];
    const avatar    = (email || sender).charAt(0).toUpperCase();
    const hasAttach = e.has_attachments || false;

    return `
      <div class="email-row" data-idx="${i}">
        <div class="email-avatar">${avatar}</div>
        <div class="email-body">
          <div class="email-top">
            <span class="email-sender">${this._esc(sender)}</span>
            <span class="email-date">${formatDate(date)}</span>
          </div>
          <div class="email-subject">${this._esc(subject)}</div>
          <div class="email-snippet">${this._esc(snippet)}</div>
          <div style="margin-top:4px;display:flex;gap:6px;align-items:center;flex-wrap:wrap">
            <span style="font-size:10px;color:var(--text-4);background:var(--surface-2);border:1px solid var(--border);border-radius:4px;padding:1px 6px;font-family:monospace">ID: ${e.id || '—'}</span>
            ${hasAttach ? '<span class="badge badge-gray">📎</span>' : ''}
            ${labels.slice(0,3).map(l => `<span class="badge badge-gray" style="font-size:10px">${l}</span>`).join('')}
          </div>
        </div>
        <div style="margin-left:auto;padding-left:8px;flex-shrink:0">
          <button
            class="btn btn-ghost btn-sm"
            title="Draft Reply"
            onclick="event.stopPropagation();DraftsPage._openWithId(${e.id || e.message_id || 0}, '')">
            ✍️
          </button>
        </div>
      </div>`;
  },

  _onEmailClick(email) {
    const id = email.id || email.message_id;
    if (id) DraftsPage._openWithId(id, email.subject || '');
  },

  _esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
};
