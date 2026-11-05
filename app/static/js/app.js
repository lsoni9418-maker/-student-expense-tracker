(() => {
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const CSRF = $('meta[name=csrf-token]').content;
const CATS = $('#cfg').dataset.categories.split('|');
const PALETTE = ['#0B1F3A', '#2FBF8F', '#4F7CAC', '#F2B84B', '#E4717A', '#8E7DBE', '#5BC0BE', '#A0A8B8', '#7BAE7F'];
const inr = n => '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pad = n => String(n).padStart(2, '0');
const now = new Date();
const todayStr = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
let month = todayStr.slice(0, 7), view = 'dashboard', editing = null, cache = {};
const fmtDate = d => new Date(d + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
Chart.defaults.font.family = 'Inter, system-ui, sans-serif';
Chart.defaults.color = '#6B778C';
const charts = {};

async function api(url, method = 'GET', body) {
  const r = await fetch(url, { method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF }, body: body ? JSON.stringify(body) : undefined });
  if (r.status === 401) { location = '/login'; return new Promise(() => {}); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || 'Something went wrong. Please try again.');
  return d;
}
function toast(msg, isErr) {
  const t = $('#toast'); t.textContent = msg; t.className = 'toast show' + (isErr ? ' error' : '');
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove('show'), 2600);
}
const guard = fn => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };
function draw(id, hasData, cfg) {
  charts[id]?.destroy();
  const box = $('#' + id).parentElement; box.classList.toggle('noData', !hasData);
  if (hasData) charts[id] = new Chart($('#' + id), cfg);
}
const catIdx = c => Math.max(CATS.indexOf(c), 0);

function expRow(x, actions) {
  return `<div class="exp"><span class="dot c${catIdx(x.category) % 9}"></span>
    <div class="info"><b>${esc(x.description || x.category)}</b><small>${esc(x.category)} · ${fmtDate(x.date)}</small></div>
    <strong>−${inr(x.amount)}</strong>
    ${actions ? `<div class="acts"><button class="btn ghost sm" data-edit="${x.id}">Edit</button><button class="btn ghost sm danger" data-del="${x.id}">Delete</button></div>` : ''}</div>`;
}

