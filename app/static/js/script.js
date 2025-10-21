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

  if (empty) empty.style.display = list.length ? 'none' : '';
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

  if (empty) empty.style.display = 'none';
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
      if (data.error === 'link_required') {
        flashClient('Vincule seu Telegram para habilitar o controle.', 'warning');
      } else {
        flashClient('Falha ao alternar. Estado mantido.', 'warning');
      }
      return;
    }

    el.checked = !!data.running;
    setBotStatus(data.running ? 'Ativado' : 'Parado');

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

  // legenda simples
  ctx.fillStyle = '#e8eefc';
  ctx.fillText('R$ (linha) • # ganhos (barras)', P.l, P.t + 12);
}

async function updateDailyChart(){
  const canvas = document.getElementById('rev-chart');
  if (!canvas) return;
  try {
    const res = await apiFetch('/dashboard/api/kpis/daily');
    let data = {};
    try { data = await res.json(); } catch {}
    if (!data || !data.ok) return;
    drawChart(canvas, data.labels || [], data.cents || [], data.counts || []);
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
  }, 20000);
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

  // sincroniza UI inicial
  refreshBotStatus();
  startPolling();

  // debounce para visibilidade (evita liga/desliga rápido ao alternar abas)
  document.addEventListener('visibilitychange', () => {
    clearTimeout(visTimer);
    visTimer = setTimeout(() => {
      if (document.hidden) stopPolling(); else startPolling();
    }, 150);
  });

  // re-render do gráfico em resize
  let resizeTO;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTO);
    resizeTO = setTimeout(updateDailyChart, 150);
  });
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
