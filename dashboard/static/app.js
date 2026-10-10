// Smart Fire Detection dashboard - polls the Flask API and updates the page.
const $ = (id) => document.getElementById(id);
const POLL_MS = 2000;
let lastLevel = "SAFE";
let chart = null;
let cameraRunning = false;
let audioCtx = null;

function fmtTime(ts) { return new Date(ts * 1000).toLocaleTimeString(); }
function fmt(v, digits = 1) { return v === null || v === undefined ? "--" : Number(v).toFixed(digits); }
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

function alarm() {
  if (!$("soundToggle").checked) return;
  audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
  [0, 0.4, 0.8].forEach((t) => {
    const o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.frequency.value = 2400; o.type = "square"; g.gain.value = 0.08;
    o.connect(g); g.connect(audioCtx.destination);
    o.start(audioCtx.currentTime + t); o.stop(audioCtx.currentTime + t + 0.25);
  });
}

function renderStatus(s) {
  $("statusPill").textContent = s.level;
  $("statusPill").className = `pill pill-${s.level}`;
  $("banner").className = `banner banner-${s.level}`;
  $("bannerTitle").textContent = { SAFE: "All clear", WARNING: "Warning", FIRE: "FIRE DETECTED" }[s.level];
  $("bannerText").textContent = s.reasons.length ? s.reasons.join(" · ")
    : s.level === "SAFE" ? "No fire or smoke detected." : "Check the camera feed and sensors.";
  $("ackAll").hidden = s.active_alerts === 0;
  if (s.level === "FIRE" && lastLevel !== "FIRE") alarm();
  lastLevel = s.level;

  $("tScore").textContent = s.score;
  const bar = $("scoreBar");
  bar.style.width = `${s.score}%`;
  bar.style.background = s.score >= 70 ? "var(--fire)" : s.score >= 30 ? "var(--warn)" : "var(--safe)";

  // sensor tiles: take the hottest / smokiest online device
  const r = s.readings;
  const pick = (k) => { const v = r.map((x) => x[k]).filter((x) => x !== null && x !== undefined); return v.length ? Math.max(...v) : null; };
  $("tTemp").textContent = fmt(pick("temperature"));
  $("tSmoke").textContent = fmt(pick("smoke"), 0);
  $("tHum").textContent = fmt(pick("humidity"), 0);

  $("tAlerts").textContent = s.today.total;
  $("tAlertsSub").textContent = `${s.today.fire} fire · ${s.today.warning} warning`;
  const online = s.devices.filter((d) => d.online);
  $("tDevices").textContent = online.length;
  $("tDevicesSub").textContent = `of ${s.devices.length} known`;

  renderDevices(s.devices);
  renderCamera(s);
}

function renderDevices(devices) {
  if (!devices.length) return;
  $("devices").innerHTML = devices.map((d) => `
    <div class="device">
      <div><span class="dot ${d.online ? "on" : ""}"></span><b>${esc(d.id)}</b></div>
      <div class="muted small">${esc(d.kind || "device")} · ${esc(d.ip || "")}</div>
      <div class="muted small">last seen ${d.last_seen ? fmtTime(d.last_seen) : "never"}</div>
    </div>`).join("");

  const sel = $("feedSelect"), current = sel.value;
  const opts = ['<option value="__local">This laptop\'s webcam</option>']
    .concat(devices.filter((d) => d.has_frame).map((d) => `<option value="${esc(d.id)}">${esc(d.id)}</option>`));
  if (sel.options.length !== opts.length) { sel.innerHTML = opts.join(""); sel.value = current; if (!sel.value) sel.value = "__local"; }

  const cSel = $("chartDevice"), cCur = cSel.value;
  const cOpts = ['<option value="">All devices</option>'].concat(devices.map((d) => `<option value="${esc(d.id)}">${esc(d.id)}</option>`));
  if (cSel.options.length !== cOpts.length) { cSel.innerHTML = cOpts.join(""); cSel.value = cCur; }
}

