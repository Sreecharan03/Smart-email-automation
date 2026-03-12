/* ============================
   DASHBOARD PAGE
============================ */
const DashboardPage = {

  render() {
    return `
      <div class="page-header animate-in">
        <div class="page-header-text">
          <h1 class="page-title">Dashboard</h1>
          <p class="page-desc">Overview of your AI Email Assistant</p>
        </div>
        <button class="btn btn-primary" id="syncBtn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="23 4 23 10 17 10"/>
            <polyline points="1 20 1 14 7 14"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          Sync Now
        </button>
      </div>

      <!-- Stats -->
      <div class="stats-grid" id="statsGrid">
        ${this._skeletonStats()}
      </div>

      <!-- Accounts + Quick Actions -->
      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <span class="card-title">Connected Accounts</span>
            <div style="display:flex;gap:6px">
              <button class="btn btn-secondary btn-sm" id="copyAuthUrlBtn" title="Copy auth URL to paste in another browser profile">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
                Copy URL
              </button>
              <button class="btn btn-primary btn-sm" id="connectGmailBtn">+ Connect Gmail</button>
            </div>
          </div>
          <div class="card-body" id="accountsList" style="padding:0">
            <div style="display:flex;justify-content:center;padding:32px">
              <div class="spinner"></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <span class="card-title">Quick Actions</span>
          </div>
          <div class="card-body" style="display:flex;flex-direction:column;gap:10px">
            <button class="btn btn-secondary" onclick="App.navigate('search')" style="width:100%">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              Smart Search
            </button>
            <button class="btn btn-secondary" onclick="App.navigate('emails')" style="width:100%">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                <polyline points="22,6 12,13 2,6"/>
              </svg>
              View Emails
            </button>
            <button class="btn btn-secondary" onclick="App.navigate('drafts')" style="width:100%">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 20h9"/>
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
              </svg>
              Create AI Draft
            </button>
            <a href="/docs" target="_blank" class="btn btn-ghost" style="width:100%">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              API Documentation
            </a>
          </div>
        </div>
      </div>
    `;
  },

  _skeletonStats() {
    const colors = ['#4F46E5','#059669','#D97706','#0284C7'];
    return colors.map(c => `
      <div class="stat-card" style="--stat-color:${c}">
        <div class="skeleton" style="width:36px;height:36px;border-radius:8px;margin-bottom:12px"></div>
        <div class="skeleton" style="width:60%;height:28px;margin-bottom:8px"></div>
        <div class="skeleton" style="width:80%;height:13px"></div>
      </div>
    `).join('');
  },

  async init() {
    await Promise.all([this._loadStats(), this._loadAccounts()]);
    this._setupActions();
  },

  async _loadStats() {
    try {
      const data = await API.getStats();
      const grid = document.getElementById('statsGrid');
      if (!grid) return;

      const statsConfig = [
        { label: 'Total Emails',       value: data.messages?.total   ?? data.total_emails   ?? data.emails_count ?? 0, color: '#4F46E5', icon: '📧' },
        { label: 'Accounts Connected', value: data.accounts?.active  ?? data.total_accounts ?? 0,                      color: '#059669', icon: '🔗' },
        { label: 'AI Drafts Created',  value: data.drafts?.total     ?? data.total_drafts   ?? 0,                      color: '#D97706', icon: '✍️' },
        { label: 'Emails Today',       value: data.emails_today      ?? 0,                                             color: '#0284C7', icon: '📅' },
      ];

      grid.innerHTML = statsConfig.map(s => `
        <div class="stat-card" style="--stat-color:${s.color}">
          <div class="stat-icon" style="background:${s.color}18">${s.icon}</div>
          <div class="stat-value">${Number(s.value).toLocaleString()}</div>
          <div class="stat-label">${s.label}</div>
        </div>
      `).join('');
    } catch (e) {
      const grid = document.getElementById('statsGrid');
      if (grid) grid.innerHTML = `
        <div class="alert alert-error" style="grid-column:1/-1">
          Could not load stats: ${e.message}
        </div>`;
    }
  },

  async _loadAccounts() {
    const el = document.getElementById('accountsList');
    if (!el) return;

    try {
      const status = await API.getAuthStatus();
      const accounts = status.connected_accounts || [];

      if (accounts.length === 0) {
        el.innerHTML = `
          <div class="empty-state">
            <span class="empty-icon">📭</span>
            <div class="empty-title">No accounts connected</div>
            <div class="empty-desc">Click "+ Connect Gmail" to get started</div>
          </div>`;
        return;
      }

      el.innerHTML = accounts.map(acc => `
        <div style="display:flex;align-items:center;gap:12px;padding:12px 20px;border-bottom:1px solid var(--border)">
          <div class="email-avatar">${(acc.email_address || 'U').charAt(0).toUpperCase()}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${acc.email_address}</div>
            <div style="font-size:11px;color:var(--text-4);margin-top:1px">${acc.provider || 'gmail'} &middot; ${acc.token_status || 'active'}</div>
          </div>
          <span class="badge ${acc.is_active ? 'badge-success' : 'badge-error'}">
            ${acc.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
      `).join('') + `
        <div style="padding:12px 20px">
          <div style="font-size:12px;color:var(--text-4)">${accounts.length} account${accounts.length !== 1 ? 's' : ''} connected</div>
        </div>`;
    } catch (e) {
      el.innerHTML = `<div class="card-body"><div class="alert alert-error">Failed to load accounts: ${e.message}</div></div>`;
    }
  },

  _setupActions() {
    // Connect Gmail — opens in new tab (current profile)
    const connectBtn = document.getElementById('connectGmailBtn');
    if (connectBtn) {
      connectBtn.addEventListener('click', async () => {
        connectBtn.disabled = true;
        try {
          const data = await API.startGmailAuth();
          if (data.authorization_url) {
            window.open(data.authorization_url, '_blank');
            Toast.success('Gmail auth page opened in new tab');
          }
        } catch (e) {
          Toast.error('Failed to start Gmail auth: ' + e.message);
        } finally {
          connectBtn.disabled = false;
        }
      });
    }

    // Copy Auth URL — for pasting in a different browser profile
    const copyBtn = document.getElementById('copyAuthUrlBtn');
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        copyBtn.disabled = true;
        const orig = copyBtn.innerHTML;
        try {
          const data = await API.startGmailAuth();
          if (data.authorization_url) {
            await navigator.clipboard.writeText(data.authorization_url);
            copyBtn.innerHTML = `
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              Copied!`;
            Toast.success('Auth URL copied! Paste it in your other Gmail browser profile.');
            setTimeout(() => { copyBtn.innerHTML = orig; copyBtn.disabled = false; }, 2500);
          }
        } catch (e) {
          Toast.error('Failed to copy URL: ' + e.message);
          copyBtn.innerHTML = orig;
          copyBtn.disabled = false;
        }
      });
    }

    // Sync
    const syncBtn = document.getElementById('syncBtn');
    if (syncBtn) {
      syncBtn.addEventListener('click', async () => {
        syncBtn.disabled = true;
        syncBtn.innerHTML = '<div class="spinner spinner-sm"></div> Syncing...';
        try {
          const result = await API.syncEmails(2, 50);
          const stored = result.emails_stored ?? result.stored ?? 0;
          Toast.success(`Synced ${stored} new email${stored !== 1 ? 's' : ''}`);
          this._loadStats();
        } catch (e) {
          Toast.error('Sync failed: ' + e.message);
        } finally {
          syncBtn.disabled = false;
          syncBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="23 4 23 10 17 10"/>
              <polyline points="1 20 1 14 7 14"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            Sync Now`;
        }
      });
    }
  }
};