/* ---------- views ---------- */
const loaders = {
  async dashboard() {
    const [s, m, e] = await Promise.all([api(`/api/summary?month=${month}`), api(`/api/charts/monthly?month=${month}`), api(`/api/expenses?month=${month}&limit=6`)]);
    $('#stats').innerHTML = [['Income', s.income, ''], ['Budget', s.budget, ''], ['Spent', s.spent, ''], ['Balance', s.balance, s.balance < 0 ? 'neg' : 'pos']]
      .map(([l, v, c]) => `<div class="card stat ${c}"><span>${l}</span><strong>${inr(v)}</strong></div>`).join('');
    $('#budgetText').textContent = s.budget > 0 ? `${inr(s.spent)} of ${inr(s.budget)} (${s.budget_used_pct}%)` : 'Set a budget in Income & Budget';
    const bar = $('#budgetBar'); bar.style.width = Math.min(s.budget_used_pct, 100) + '%'; bar.classList.toggle('over', s.budget_used_pct > 100);
    draw('chDonut', s.categories.length > 0, { type: 'doughnut',
      data: { labels: s.categories.map(c => c.category), datasets: [{ data: s.categories.map(c => c.total), backgroundColor: s.categories.map(c => PALETTE[catIdx(c.category) % 9]), borderWidth: 2 }] },
      options: { maintainAspectRatio: false, cutout: '62%', plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: c => ` ${c.label}: ${inr(c.parsed)}` } } } } });
    draw('chMonthly', m.totals.some(v => v > 0), { data: { labels: m.labels, datasets: [
      { type: 'bar', label: 'Spent', data: m.totals, backgroundColor: '#2FBF8F', borderRadius: 6 },
      { type: 'line', label: 'Budget', data: m.budgets, borderColor: '#0B1F3A', borderDash: [5, 4], pointRadius: 2, tension: .2 }] },
      options: { maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { callback: v => inr(v) } } }, plugins: { legend: { position: 'bottom' } } } });
    $('#recent').innerHTML = e.length ? e.map(x => expRow(x, false)).join('') : '<p class="empty-msg">No expenses this month. Click “+ Add expense” to start.</p>';
  },
  async expenses() {
    const scope = $('#fScope').value, cat = $('#fCat').value, q = $('#fQ').value.trim();
    const p = new URLSearchParams({ month: scope === 'all' ? 'all' : month }); if (cat) p.set('category', cat); if (q) p.set('q', q);
    const rows = await api('/api/expenses?' + p);
    cache = Object.fromEntries(rows.map(x => [x.id, x]));
    const total = rows.reduce((a, x) => a + x.amount, 0);
    $('#expList').innerHTML = rows.length ? `<p class="muted small">${rows.length} expense(s) · total ${inr(total)}</p>` + rows.map(x => expRow(x, true)).join('') : '<p class="empty-msg">No expenses found.</p>';
  },
  async budget() {
    const p = await api(`/api/plan?month=${month}`);
    const f = $('#planForm'); f.income.value = p.income; f.budget.value = p.budget;
    $('#planNote').textContent = p.inherited ? 'No plan saved for this month yet — showing your last saved values. Click Save to confirm.' : 'Set your income and budget for the selected month.';
  },
  async analytics() {
    const [r, p] = await Promise.all([api(`/api/report?month=${month}`), api('/api/predict')]);
    const cats = r.summary.categories, pred = Object.fromEntries(p.by_category.map(c => [c.category, c.predicted]));
    draw('chCats', cats.length > 0, { type: 'bar', data: { labels: cats.map(c => c.category), datasets: [{ data: cats.map(c => c.total), backgroundColor: cats.map(c => PALETTE[catIdx(c.category) % 9]), borderRadius: 6 }] },
      options: { indexAxis: 'y', maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { ticks: { callback: v => inr(v) } } } } });
    draw('chDaily', r.summary.spent > 0, { type: 'line', data: { labels: r.daily.map(d => +d.date.slice(8)), datasets: [{ data: r.daily.map(d => d.total), borderColor: '#2FBF8F', backgroundColor: 'rgba(47,191,143,.15)', fill: true, tension: .3, pointRadius: 2 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { callback: v => inr(v) } }, x: { title: { display: true, text: 'Day of month' } } } } });
    $('#catTable').innerHTML = cats.length ? cats.map(c => `<div class="catrow"><span><span class="dot c${catIdx(c.category) % 9}" style="display:inline-block;margin-right:8px"></span>${esc(c.category)}</span>
      <div class="bar"><i style="width:${c.pct}%"></i></div><b>${inr(c.total)}</b><span class="pct muted">${c.pct}%</span></div>`).join('') : '<p class="empty-msg">No spending to analyse yet.</p>';
  },
  async ai() {
    const [p, t] = await Promise.all([api('/api/predict'), api(`/api/suggestions?month=${month}`)]);
    $('#predBox').innerHTML = p.predicted_total > 0
      ? `<p class="muted small" style="margin:0">Expected spending in ${esc(p.next_label)}</p><div class="big">${inr(p.predicted_total)}</div>
         <span class="badge">${esc(p.confidence)} confidence</span> <span class="muted small">${p.months_used} month(s) of data</span>
         <p class="muted small">${esc(p.basis)}</p>${p.by_category.slice(0, 5).map(c => `<div class="mini"><span>${esc(c.category)}</span><b>${inr(c.predicted)}</b></div>`).join('')}`
      : `<p class="empty-msg">${esc(p.basis)}</p>`;
    const labels = [...p.history.map(h => h.label), p.next_label + ' (predicted)'];
    draw('chPred', p.history.length > 0, { type: 'bar', data: { labels, datasets: [{ data: [...p.history.map(h => h.total), p.predicted_total],
      backgroundColor: [...p.history.map(() => '#0B1F3A'), '#2FBF8F'], borderRadius: 6 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { callback: v => inr(v) } } } } });
    $('#tips').innerHTML = t.suggestions.map(x => `<div class="tip ${esc(x.type)}"><b>${esc(x.title)}</b>${esc(x.text)}</div>`).join('');
  },
  async reports() {
    const r = await api(`/api/report?month=${month}`), s = r.summary;
    $('#csvMonth').href = `/api/export.csv?month=${month}`;
    const label = new Date(month + '-01T00:00').toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
    $('#reportBox').innerHTML = `<h3>Monthly report — ${esc(label)}</h3><table class="rtable">
      <tr><td>Income</td><td>${inr(s.income)}</td></tr><tr><td>Budget</td><td>${inr(s.budget)}</td></tr>
      <tr><td>Total spent</td><td>${inr(s.spent)}</td></tr><tr><td>Remaining balance</td><td>${inr(s.balance)}</td></tr>
      <tr><td>Budget left</td><td>${inr(s.budget_left)}</td></tr><tr><td>Number of expenses</td><td>${r.count}</td></tr>
      <tr><td>Average per day</td><td>${inr(r.avg_per_day)}</td></tr>
      <tr><td>Highest-spend day</td><td>${r.busiest_day ? fmtDate(r.busiest_day.date) + ' (' + inr(r.busiest_day.total) + ')' : '—'}</td></tr></table>
      <h3 style="margin-top:20px">By category</h3>${s.categories.map(c => `<div class="mini"><span>${esc(c.category)}</span><b>${inr(c.total)} · ${c.pct}%</b></div>`).join('') || '<p class="muted">No expenses.</p>'}
      <h3 style="margin-top:20px">Top 5 expenses</h3>${r.top_expenses.map(x => expRow(x, false)).join('') || '<p class="muted">No expenses.</p>'}`;
  },
  async profile() {
    const p = await api('/api/profile'), f = $('#profileForm');
    f.name.value = p.name; f.email.value = p.email; f.course.value = p.course; f.college.value = p.college;
    $('#joined').textContent = p.joined ? fmtDate(p.joined) : '';
  }
};
const titles = { dashboard: 'Dashboard', expenses: 'Expenses', budget: 'Income & Budget', analytics: 'Analytics', ai: 'AI Insights', reports: 'Reports', profile: 'Profile' };
const show = guard(async v => {
  view = v;
  $$('.view').forEach(el => el.classList.toggle('hidden', el.id !== 'view-' + v));
  $$('.sidebar nav button').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  $('#pageTitle').textContent = titles[v]; closeMenu();
  await loaders[v]();
});
const refresh = () => show(view);

