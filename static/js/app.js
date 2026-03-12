/* ============================
   APP ROUTER & UTILITIES
============================ */

/* ── Toast ─────────────────────────────── */
const Toast = {
  _timer: null,
  show(msg, type = '') {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = `toast ${type} show`;
    clearTimeout(this._timer);
    this._timer = setTimeout(() => { el.className = `toast ${type}`; }, 3800);
  },
  success(msg) { this.show(msg, 'success'); },
  error(msg)   { this.show(msg, 'error'); },
  warning(msg) { this.show(msg, 'warning'); }
};

/* ── Utilities ──────────────────────────── */
function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d   = new Date(dateStr);
    const now = new Date();
    const diff = now - d;
    if (isNaN(diff)) return dateStr;
    if (diff < 0)          return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    if (diff < 60000)      return 'Just now';
    if (diff < 3600000)    return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000)   return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diff < 604800000)  return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return dateStr; }
}

/* ── Router / App ───────────────────────── */
const App = {
  currentPage: 'dashboard',

  pages: {
    dashboard: { title: 'Dashboard',    module: DashboardPage },
    search:    { title: 'Smart Search', module: SearchPage },
    emails:    { title: 'Emails',       module: EmailsPage },
    drafts:    { title: 'AI Drafts',    module: DraftsPage }
  },

  init() {
    this._setupNav();
    this._setupMobile();
    this._checkAccountStatus();
    this.navigate('dashboard');
  },

  _setupNav() {
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.addEventListener('click', () => this.navigate(item.dataset.page));
    });
  },

  _setupMobile() {
    const sidebar  = document.getElementById('sidebar');
    const overlay  = document.getElementById('sidebarOverlay');
    const menuBtn  = document.getElementById('menuBtn');
    const closeBtn = document.getElementById('closeSidebar');

    const openSidebar = () => {
      sidebar.classList.add('open');
      overlay.classList.add('active');
      document.body.style.overflow = 'hidden';
    };
    const closeSidebar = () => {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
      document.body.style.overflow = '';
    };

    if (menuBtn)  menuBtn.addEventListener('click', openSidebar);
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (overlay)  overlay.addEventListener('click', closeSidebar);
  },

  navigate(page) {
    const def = this.pages[page];
    if (!def) return;

    this.currentPage = page;

    // Update active nav
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.classList.toggle('active', item.dataset.page === page);
    });

    // Update topbar title
    const topbarTitle = document.getElementById('topbarTitle');
    if (topbarTitle) topbarTitle.textContent = def.title;

    // Close mobile sidebar
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('sidebarOverlay')?.classList.remove('active');
    document.body.style.overflow = '';

    // Render page
    const content = document.getElementById('pageContent');
    if (!content) return;
    content.innerHTML = '<div class="page-loading"><div class="spinner"></div></div>';

    // Small delay to allow spinner to show, then render
    requestAnimationFrame(() => {
      content.innerHTML = def.module.render();
      def.module.init();
    });
  },

  async _checkAccountStatus() {
    const dot    = document.getElementById('statusDot');
    const email  = document.getElementById('accountEmail');
    const label  = document.getElementById('accountLabel');

    if (dot) dot.className = 'status-dot checking';
    if (label) label.textContent = 'Checking...';

    try {
      const status = await API.getAuthStatus();
      const accounts = status.connected_accounts || [];
      const active   = accounts.filter(a => a.is_active);

      if (active.length > 0) {
        if (dot)   dot.className = 'status-dot connected';
        if (email) email.textContent = active[0].email_address;
        if (label) label.textContent = `${active.length} account${active.length !== 1 ? 's' : ''} connected`;
      } else {
        if (dot)   dot.className = 'status-dot disconnected';
        if (email) email.textContent = 'No account';
        if (label) label.textContent = 'Connect Gmail to start';
      }
    } catch {
      if (dot)   dot.className = 'status-dot disconnected';
      if (email) email.textContent = 'Connection error';
      if (label) label.textContent = 'Check API server';
    }
  }
};

/* ── Boot ───────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => App.init());
