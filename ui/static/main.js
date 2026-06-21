/* ── Chart setup ──────────────────────────────────────────────────────────── */
const wrap = document.getElementById('chart-wrap');

const chart = LightweightCharts.createChart(wrap, {
  width:  wrap.clientWidth,
  height: 360,
  layout: {
    background: { color: '#0b0b0d' },
    textColor:  '#6a6a80',
  },
  grid: {
    vertLines: { color: '#111116' },
    horzLines: { color: '#111116' },
  },
  crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  rightPriceScale: { borderColor: '#222230' },
  timeScale: {
    borderColor:    '#222230',
    timeVisible:    true,
    secondsVisible: true,
  },
});

const bidSeries = chart.addLineSeries({
  color: '#26d19a', lineWidth: 1, title: 'Bid', priceLineVisible: false,
});
const askSeries = chart.addLineSeries({
  color: '#f05060', lineWidth: 1, title: 'Ask', priceLineVisible: false,
});

// Fill markers live on a hidden mid series so they don't crowd bid/ask
const midSeries = chart.addLineSeries({
  color: 'transparent', lineWidth: 0, title: '', priceLineVisible: false,
});

window.addEventListener('resize', () =>
  chart.resize(wrap.clientWidth, 360));

/* ── Chart update throttle (1 Hz to avoid duplicate-time errors) ──────────── */
let lastChartSec = 0;

function chartUpdate(bid, ask, mid) {
  const t = Math.floor(Date.now() / 1000);
  if (t === lastChartSec) return;
  lastChartSec = t;
  bidSeries.update({ time: t, value: bid });
  askSeries.update({ time: t, value: ask });
  midSeries.update({ time: t, value: mid });
}

/* ── Fill markers ─────────────────────────────────────────────────────────── */
const markers = [];

function addFillMarker(side, qty, price) {
  const t = Math.floor(Date.now() / 1000);
  markers.push({
    time:     t,
    position: side === 'BUY' ? 'belowBar' : 'aboveBar',
    color:    side === 'BUY' ? '#26d19a'  : '#f05060',
    shape:    side === 'BUY' ? 'arrowUp'  : 'arrowDown',
    text:     `${side} ${qty}@${price.toFixed(2)}`,
  });
  midSeries.setMarkers(markers);
}

/* ── Socket.IO ────────────────────────────────────────────────────────────── */
const socket = io();

socket.on('connect', () => {
  document.getElementById('dot').classList.add('live');
  document.getElementById('feed-label').textContent = 'live';
});
socket.on('disconnect', () => {
  document.getElementById('dot').classList.remove('live');
  document.getElementById('feed-label').textContent = 'disconnected';
});

socket.on('quote', (d) => {
  chartUpdate(d.bid, d.ask, d.mid);

  document.getElementById('p-bid').textContent    = d.bid.toFixed(4);
  document.getElementById('p-ask').textContent    = d.ask.toFixed(4);
  document.getElementById('p-mid').textContent    = d.mid.toFixed(4);
  document.getElementById('p-bid-sz').textContent = d.bid_sz;
  document.getElementById('p-ask-sz').textContent = d.ask_sz;
  document.getElementById('p-spd').textContent    = (d.ask - d.bid).toFixed(4);

  if (d.pnl) updatePnl(d.pnl);
});

socket.on('fill', (d) => {
  appendBlotterRow(d);
  if (d.pnl) updatePnl(d.pnl);
  if (d.status === 'FILLED') {
    addFillMarker(d.side, d.fill_qty, d.fill_px);
  }
  refreshResting();
  flashMsg(d.status === 'FILLED'
    ? `Filled ${d.side} ${d.fill_qty} @ ${d.fill_px.toFixed(4)}`
    : `Order ${d.order_id} ${d.status}`);
});

/* ── P&L display ──────────────────────────────────────────────────────────── */
function updatePnl(p) {
  document.getElementById('pnl-pos').textContent = p.position;
  document.getElementById('pnl-avg').textContent =
    p.position !== 0 ? p.avg_cost.toFixed(4) : '—';

  setMoney('pnl-unreal', p.unrealized);
  setMoney('pnl-real',   p.realized);
  setMoney('pnl-total',  p.total);
}

