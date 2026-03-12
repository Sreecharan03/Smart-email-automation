/* ============================
   SEARCH PAGE
============================ */
const SearchPage = {

  render() {
    return `
      <div class="page-header animate-in">
        <div class="page-header-text">
          <h1 class="page-title">Smart Search</h1>
          <p class="page-desc">Natural language search across all your emails</p>
        </div>
      </div>

      <div class="search-box">
        <span class="search-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </span>
        <input
          type="text"
          class="search-input"
          id="searchInput"
          placeholder='Try "emails from John last week" or "invoice payments"...'
          autocomplete="off"
        />
        <button class="btn btn-primary search-btn" id="searchBtn">Search</button>
      </div>

      <div class="suggestion-chips">
        <span class="chip-label">Try:</span>
        ${['meetings last week', 'important invoices', 'emails with attachments', 'from noreply'].map(q => `
          <button class="btn btn-ghost btn-sm" data-query="${q}" style="border:1px solid var(--border)">${q}</button>
        `).join('')}
      </div>

      <div id="searchResults"></div>
    `;
  },

  init() {
    const input = document.getElementById('searchInput');
    const btn   = document.getElementById('searchBtn');

    const doSearch = () => {
      const q = input.value.trim();
      if (q) this._runSearch(q);
    };

    btn.addEventListener('click', doSearch);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

    document.querySelectorAll('[data-query]').forEach(chip => {
      chip.addEventListener('click', () => {
        input.value = chip.dataset.query;
        this._runSearch(chip.dataset.query);
        input.focus();
      });
    });
  },

  async _runSearch(query) {
    const results = document.getElementById('searchResults');
    results.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;color:var(--text-3);padding:20px 0">
        <div class="spinner spinner-sm"></div>
        Searching for "<strong style="color:var(--text)">${this._esc(query)}</strong>"...
      </div>`;

    try {
      const data = await API.searchEmails(query, 2, 20);
      const list = data.results || [];

      if (list.length === 0) {
        results.innerHTML = `
          <div class="empty-state">
            <span class="empty-icon">🔍</span>
            <div class="empty-title">No results found</div>
            <div class="empty-desc">Try different keywords or a broader query</div>
          </div>`;
        return;
      }

      const typeBadge = { keyword: 'badge-info', semantic: 'badge-primary', hybrid: 'badge-success' };

      results.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
          <span style="font-size:13px;color:var(--text-3)">
            ${list.length} result${list.length !== 1 ? 's' : ''} &middot; ${data.processing_time ?? 0}s
          </span>
          <span class="badge ${typeBadge[data.search_type] || 'badge-gray'}">${data.search_type || 'search'}</span>
        </div>

        ${list.map(r => `
          <div class="result-card">
            <div class="result-header">
              <span class="result-subject">${this._esc(r.subject || '(No Subject)')}</span>
              <span class="result-score">Score: ${r.relevance_score ?? '—'}</span>
            </div>
            <div class="result-meta">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              ${this._esc(r.sender_email || 'Unknown')}
              &middot;
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="4" width="18" height="18" rx="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              ${formatDate(r.date_sent)}
              ${r.has_attachments ? '<span class="badge badge-gray">📎 Attachment</span>' : ''}
            </div>
            <div class="result-snippet">${this._esc(r.snippet || '')}</div>
            <div style="display:flex;align-items:center;gap:8px;margin-top:10px">
              <span class="badge ${typeBadge[r.search_type] || 'badge-gray'}">${r.search_type}</span>
              <button
                class="btn btn-ghost btn-sm"
                style="margin-left:auto"
                onclick="DraftsPage._openWithId(${r.message_id}, '${this._escAttr(r.subject || '')}')">
                ✍️ Draft Reply
              </button>
            </div>
          </div>
        `).join('')}
      `;
    } catch (e) {
      results.innerHTML = `<div class="alert alert-error">Search failed: ${e.message}</div>`;
    }
  },

  _esc(str) {
    if (!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  },

  _escAttr(str) {
    return String(str || '').replace(/'/g, '').replace(/"/g, '');
  }
};
