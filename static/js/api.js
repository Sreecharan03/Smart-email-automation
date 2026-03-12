/* ============================
   API CLIENT
   All calls to FastAPI backend
============================ */

const USER_ID = 'demo_user_btechproject';

const API = {
  _headers() {
    return {
      'Content-Type': 'application/json',
      'X-User-ID': USER_ID
    };
  },

  async _get(path, params = {}) {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== undefined && v !== null))
    ).toString();
    const url = qs ? `${path}?${qs}` : path;
    const res = await fetch(url, { headers: this._headers() });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || `Request failed (${res.status})`);
    }
    return res.json();
  },

  async _post(path, body = {}) {
    const res = await fetch(path, {
      method: 'POST',
      headers: this._headers(),
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || err.message || `Request failed (${res.status})`);
    }
    return res.json();
  },

  // ── Auth ──────────────────────────────────
  getAuthStatus()       { return this._get('/api/auth/status'); },
  startGmailAuth()      { return this._get('/api/auth/gmail'); },
  getAuthHealth()       { return this._get('/api/auth/health'); },

  // ── Stats ─────────────────────────────────
  getStats()            { return this._get('/api/stats'); },

  // ── Emails ────────────────────────────────
  getRecentEmails(limit = 50) {
    return this._get('/api/emails', { limit });
  },

  syncEmails(accountId = 2, maxEmails = 50) {
    return this._post('/api/sync', { account_id: accountId, max_emails: maxEmails });
  },

  // ── Search ────────────────────────────────
  searchEmails(query, accountId = 2, maxResults = 20) {
    return this._post('/api/search', {
      query,
      account_id: accountId,
      max_results: maxResults
    });
  },

  getRecentSearches() { return this._get('/api/search/recent'); },

  // ── Drafts ────────────────────────────────
  createDraft(originalMessageId, userInstructions = '', tone = 'professional', length = 'medium') {
    return this._post('/api/drafts', {
      original_message_id: originalMessageId,
      user_instructions: userInstructions,
      tone,
      length
    });
  },

  getDrafts()          { return this._get('/api/drafts'); },
  getDraft(id)         { return this._get(`/api/drafts/${id}`); },
  approveDraft(id)     { return this._post(`/api/drafts/${id}/approve`); },
  rejectDraft(id)      { return this._post(`/api/drafts/${id}/reject`); },

  editDraft(id, body)  { return this._post(`/api/drafts/${id}/edit`, body); },

  // ── Health ────────────────────────────────
  healthCheck()        { return this._get('/health'); }
};
