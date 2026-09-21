const $ = (id) => document.getElementById(id);
let payload = null;
let view = "rising";
let range = 60;
const observers = new Set();

function el(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}

function pct(value) {
  if (!Number.isFinite(Number(value))) return "--";
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

function price(value) {
  if (!Number.isFinite(Number(value))) return "--";
  const decimals = Math.abs(value) < 100 ? 3 : 2;
  return Number(value).toLocaleString("zh-CN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function tone(value) { return value >= 0 ? "rise" : "fall"; }

function renderHeadline() {
  const holder = $("headline-ranks");
  holder.replaceChildren();
  for (const side of ["rising", "falling"]) {
    const column = el("div", `headline-column ${side}`);
    const title = el("div", "headline-title");
    title.append(el("span", "", side === "rising" ? "中位数领涨" : "中位数领跌"), el("span", "", "近5个交易日"));
    const items = el("div", "headline-items");
    payload.rankings[side].forEach((item, index) => {
      const box = el("div", "headline-item");
      box.append(el("small", "", `0${index + 1}`), el("strong", "", item.category), el("em", tone(item.medianReturn), pct(item.medianReturn)));
      items.append(box);
    });
    column.append(title, items); holder.append(column);
  }
}

function drawLine(ctx, points, color, width = 1.25) {
  ctx.beginPath();
  let started = false;
  for (const point of points) {
    if (!point) { started = false; continue; }
    if (started) ctx.lineTo(point[0], point[1]); else { ctx.moveTo(point[0], point[1]); started = true; }
  }
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
}

function drawChart(canvas, points, maKeys, hover = -1) {
  const rect = canvas.getBoundingClientRect();
  if (rect.width < 20 || !points.length) return;
  const data = points.slice(-range);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * dpr); canvas.height = Math.round(rect.height * dpr);
  const ctx = canvas.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const w = rect.width, h = rect.height, left = 4, right = 46, top = 7, bottom = 20;
  const plotW = w - left - right, plotH = h - top - bottom;
  const rawHigh = Math.max(...data.map((item) => item.high));
  const rawLow = Math.min(...data.map((item) => item.low));
  const pad = (rawHigh - rawLow || 1) * .07, high = rawHigh + pad, low = rawLow - pad;
  const x = (index) => left + (index + .5) * plotW / data.length;
  const y = (value) => top + (high - value) / (high - low) * plotH;
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, w, h);
  ctx.font = '9px Bahnschrift, "Microsoft YaHei UI", sans-serif';
  for (let index = 0; index < 4; index++) {
    const gridY = top + index * plotH / 3;
    ctx.strokeStyle = "#e8ecea"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(left, gridY); ctx.lineTo(w - right + 4, gridY); ctx.stroke();
    ctx.fillStyle = "#788681"; ctx.textAlign = "left"; ctx.fillText(price(high - index * (high - low) / 3), w - right + 7, gridY + 3);
  }
  const candleW = Math.max(1.1, Math.min(5.5, plotW / data.length * .58));
  data.forEach((bar, index) => {
    const cx = x(index); ctx.strokeStyle = ctx.fillStyle = bar.close >= bar.open ? "#c83e49" : "#16846b";
    ctx.beginPath(); ctx.moveTo(cx, y(bar.high)); ctx.lineTo(cx, y(bar.low)); ctx.stroke();
    const bodyTop = Math.min(y(bar.open), y(bar.close));
    ctx.fillRect(cx - candleW / 2, bodyTop, candleW, Math.max(1, Math.abs(y(bar.open) - y(bar.close))));
  });
  const colors = { ma5: "#297c89", ma10: "#af7d1c", ma60: "#28445b" };
  maKeys.forEach((key) => drawLine(ctx, data.map((bar, index) => bar[key] == null ? null : [x(index), y(bar[key])]), colors[key], 1.35));
  [0, Math.floor((data.length - 1) / 2), data.length - 1].forEach((index) => {
    const label = data[index].time.slice(5, 10);
    ctx.fillStyle = "#788681"; ctx.textAlign = index === 0 ? "left" : index === data.length - 1 ? "right" : "center";
    ctx.fillText(label, x(index), h - 5);
  });
  if (hover >= 0 && hover < data.length) {
    ctx.strokeStyle = "#788681"; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(x(hover), top); ctx.lineTo(x(hover), h - bottom); ctx.stroke(); ctx.setLineDash([]);
  }
  canvas._geometry = { data, left, plotW };
}

function chartPanel(title, period, points, maKeys) {
  const panel = el("div", "chart-panel");
  const caption = el("div", "chart-caption");
  const label = el("strong", "", title);
  const legend = el("div", "legend");
  for (const key of maKeys) legend.append(el("span", key, key.toUpperCase()));
  caption.append(label, legend); panel.append(caption);
  if (!points?.length) { panel.append(el("div", "chart-empty", `${period}数据暂缺`)); return panel; }
  const wrap = el("div", "canvas-wrap"), canvas = el("canvas", "chart-canvas"), tip = el("div", "chart-tooltip");
  tip.hidden = true; canvas.setAttribute("role", "img"); canvas.setAttribute("aria-label", `${title}K线及均线`);
  wrap.append(canvas, tip); panel.append(wrap);
  const redraw = (hover = -1) => drawChart(canvas, points, maKeys, hover);
  const observer = new ResizeObserver(() => redraw()); observer.observe(wrap); observers.add(observer);
  canvas.addEventListener("mousemove", (event) => {
    const geometry = canvas._geometry; if (!geometry) return;
    const rect = canvas.getBoundingClientRect(); const localX = event.clientX - rect.left;
    const index = Math.max(0, Math.min(geometry.data.length - 1, Math.floor((localX - geometry.left) / geometry.plotW * geometry.data.length)));
    const bar = geometry.data[index]; redraw(index);
    const averages = maKeys.map((key) => `${key.toUpperCase()} ${bar[key] == null ? "--" : price(bar[key])}`).join(" · ");
    tip.textContent = `${bar.time}  开 ${price(bar.open)}  高 ${price(bar.high)}  低 ${price(bar.low)}  收 ${price(bar.close)}  ${averages}`;
    tip.hidden = false; tip.style.left = `${Math.min(Math.max(localX + 8, 4), rect.width - tip.offsetWidth - 4)}px`; tip.style.top = "6px";
  });
  canvas.addEventListener("mouseleave", () => { tip.hidden = true; redraw(); });
  requestAnimationFrame(redraw); return panel;
}

function instrumentCard(member) {
  const chart = payload.charts[member.symbol] || { intradayPeriod: member.hasNight ? "2h" : "1h", intraday: [], daily: [] };
  const article = el("article", "instrument");
  const head = el("header", "instrument-head"), identity = el("div", "instrument-id");
  const name = el("h3", "", member.name); name.append(el("span", "symbol", member.symbol));
  const line = el("div", "price-line"); line.append(el("span", "", "收盘价"), el("strong", "", price(member.price)), el("span", "", member.dataDate.slice(5)));
  identity.append(name, line); head.append(identity, el("strong", `return-value ${tone(member.return5)}`, pct(member.return5)));
  const stack = el("div", "chart-stack");
  stack.append(
    chartPanel(`${chart.intradayPeriod === "2h" ? "2小时" : "1小时"}线`, chart.intradayPeriod, chart.intraday, ["ma5", "ma10", "ma60"]),
    chartPanel("日线", "1d", chart.daily, ["ma5", "ma10"]),
  );
  article.append(head, stack); return article;
}

function renderRankings(side) {
  for (const observer of observers) observer.disconnect(); observers.clear();
  const holder = $("category-list"); holder.replaceChildren();
  payload.rankings[side].forEach((category, index) => {
    const section = el("section", "category-section");
    const heading = el("header", "category-heading"), name = el("div", "category-name"), score = el("div", "category-score");
    name.append(el("span", "rank-number", `0${index + 1}`), el("h2", "", category.category));
    score.append(el("small", "", "品类5日收益中位数"), el("strong", tone(category.medianReturn), pct(category.medianReturn)), el("span", "", `${category.memberCount}个有效品种`));
    heading.append(name, score);
    const grid = el("div", "instrument-grid"); category.members.forEach((member) => grid.append(instrumentCard(member)));
    section.append(heading, grid); holder.append(section);
  });
  holder.hidden = false; $("category-table").hidden = true;
}

function renderTable() {
  const section = $("category-table"); section.replaceChildren();
  const table = el("table"), thead = el("thead"), header = el("tr");
  ["品类", "有效品种", "近5日收益中位数"].forEach((text) => header.append(el("th", "", text)));
  thead.append(header); const tbody = el("tbody");
  payload.categoryTable.forEach((item, index) => {
    const row = el("tr"), category = el("td"); category.append(el("span", "order", String(index + 1).padStart(2, "0")), document.createTextNode(item.category));
    row.append(category, el("td", "", String(item.memberCount)), el("td", `return ${tone(item.medianReturn)}`, pct(item.medianReturn))); tbody.append(row);
  });
  table.append(thead, tbody); section.append(table); section.hidden = false; $("category-list").hidden = true;
}

function setView(next) {
  view = next;
  document.querySelectorAll("[data-view]").forEach((button) => { const active = button.dataset.view === view; button.classList.toggle("active", active); button.setAttribute("aria-selected", String(active)); });
  if (view === "all") renderTable(); else renderRankings(view);
}

async function load() {
  try {
    const response = await fetch("data/latest.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
    $("data-date").textContent = payload.dataDate;
    $("generated-at").textContent = payload.generatedAt.replace("T", " ").slice(0, 16);
    $("coverage").textContent = `${payload.coverage.available}/${payload.coverage.total}`;
    renderHeadline(); setView(view); $("loading").hidden = true;
  } catch (error) {
    $("loading").hidden = true; $("error").hidden = false; $("error").textContent = `数据加载失败：${error.message}`;
  }
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => payload && setView(button.dataset.view)));
document.querySelectorAll("[data-range]").forEach((button) => button.addEventListener("click", () => {
  range = Number(button.dataset.range);
  document.querySelectorAll("[data-range]").forEach((candidate) => candidate.classList.toggle("active", candidate === button));
  if (payload && view !== "all") renderRankings(view);
}));
load();
