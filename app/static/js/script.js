// =====================================================
// SmartPayBot - script.js (revisado completo)
// =====================================================

// === Utilidades ===
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

let pollTimer = null;
let visTimer  = null;

// CSRF via <meta name="csrf-token" content="...">
function csrfToken() {
  const m = $('meta[name="csrf-token"]');
  return m ? m.getAttribute('content') : '';
}

function flashClient(message, type = 'info', ttlMs = 5000) {
  let box = $('.flashes');
  let temp = false;
  if (!box) {
    box = document.createElement('div');
    box.className = 'flashes';
    box.setAttribute('role', 'status');
    box.setAttribute('aria-live', 'polite');
    const main = $('main.container') || document.body;
    main.prepend(box);
    temp = true;
  }
  const div = document.createElement('div');
  div.className = `flash ${type}`;
  div.textContent = message;
  box.appendChild(div);
  setTimeout(() => {
    div.remove();
    if (temp && !box.children.length) box.remove();
  }, ttlMs);
}

// auto-dismiss de flashes renderizados pelo servidor
window.addEventListener('load', () => {
  $$('.flash').forEach(el => { setTimeout(() => el.remove(), 5000); });
});

function setBotStatus(text) {
  const el = $('#bot-status');
  if (el) el.textContent = text;
}

function setDashboardMonitoringStatus(active) {
  const el = $('#dashboard-monitoring-status');
  if (!el) return;
  const label = el.querySelector('[data-dashboard-status-label]');
  if (label) label.textContent = active ? 'Monitoramento ativo' : 'Monitoramento pausado';
  el.classList.toggle('status-pill--ok', !!active);
  el.classList.toggle('status-pill--muted', !active);
  el.classList.remove('status-pill--warn');
}

function setDashboardTelegramStatus(linked) {
  const el = $('#dashboard-telegram-status');
  if (!el) return;
  const label = el.querySelector('[data-dashboard-status-label]');
  if (label) label.textContent = linked ? 'Telegram conectado' : 'Telegram desconectado';
  el.classList.toggle('status-pill--ok', !!linked);
  el.classList.toggle('status-pill--warn', !linked);
  el.classList.remove('status-pill--muted');
}

