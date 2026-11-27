(function () {
  const csrf = document.querySelector('meta[name=csrf-token]')?.content || '';
  window.CSRF = csrf;
  window.api = (url, opts = {}) => fetch(url, Object.assign({credentials: 'same-origin'}, opts, {
    headers: Object.assign({'X-CSRFToken': csrf, 'X-Requested-With': 'fetch'}, opts.headers || {})
  })).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });

  const box = document.getElementById('toasts');
  window.toast = (msg, cat) => {
    if (!box) return;
    const color = {success: 'success', danger: 'danger', warning: 'warning', info: 'primary'}[cat] || 'primary';
    const el = document.createElement('div');
    el.className = `toast align-items-center text-bg-${color} border-0`;
    el.innerHTML = '<div class="d-flex"><div class="toast-body"></div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>';
    el.querySelector('.toast-body').textContent = msg;
    box.appendChild(el);
    new bootstrap.Toast(el, {delay: cat === 'danger' ? 8000 : 4500}).show();
  };
  try { JSON.parse(document.getElementById('flash-data')?.textContent || '[]').forEach(m => toast(m[1], m[0])); } catch (e) {}

  const loading = document.getElementById('loading');
  window.addEventListener('pageshow', () => loading && (loading.style.display = 'none'));
  const cm = document.getElementById('confirmModal');
  let pending = null;
  document.addEventListener('submit', e => {
    const f = e.target;
    if (f.dataset.confirm && !f.dataset.ok) {
      e.preventDefault(); pending = f;
      document.getElementById('confirmText').textContent = f.dataset.confirm;
      bootstrap.Modal.getOrCreateInstance(cm).show();
      return;
    }
    if (!f.hasAttribute('data-noload') && loading && f.method.toLowerCase() === 'post') loading.style.display = 'grid';
  });
  document.getElementById('confirmYes')?.addEventListener('click', () => { if (pending) { pending.dataset.ok = '1'; pending.requestSubmit(); } });

  document.getElementById('sideToggle')?.addEventListener('click', () => {
    if (window.innerWidth < 992) document.body.classList.toggle('open-side');
    else { document.body.classList.toggle('collapsed'); localStorage.setItem('side', document.body.classList.contains('collapsed') ? '1' : ''); }
  });
  if (localStorage.getItem('side') && window.innerWidth >= 992) document.body.classList.add('collapsed');

  // notifications bell
  const bell = document.getElementById('bellCount'), list = document.getElementById('bellList');
  function pollNotes() {
    if (!bell) return;
    api('/api/notifications').then(d => {
      bell.textContent = d.unread; bell.style.display = d.unread ? '' : 'none';
      list.innerHTML = d.items.length ? '' : '<div class="p-3 text-muted small">No notifications</div>';
      d.items.forEach(n => {
        const a = document.createElement('a'); a.className = 'dropdown-item small text-wrap' + (n.read ? '' : ' fw-semibold');
        a.href = n.link || '/notifications'; a.textContent = n.title + ' · ' + n.at; list.appendChild(a);
      });
    }).catch(() => {});
  }
  pollNotes(); setInterval(pollNotes, 30000);

  // live SOS watcher (polls the database every 15 s; not a push channel)
  if (document.body.dataset.sos) {
    let last = parseInt(localStorage.getItem('lastSos') || '0');
    const badge = document.getElementById('sosBadge');
    const tick = () => api('/api/sos/pending').then(d => {
      if (badge) { badge.textContent = d.pending; badge.style.display = d.pending ? '' : 'none'; }
      if (d.latest_id > last && last !== 0 && d.latest) toast(`New SOS ${d.latest.code}: ${d.latest.people} people (${d.latest.priority})`, 'danger');
      if (d.latest_id > last) { last = d.latest_id; localStorage.setItem('lastSos', last); }
      document.dispatchEvent(new CustomEvent('sos-update', {detail: d}));
    }).catch(() => {});
    tick(); setInterval(tick, 15000);
  }
})();