function renderCamera(s) {
  cameraRunning = s.camera.running;
  const feed = $("feedSelect").value;
  const img = $("video");
  if (feed === "__local") {
    $("camBtn").hidden = false;
    $("camBtn").textContent = cameraRunning ? "Stop camera" : "Start camera";
    if (cameraRunning && !img.src.includes("/video_feed")) img.src = "/video_feed";
    if (!cameraRunning) img.removeAttribute("src");
    img.hidden = !cameraRunning;
    $("videoPlaceholder").hidden = cameraRunning;
    const info = [];
    if (cameraRunning) info.push(`${s.camera.fps} FPS`, `detector: ${s.camera.mode || "loading"}`);
    if (s.camera.mode === "demo") info.push("⚠ demo colour detector - put trained weights in model/weights/best.pt");
    if (s.camera.error) info.push(`error: ${s.camera.error}`);
    $("camInfo").textContent = info.join(" · ");
  } else {
    $("camBtn").hidden = true;
    img.hidden = false; $("videoPlaceholder").hidden = true;
    img.src = `/api/devices/${encodeURIComponent(feed)}/frame.jpg?t=${Date.now()}`;
    $("camInfo").textContent = `Preview frames from ${feed} (about 1 per second)`;
  }
}

function renderEvents(events) {
  if (!events.length) return;
  $("eventsBody").innerHTML = events.map((e) => `
    <tr class="${e.acknowledged ? "" : "unack"}">
      <td>${new Date(e.ts * 1000).toLocaleString()}</td>
      <td>${esc(e.device)}</td>
      <td class="lvl lvl-${esc(e.level)}">${esc(e.level)}</td>
      <td>${esc(e.label || "-")}${e.detector_mode === "demo" ? '<span class="tag">demo</span>' : ""}</td>
      <td>${e.confidence !== null ? Math.round(e.confidence * 100) + "%" : "-"}</td>
      <td>${fmt(e.temperature)} °C / ${fmt(e.smoke, 0)} %</td>
      <td>${e.snapshot ? `<img class="thumb" src="/static/snapshots/${encodeURIComponent(e.snapshot)}" alt="snapshot">` : "-"}</td>
      <td>${e.acknowledged ? '<span class="muted small">ack</span>' : `<button class="btn btn-small" data-ack="${e.id}">Ack</button>`}</td>
    </tr>`).join("");
}

async function renderChart() {
  if (typeof Chart === "undefined") { $("chartNote").textContent = "Chart library could not load (offline?)."; return; }
  const device = $("chartDevice").value;
  const rows = await api(`/api/readings?minutes=30${device ? `&device=${encodeURIComponent(device)}` : ""}`);
  const points = (k) => rows.filter((r) => r[k] !== null).map((r) => ({ x: r.ts * 1000, y: r[k] }));
  const data = {
    datasets: [
      { label: "Temperature °C", data: points("temperature"), borderColor: "#e85d04", yAxisID: "y", pointRadius: 0, tension: .3 },
      { label: "Smoke %", data: points("smoke"), borderColor: "#6b7280", yAxisID: "y1", pointRadius: 0, tension: .3 },
    ],
  };
  $("chartNote").textContent = rows.length ? "" : "No sensor data yet - start the Raspberry Pi monitor (or run it with --simulate).";
  if (!chart) {
    chart = new Chart($("sensorChart"), {
      type: "line", data,
      options: {
        animation: false, maintainAspectRatio: false, parsing: false,
        interaction: { mode: "nearest", axis: "x", intersect: false },
        scales: {
          x: { type: "linear", ticks: { callback: (v) => new Date(v).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) } },
          y: { position: "left", title: { display: true, text: "°C" } },
          y1: { position: "right", min: 0, max: 100, grid: { drawOnChartArea: false }, title: { display: true, text: "smoke %" } },
        },
      },
    });
  } else { chart.data = data; chart.update(); }
}

async function tick() {
  try {
    const [status, events] = await Promise.all([api("/api/status"), api("/api/events?limit=30")]);
    renderStatus(status); renderEvents(events);
  } catch (err) { $("bannerText").textContent = `Dashboard server not reachable (${err.message})`; }
  $("clock").textContent = new Date().toLocaleTimeString();
}

$("camBtn").addEventListener("click", async () => {
  await api(cameraRunning ? "/api/camera/stop" : "/api/camera/start", { method: "POST" });
  tick();
});
$("ackAll").addEventListener("click", async () => { await api("/api/events/ack_all", { method: "POST" }); tick(); });
$("eventsBody").addEventListener("click", async (ev) => {
  const id = ev.target.dataset.ack;
  if (id) { await api(`/api/events/${id}/ack`, { method: "POST" }); tick(); }
  if (ev.target.classList.contains("thumb")) { $("lightbox").querySelector("img").src = ev.target.src; $("lightbox").hidden = false; }
});
$("lightbox").addEventListener("click", () => { $("lightbox").hidden = true; });
$("feedSelect").addEventListener("change", tick);
$("chartDevice").addEventListener("change", renderChart);

tick();
renderChart();
setInterval(tick, POLL_MS);
setInterval(renderChart, 10000);