function setMoney(id, val) {
  const el  = document.getElementById(id);
  const abs = Math.abs(val).toFixed(2);
  el.textContent = (val >= 0 ? '+' : '-') + '$' + abs;
  el.className   = 'val ' + (val > 0 ? 'pos' : val < 0 ? 'neg' : 'zero');
}

/* ── Blotter ──────────────────────────────────────────────────────────────── */
function appendBlotterRow(d) {
  const tbody = document.getElementById('blotter-body');
  const tr    = document.createElement('tr');
  const cls   = d.status === 'REJECTED' ? 'rej'
              : d.side   === 'BUY'      ? 'buy'
              :                           'sell';
  tr.className = cls;
  tr.innerHTML = `
    <td>${d.order_id}</td>
    <td>${d.side}</td>
    <td>${d.fill_qty || '—'}</td>
    <td>${d.fill_px  ? d.fill_px.toFixed(4) : '—'}</td>
    <td>${d.status}</td>`;
  tbody.insertBefore(tr, tbody.firstChild);
  while (tbody.rows.length > 50) tbody.deleteRow(tbody.rows.length - 1);
}

/* ── Resting orders ───────────────────────────────────────────────────────── */
async function refreshResting() {
  const resp   = await fetch('/resting');
  const orders = await resp.json();
  const tbody  = document.getElementById('resting-body');
  tbody.innerHTML = '';
  for (const o of orders) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${o.order_id}</td>
      <td style="color:${o.side==='BUY'?'var(--green)':'var(--red)'}">${o.side}</td>
      <td>${o.qty}</td>
      <td>${o.limit_px.toFixed(4)}</td>
      <td><button class="btn-cancel" onclick="cancelOrder(${o.order_id})">✕</button></td>`;
    tbody.appendChild(tr);
  }
}

async function cancelOrder(oid) {
  await fetch('/cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ order_id: oid }),
  });
  refreshResting();
}

/* ── Order entry ──────────────────────────────────────────────────────────── */
let currentSide = 'BUY';

function setSide(side) {
  currentSide = side;
  document.getElementById('btn-buy').className  =
    'btn-side' + (side === 'BUY'  ? ' active-buy'  : '');
  document.getElementById('btn-sell').className =
    'btn-side' + (side === 'SELL' ? ' active-sell' : '');
  const btn = document.getElementById('submit-btn');
  btn.textContent = `Submit ${side}`;
  btn.className   = 'btn-submit' + (side === 'SELL' ? ' sell' : '');
}

function onTypeChange() {
  const isLimit = document.getElementById('ord-type').value === 'LIMIT';
  document.getElementById('limit-row').style.display = isLimit ? 'flex' : 'none';
}

async function submitOrder() {
  const qty      = parseInt(document.getElementById('ord-qty').value);
  const ordType  = document.getElementById('ord-type').value;
  const limitPx  = parseFloat(document.getElementById('ord-limit').value) || 0;

  if (!qty || qty <= 0) { flashMsg('Enter a valid quantity.', true); return; }
  if (ordType === 'LIMIT' && limitPx <= 0) { flashMsg('Enter a valid limit price.', true); return; }

  const btn = document.getElementById('submit-btn');
  btn.disabled = true;

  try {
    const resp = await fetch('/order', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ side: currentSide, order_type: ordType,
                                qty, limit_px: limitPx }),
    });
    const result = await resp.json();
    flashMsg(`#${result.order_id} submitted`);
    if (ordType === 'LIMIT') refreshResting();
  } catch (e) {
    flashMsg('Submission failed.', true);
  } finally {
    btn.disabled = false;
  }
}

function flashMsg(msg, err = false) {
  const el = document.getElementById('submit-msg');
  el.textContent = msg;
  el.style.color = err ? 'var(--red)' : 'var(--green)';
  setTimeout(() => { el.textContent = ''; }, 3000);
}

/* ── Keyboard shortcuts ───────────────────────────────────────────────────── */
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if (e.key === 'b' || e.key === 'B') setSide('BUY');
  if (e.key === 's' || e.key === 'S') setSide('SELL');
  if (e.key === 'Enter') submitOrder();
});