/* ---------- menu ---------- */
const closeMenu = () => { $('#sidebar').classList.remove('open'); $('#scrim').classList.remove('show'); };
$('#menuBtn').onclick = () => { $('#sidebar').classList.add('open'); $('#scrim').classList.add('show'); };
$('#scrim').onclick = closeMenu;
$$('.sidebar nav button').forEach(b => b.onclick = () => show(b.dataset.view));
$('#monthPick').value = month;
$('#monthPick').onchange = e => { if (e.target.value) { month = e.target.value; refresh(); } };

/* ---------- expense modal ---------- */
const modal = $('#expModal'), form = $('#expForm');
form.category.innerHTML = CATS.map(c => `<option>${esc(c)}</option>`).join('');
$('#fCat').innerHTML += CATS.map(c => `<option>${esc(c)}</option>`).join('');
function openModal(x) {
  editing = x ? x.id : null; $('#modalTitle').textContent = x ? 'Edit expense' : 'Add expense';
  form.amount.value = x ? x.amount : ''; form.category.value = x ? x.category : CATS[0];
  form.date.value = x ? x.date : todayStr; form.description.value = x ? x.description : '';
  modal.showModal();
}
$('#addBtn').onclick = () => openModal(null);
$('#cancelExp').onclick = () => modal.close();
form.onsubmit = guard(async e => {
  e.preventDefault();
  const body = { amount: form.amount.value, category: form.category.value, date: form.date.value, description: form.description.value };
  await api(editing ? `/api/expenses/${editing}` : '/api/expenses', editing ? 'PUT' : 'POST', body);
  modal.close(); toast(editing ? 'Expense updated' : 'Expense added'); refresh();
});
$('#expList').onclick = guard(async e => {
  const ed = e.target.closest('[data-edit]'), del = e.target.closest('[data-del]');
  if (ed) openModal(cache[ed.dataset.edit]);
  if (del && confirm('Delete this expense?')) { await api(`/api/expenses/${del.dataset.del}`, 'DELETE'); toast('Expense deleted'); refresh(); }
});
['fScope', 'fCat'].forEach(id => $('#' + id).onchange = refresh);
let timer; $('#fQ').oninput = () => { clearTimeout(timer); timer = setTimeout(refresh, 300); };

/* ---------- forms ---------- */
$('#planForm').onsubmit = guard(async e => {
  e.preventDefault(); const f = e.target;
  await api(`/api/plan?month=${month}`, 'PUT', { income: f.income.value, budget: f.budget.value }); toast('Saved'); refresh();
});
$('#profileForm').onsubmit = guard(async e => {
  e.preventDefault(); const f = e.target;
  await api('/api/profile', 'PUT', { name: f.name.value, course: f.course.value, college: f.college.value }); toast('Profile saved');
});
$('#pwForm').onsubmit = guard(async e => {
  e.preventDefault(); const f = e.target;
  await api('/api/profile/password', 'POST', { current_password: f.current_password.value, new_password: f.new_password.value });
  f.reset(); toast('Password updated');
});
$('#printBtn').onclick = () => window.print();

show('dashboard');
})();