// converte valor em inteiro, aceitando "1.234", "1,234" ou "1234"
function toInt(v) {
  if (typeof v === 'string') {
    v = v.trim().replace(/\./g, '').replace(',', '.');
  }
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

// --- apiFetch: cabeçalhos corretos, sem cache e CSRF quando precisa ---
async function apiFetch(url, opts = {}) {
  const base = { method: 'GET', credentials: 'same-origin', cache: 'no-store' };
  const req  = Object.assign(base, opts);
  const method = (req.method || 'GET').toUpperCase();

  const headers = Object.assign(
    { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'Cache-Control': 'no-cache' },
    req.headers || {}
  );

  if (req.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = csrfToken();
    if (token) {
      headers['X-CSRFToken']  = token;
      headers['X-CSRF-Token'] = token;
    }
  }
  req.headers = headers;

  const res = await fetch(url, req);

  if (res.status === 400) { window.location.reload(); throw new Error('csrf'); }
  if (res.status === 401 || res.status === 403) { window.location.href = '/auth/login'; throw new Error('auth'); }
  return res;
}

// ====== Chips ======
const CHIP_COLORS = [
  'chip--blue','chip--red','chip--green','chip--amber',
  'chip--pink','chip--indigo','chip--purple','chip--teal','chip--cyan'
];
const colorByIndex = i => CHIP_COLORS[i % CHIP_COLORS.length];

function getDomKeywords() {
  return $$('#keywords-list .chip')
    .map(li => li.dataset.kw)
    .filter(Boolean);
}

function splitInputKeywords(raw) {
  return (raw || '')
    .split(/[;,]/g)
    .map(s => s.trim())
    .filter(Boolean);
}

function updateKwCounter() {
  const display = document.getElementById('kw-count-display');
  if (!display) return; // plano Pro não tem contador
  const max  = parseInt(display.getAttribute('data-kw-max') || '-1', 10);
  const used = getDomKeywords().length;
  display.textContent = `${used} / ${max > 0 ? max : '∞'}`;
  const pct = max > 0 ? Math.min(100, Math.round(used / max * 100)) : 0;
  display.className = 'usage-count ' + (pct >= 100 ? 'usage-count--danger' : pct >= 67 ? 'usage-count--warn' : 'usage-count--ok');
  const bar = document.getElementById('kw-bar');
  if (bar && max > 0) {
    bar.style.width = pct + '%';
    bar.className = 'progress-fill ' + (pct >= 100 ? 'progress-fill--danger' : pct >= 67 ? 'progress-fill--warn' : '');
  }
}

function updateAlertCounter(alertsToday, maxAlerts) {
  const display = document.getElementById('al-count-display');
  if (!display) return; // plano Pro -- sem contador
  const max  = maxAlerts   !== undefined ? parseInt(maxAlerts,   10) : parseInt(display.getAttribute('data-al-max') || '-1', 10);
  const used = alertsToday !== undefined ? parseInt(alertsToday, 10) : NaN;
  if (isNaN(used) || max < 0) return;
  display.textContent = `${used} / ${max}`;
  const pct = Math.min(100, Math.round(used / max * 100));
  display.className = 'usage-count ' + (pct >= 100 ? 'usage-count--danger' : pct >= 67 ? 'usage-count--warn' : 'usage-count--ok');
  const bar = document.getElementById('al-bar');
  if (bar) {
    bar.style.width = pct + '%';
    bar.className = 'progress-fill ' + (pct >= 100 ? 'progress-fill--danger' : pct >= 67 ? 'progress-fill--warn' : 'progress-fill--ok');
  }
  const banner = document.getElementById('al-limit-banner');
  if (banner) banner.style.display = (used >= max) ? '' : 'none';
}

function renderKeywords(list = []) {
  const ul = $('#keywords-list');
  const empty = $('#keywords-empty');
  if (!ul) return;

  ul.textContent = '';
  list.forEach((k, i) => {
    const li = document.createElement('li');
    li.className = `chip ${colorByIndex(i)}`;
    li.dataset.kw = k;

    const label = document.createElement('span');
    label.className = 'chip-text';
    label.textContent = k;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip-x';
    btn.setAttribute('data-kw', k);
    btn.setAttribute('aria-label', `Remover ${k}`);
    btn.textContent = '×';

    li.append(label, btn);
    ul.appendChild(li);
  });

  if (empty) {
    empty.hidden = !!list.length;
    empty.style.display = list.length ? 'none' : '';
  }
  updateKwCounter();
}

function appendKeywordsOptimistic(newOnes = []) {
  const ul = $('#keywords-list');
  const empty = $('#keywords-empty');
  if (!ul || !newOnes.length) return;

  const existing = new Set(getDomKeywords().map(s => String(s).toLowerCase()));
  const toAdd = newOnes.filter(k => !existing.has(String(k).toLowerCase()));
  if (!toAdd.length) return;

  const startIdx = ul.children.length;
  toAdd.forEach((k, i) => {
    const li = document.createElement('li');
    li.className = `chip ${colorByIndex(startIdx + i)}`;
    li.dataset.kw = k;

    const label = document.createElement('span');
    label.className = 'chip-text';
    label.textContent = k;

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip-x';
    btn.setAttribute('data-kw', k);
    btn.setAttribute('aria-label', `Remover ${k}`);
    btn.textContent = '×';

    li.append(label, btn);
    ul.appendChild(li);
  });

  if (empty) {
    empty.hidden = true;
    empty.style.display = 'none';
  }
  updateKwCounter();
}

async function refreshKeywordsFromServer() {
  try {
    const res = await apiFetch('/dashboard/api/keywords');
    let data = {};
    try { data = await res.json(); } catch {}
    if (data && Array.isArray(data.keywords)) {
      renderKeywords(data.keywords);
    }
  } catch {/* ignore */}
}

// --- addKeywords: otimista + reconcile sempre ---
async function addKeywords(raw) {
  const form = $('#keywords-form');
  const submitBtn = form && (form.querySelector('button[type="submit"], input[type="submit"]'));

  const typed = splitInputKeywords(raw);
  if (typed.length) appendKeywordsOptimistic(typed);

  if (submitBtn) submitBtn.disabled = true;
  try {
    const res = await apiFetch('/dashboard/keywords', {
      method: 'POST',
      body: JSON.stringify({ keywords: raw })
    });
    let data = {};
    try { data = await res.json(); } catch {}
    if (data && data.ok) {
      await refreshKeywordsFromServer(); // refletir normalização/ordem do backend
      flashClient(`${data.saved ?? typed.length} palavra(s) adicionada(s).`, 'info');
    } else {
      await refreshKeywordsFromServer();
      flashClient((data && data.error) || 'Falha ao salvar palavras-chave.', 'danger');
    }
  } catch {
    await refreshKeywordsFromServer();
    flashClient('Falha de rede ao salvar.', 'danger');
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

// --- delKeyword ---
async function delKeyword(kw, btnEl) {
  // Otimista
  const li = btnEl && btnEl.closest('.chip');
  if (li) li.remove();

  try {
    const res = await apiFetch('/dashboard/keywords/delete', {
      method: 'POST',
      body: JSON.stringify({ kw })
    });
    let data = {};
    try { data = await res.json(); } catch {}
    if (data && data.ok) {
      await refreshKeywordsFromServer();
      flashClient('Palavra removida.', 'info');
    } else {
      await refreshKeywordsFromServer();
      flashClient((data && data.error) || 'Nada foi removido.', 'warning');
    }
  } catch {
    await refreshKeywordsFromServer();
    flashClient('Falha de rede ao remover.', 'danger');
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

// ====== Bot (switch) ======
async function refreshBotStatus() {
  try {
    const res = await apiFetch('/dashboard/api/bot');
    let data = {};
    try { data = await res.json(); } catch {}
    if (data && typeof data.running === 'boolean') {
      const t = $('#bot-toggle');
      if (t) t.checked = !!data.running;
      setBotStatus(data.running ? 'Ativado' : 'Parado');
      setDashboardMonitoringStatus(data.running);
    }
  } catch {/* ignore */}
}

async function toggleBot(el) {
  const targetChecked = !!el.checked;
  el.disabled = true;
  setBotStatus(targetChecked ? 'Ativando…' : 'Parando…');

  try {
    const res = await apiFetch('/dashboard/bot-toggle', {
      method: 'POST',
      body: JSON.stringify({ enabled: targetChecked })
    });
    let data = {};
    try { data = await res.json(); } catch {}

    if (!res.ok || !data || typeof data.running !== 'boolean') {
      el.checked = !targetChecked;
      setBotStatus(targetChecked ? 'Parado' : 'Ativado');
      flashClient('Não foi possível alternar o bot.', 'danger');
      return;
    }

    if (data.ok === false) {
      el.checked = !!data.running;
      setBotStatus(data.running ? 'Ativado' : 'Parado');
      setDashboardMonitoringStatus(data.running);
      if (data.error === 'link_required') {
        flashClient('Vincule seu Telegram para habilitar o controle.', 'warning');
      } else {
        flashClient('Falha ao alternar. Estado mantido.', 'warning');
      }
      return;
    }

    el.checked = !!data.running;
    setBotStatus(data.running ? 'Ativado' : 'Parado');
    setDashboardMonitoringStatus(data.running);

    if (data.running !== targetChecked) {
      flashClient(`Estado atual: ${data.running ? 'Ativado' : 'Parado'}.`, 'warning');
    }
  } catch {
    el.checked = !targetChecked;
    setBotStatus(targetChecked ? 'Parado' : 'Ativado');
    flashClient('Erro de rede ao alternar o bot.', 'danger');
  } finally {
    el.disabled = false;
  }
}

// ====== Resumo (contador) ======
function currentDomCount() {
  const el = $('#projects-count') || $('.projects-count');
  if (!el) return NaN;
  const n = Number(String(el.textContent || '').trim());
  return Number.isFinite(n) ? n : NaN;
}

async function updateSummaryOnce() {
  try {
    const res = await apiFetch('/dashboard/api/summary');
    let data = {};
    try { data = await res.json(); } catch {}
    if (!data) return;

    const counts = data.counts || {};
    const today     = toInt(counts.today     ?? counts.hoje);
    const yesterday = toInt(counts.yesterday ?? counts.ontem);
    const week      = toInt(counts.week      ?? counts.last7 ?? counts.seven_days);
    const total     = toInt(data.projects_count ?? counts.total ?? data.total ?? data.count);

    // Evita sobrescrever total com 0 se já há valor maior no DOM
    const domTotalEl = $('#count-total') || $('#projects-count') || $('.projects-count');
    const domTotal   = domTotalEl ? toInt(domTotalEl.textContent) : 0;
    const totalFinal = (total === 0 && domTotal > 0) ? domTotal : total;

    const setText = (id, val) => { const e = $(id.startsWith('#') ? id : `#${id}`); if (e) e.textContent = String(val ?? 0); };

    setText('count-today',     today);
    setText('count-yesterday', yesterday);
    setText('count-week',      week);
    if (domTotalEl) domTotalEl.textContent = String(totalFinal);

    if (data.alerts_today !== undefined) {
      updateAlertCounter(data.alerts_today, data.max_alerts_day);
    }

  } catch { /* silencioso */ }
}

// ====== Helpers de formatação BR ======
const _fmtBRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
function brlFromCents(cents){ return _fmtBRL.format((Number(cents||0))/100); }
function pct1(x){ const v = Math.max(0, Math.min(100, (Number(x||0)*100))); return (Math.round(v*10)/10).toString().replace('.', ',') + '%'; }

// ====== KPIs (Resultados) ======
async function updateKpisOnce() {
  try {
    const res = await apiFetch('/dashboard/api/kpis');
    let data = {};
    try { data = await res.json(); } catch {}
    if (!data || !data.ok) return;

    const k = data.kpi || {};
    const rev = k.revenue || {};

    const monthEl = document.getElementById('kpi-month');
    const weekEl  = document.getElementById('kpi-week');
    const convEl  = document.getElementById('kpi-conv');
    const avgEl   = document.getElementById('kpi-avg');

    if (monthEl) monthEl.textContent = brlFromCents(rev.month_cents || 0);
    if (weekEl)  weekEl.textContent  = brlFromCents(rev.week_cents  || 0);
    if (convEl)  convEl.textContent  = pct1(k.conversion || 0);
    if (avgEl)   avgEl.textContent   = brlFromCents(k.ticket_avg_cents || 0);
  } catch { /* silencioso */ }
}

// ====== Canvas helper (nítido e responsivo) ======
function fitCanvas(canvas){
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const cssW = Math.floor(rect.width || canvas.width || 600);
  const cssH = Math.floor(rect.height || canvas.height || 180);
  canvas.style.width  = cssW + 'px';
  canvas.style.height = cssH + 'px';
  canvas.width  = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  return dpr;
}

// ====== Gráfico simples (canvas) dos últimos 14 dias ======
function drawChart(canvas, labels, cents, counts){
  const dpr = fitCanvas(canvas);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const W = canvas.width / dpr;
  const H = canvas.height / dpr;

  // limpar
  ctx.clearRect(0,0,W,H);

  // paddings
  const P = { l: 40, r: 10, t: 10, b: 22 };

  // escala Y para receita (cents -> reais)
  const vals = (cents || []).map(v => (Number(v)||0)/100);
  const maxY = Math.max(10, Math.max(...vals, 0));
  const stepX = (W - P.l - P.r) / Math.max(1, (labels || []).length - 1);

  // eixos
  ctx.strokeStyle = '#1e2a44';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(P.l, H - P.b);
  ctx.lineTo(W - P.r, H - P.b);
  ctx.moveTo(P.l, H - P.b);
  ctx.lineTo(P.l, P.t);
  ctx.stroke();

  // grid horizontal (3 linhas)
  ctx.strokeStyle = '#152036';
  [0.25, 0.5, 0.75].forEach(f=>{
    const y = P.t + (H - P.t - P.b) * f;
    ctx.beginPath(); ctx.moveTo(P.l, y); ctx.lineTo(W - P.r, y); ctx.stroke();
  });

  // linha da receita (suave)
  ctx.strokeStyle = '#60a5fa';
  ctx.lineWidth = 2;
  ctx.beginPath();
  labels.forEach((_, i)=>{
    const x = P.l + stepX*i;
    const y = P.t + (H - P.t - P.b) * (1 - (vals[i]/maxY));
    if (i===0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // barras finas p/ contagem
  const cnt = counts || [];
  const maxC = Math.max(1, Math.max(...cnt, 0));
  ctx.fillStyle = '#22c55e';
  const barW = Math.max(2, stepX * 0.25);
  labels.forEach((_, i)=>{
    const x = P.l + stepX*i - barW/2;
    const h = (H - P.t - P.b) * ((cnt[i]||0)/maxC) * 0.35; // 35% da altura
    const y = H - P.b - h;
    ctx.fillRect(x, y, barW, h);
  });

  // rótulos X (a cada 3 dias)
  ctx.fillStyle = '#9ba3b8';
  ctx.font = '12px Inter, system-ui, sans-serif';
  labels.forEach((lb, i)=>{
    if (i % 3 !== 0) return;
    const x = P.l + stepX*i;
    ctx.fillText(lb, x-12, H-6);
  });

}

async function updateDailyChart(){
  const canvas = document.getElementById('rev-chart');
  if (!canvas) return;
  const chartEmpty = document.getElementById('chart-empty');
  try {
    const res = await apiFetch('/dashboard/api/kpis/daily');
    let data = {};
    try { data = await res.json(); } catch {}
    if (!data || !data.ok) return;
    const hasData = (data.counts || []).some(v => v > 0) || (data.cents || []).some(v => v > 0);
    if (chartEmpty) chartEmpty.style.display = hasData ? 'none' : '';
    canvas.style.display = hasData ? '' : 'none';
    if (hasData) drawChart(canvas, data.labels || [], data.cents || [], data.counts || []);
  } catch {}
}

// 1) start/stop polling
function startPolling() {
  stopPolling();
  updateSummaryOnce();
  updateKpisOnce();
  updateDailyChart();
  pollTimer = setInterval(() => {
    if (!document.hidden) {
      updateSummaryOnce();
      updateKpisOnce();
      updateDailyChart();
    }
  }, 12000);
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

// --- boot handlers ---
document.addEventListener('DOMContentLoaded', () => {
  const t = $('#bot-toggle');
  if (t) t.addEventListener('change', () => toggleBot(t));

  const form = $('#keywords-form');
  if (form) {
    form.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const inp = form.querySelector('textarea, input[name="keywords"], #keywords');
      const raw = inp ? inp.value.trim() : '';
      if (!raw) { flashClient('Nada para salvar.', 'warning'); return; }
      await addKeywords(raw);
      if (inp) inp.value = '';
    });

    // Enter no input também submete
    const inp = form.querySelector('textarea, input[name="keywords"], #keywords');
    if (inp) {
      inp.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' && !ev.shiftKey) {
          ev.preventDefault();
          form.dispatchEvent(new Event('submit', { cancelable:true, bubbles:true }));
        }
      });
    }
  }

  const ul = $('#keywords-list');
  if (ul) {
    ul.addEventListener('click', async (ev) => {
      const btn = ev.target.closest('.chip-x');
      if (!btn) return;
      btn.disabled = true;
      const kw = btn.getAttribute('data-kw');
      if (kw) await delKeyword(kw, btn);
    });
  }

  const isMetricsDashboard = !!document.querySelector('.dashboard-shell--metrics');
  const telegramCard = document.getElementById('tg-card');
  const botToggle = document.getElementById('bot-toggle');
  setDashboardTelegramStatus(telegramCard?.dataset.linked === 'true');
  if (botToggle) setDashboardMonitoringStatus(!!botToggle.checked);
  refreshBotStatus();

  if (!isMetricsDashboard) {
    startPolling();

    // debounce para visibilidade (evita liga/desliga rápido ao alternar abas)
    document.addEventListener('visibilitychange', () => {
      clearTimeout(visTimer);
      visTimer = setTimeout(() => {
        if (document.hidden) stopPolling(); else startPolling();
      }, 150);
    });

    // re-render do gráfico legado em resize
    let resizeTO;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTO);
      resizeTO = setTimeout(updateDailyChart, 150);
    });
  }
});

// --- Projects page handlers (mark won) ---
(function(){
  const table = document.getElementById('proj-body');
  if (!table) return;

  let marking = false;

  async function mark(tr, won){
    if (marking) return; // debounce simples
    marking = true;
    try {
      const id  = Number(tr.dataset.id || 0);
      const val = (tr.querySelector('.won-val')?.value || '').trim();

      const res = await apiFetch('/dashboard/projects/mark', {
        method: 'POST',
        body: JSON.stringify({ id, won, value: val })
      });
      const data = await res.json().catch(()=>({}));
      if (!res.ok || !data.ok) { alert('Não foi possível salvar.'); return; }

      const statusCell  = tr.querySelector('.status-cell');
      const actionsCell = tr.querySelector('.actions-cell');
      const linkEl = tr.querySelector('a[data-role="open-project"]') || tr.querySelector('a');
      const href = linkEl ? linkEl.href : '#';

      if (won) {
        statusCell.innerHTML = '<span class="badge">Ganho</span>';
        actionsCell.innerHTML =
          `<div class="row">
             <a class="btn pill" target="_blank" data-role="open-project" href="${href}">Abrir</a>
             <button class="btn ghost pill btn-unwin">Desmarcar</button>
           </div>`;
      } else {
        statusCell.innerHTML = '<span class="help">Em aberto</span>';
        const inp = tr.querySelector('.won-val'); if (inp) inp.value = '';
        actionsCell.innerHTML =
          `<div class="row">
             <a class="btn pill" target="_blank" data-role="open-project" href="${href}">Abrir</a>
             <button class="btn success pill btn-win">Marcar ganho</button>
           </div>`;
      }
    } finally {
      marking = false;
    }
  }

  document.addEventListener('click', (e)=>{
    const winBtn = e.target.closest('.btn-win');
    const unBtn  = e.target.closest('.btn-unwin');
    if (winBtn) { e.preventDefault(); mark(winBtn.closest('tr'), true); }
    if (unBtn)  { e.preventDefault(); mark(unBtn.closest('tr'),  false); }
  });
})();

// ====== Dashboard real metrics chart (SPB-251D Etapa 2) ======
function labelForDate(iso) {
  const parts = String(iso || '').split('-');
  if (parts.length !== 3) return String(iso || '');
  return `${parts[2]}/${parts[1]}`;
}

function renderDashboardMetricsChart(range = '7d') {
  const chart = document.getElementById('dashboard-chart');
  if (!chart) return;
  const svg = chart.querySelector('[data-chart-svg]');
  const summary = document.querySelector('[data-chart-summary]');
  if (!svg) return;

  let series = {};
  try { series = JSON.parse(chart.dataset.series || '{}'); } catch { series = {}; }
  const rows = Array.isArray(series[range]) ? series[range] : [];
  const values = rows.map(row => Number(row.count || 0));
  const peak = Math.max(0, ...values);
  const total = values.reduce((sum, v) => sum + v, 0);

  if (summary) {
    const label = range === '7d' ? '7 dias' : '30 dias';
    summary.textContent = peak === 0
      ? `Nenhuma oportunidade encontrada nos últimos ${label}.`
      : `${total} oportunidade${total === 1 ? '' : 's'} nos últimos ${label}. Maior dia: ${peak}.`;
  }

  if (rows.length === 0) {
    svg.innerHTML = '';
    return;
  }

  const W = 640, H = 210, padL = 8, padR = 8, padT = 18, padB = 30;
  const n = rows.length;
  const scaleMax = Math.max(1, peak * 1.15);
  const stepX = n > 1 ? (W - padL - padR) / (n - 1) : 0;
  const pts = values.map((v, i) => {
    const x = padL + i * stepX;
    const y = padT + (H - padT - padB) * (1 - v / scaleMax);
    return [x, y];
  });

  const line = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const area = pts.length > 1
    ? `${line} L${pts[pts.length - 1][0].toFixed(1)},${H - padB} L${pts[0][0].toFixed(1)},${H - padB} Z`
    : '';
  const gridLines = [0.25, 0.5, 0.75, 1].map(f => {
    const y = padT + (H - padT - padB) * f;
    return `<line x1="${padL}" y1="${y.toFixed(1)}" x2="${W - padR}" y2="${y.toFixed(1)}" stroke="var(--spb-border)" stroke-width="1"/>`;
  }).join('');

  const labelEvery = range === '7d' ? 1 : Math.max(1, Math.ceil(n / 8));
  const labels = rows.map((row, i) => (i % labelEvery === 0 || i === n - 1)
    ? `<text x="${pts[i][0].toFixed(1)}" y="${H - 10}" text-anchor="middle" font-size="10.5" fill="var(--spb-faint)" font-family="Plus Jakarta Sans, sans-serif">${labelForDate(row.date)}</text>`
    : ''
  ).join('');
  const dots = pts.map((p, i) => i === pts.length - 1
    ? ''
    : `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3" fill="var(--spb-surface)" stroke="var(--spb-accent)" stroke-width="1.6"/>`
  ).join('');
  const last = pts[pts.length - 1];
  const lastValue = values[values.length - 1];
  const lastLabel = `${lastValue}`;
  const tooltipWidth = 18 + lastLabel.length * 8;

  svg.innerHTML = `
    <defs>
      <linearGradient id="spbAreaFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--spb-accent)" stop-opacity=".22"/>
        <stop offset="100%" stop-color="var(--spb-accent)" stop-opacity="0"/>
      </linearGradient>
    </defs>
    ${gridLines}
    ${area ? `<path d="${area}" fill="url(#spbAreaFill)"/>` : ''}
    <path d="${line}" fill="none" stroke="var(--spb-accent)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
    ${dots}
    ${labels}
    <circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="4.5" fill="var(--spb-accent)" stroke="var(--spb-surface)" stroke-width="2"/>
    <g>
      <rect x="${(last[0] - tooltipWidth / 2).toFixed(1)}" y="${(last[1] - 32).toFixed(1)}" width="${tooltipWidth}" height="22" rx="7" fill="var(--spb-surface-2)" stroke="var(--spb-border-strong)"/>
      <text x="${last[0].toFixed(1)}" y="${(last[1] - 17.5).toFixed(1)}" text-anchor="middle" font-size="11" font-weight="700" fill="var(--spb-text)" font-family="Plus Jakarta Sans, sans-serif">${lastLabel}</text>
    </g>
  `;
}

function initDashboardMetricsChart() {
  const chart = document.getElementById('dashboard-chart');
  if (!chart) return;
  const buttons = document.querySelectorAll('[data-dashboard-range]');
  buttons.forEach(button => {
    button.addEventListener('click', () => {
      buttons.forEach(item => {
        item.classList.toggle('is-active', item === button);
        item.setAttribute('aria-selected', item === button ? 'true' : 'false');
      });
      renderDashboardMetricsChart(button.dataset.dashboardRange || '7d');
    });
  });
  renderDashboardMetricsChart('7d');
}

function initTelegramLinkPolling() {
  const tgCard = document.getElementById('tg-card');
  if (!tgCard || tgCard.dataset.linked === 'true') return;
  const tgCardBody = document.getElementById('tg-card-body');
  const tpl = document.getElementById('tg-linked-tpl');
  if (!tgCardBody || !tpl) return;

  function swapToLinked() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    const clone = tpl.content.cloneNode(true);
    const csrfInput = clone.querySelector('[data-csrf-placeholder]');
    if (csrfInput && meta) csrfInput.value = meta.getAttribute('content') || '';
    tgCardBody.innerHTML = '';
    tgCardBody.appendChild(clone);
  }

  const timer = setInterval(() => {
    fetch('/dashboard/api/summary', { headers: { Accept: 'application/json', 'X-Requested-With': 'fetch' } })
      .then(resp => resp.ok ? resp.json() : null)
      .then(data => {
        if (!data || !data.ok || !data.linked) return;
        clearInterval(timer);
        tgCard.dataset.linked = 'true';
        setDashboardTelegramStatus(true);
        swapToLinked();
        const toggle = document.getElementById('bot-toggle');
        if (toggle) toggle.removeAttribute('disabled');
        const hint = document.getElementById('bot-link-hint');
        if (hint) hint.textContent = 'Alertas automáticos ativados.';
      })
      .catch(() => {});
  }, 5000);
}

function initThemeToggle() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    const root = document.documentElement;
    const current = root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try {
      const res = await apiFetch('/dashboard/theme', {
        method: 'POST',
        body: JSON.stringify({ theme: next })
      });
      if (!res.ok) {
        root.setAttribute('data-theme', current);
        flashClient('Não foi possível salvar a preferência de tema.', 'danger');
      }
    } catch {
      root.setAttribute('data-theme', current);
      flashClient('Não foi possível salvar a preferência de tema.', 'danger');
    }
  });
}

window.addEventListener('DOMContentLoaded', () => {
  initDashboardMetricsChart();
  initTelegramLinkPolling();
  initThemeToggle();
});
