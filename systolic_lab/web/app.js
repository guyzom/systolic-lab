"use strict";
const $ = (id) => document.getElementById(id);
const form = $("config");
let simulation = null, current = 0, timer = null, selected = [0, 0], busy = false;
const percent = (x) => (x * 100).toFixed(1) + "%";
const number = (x) => x.toLocaleString("en-US");
function parameters(demo = false, trace = true) {
  const p = new URLSearchParams(new FormData(form));
  p.set("demo", demo ? "1" : "0"); p.set("trace", trace ? "1" : "0"); return p;
}
async function fetchSimulation(params) {
  const response = await fetch("/api/simulate?" + params);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Simulation failed");
  return data;
}
function status(message, error = false) {
  $("status").textContent = message; $("status").className = error ? "error" : "";
}
function lock(value) {
  busy = value;
  for (const button of document.querySelectorAll("form button, #compare")) button.disabled = value;
}
function stop() { clearInterval(timer); timer = null; $("play").textContent = "Play"; $("play").setAttribute("aria-label", "Play cycles"); }
function table(matrix, target) {
  const element = document.createElement("table");
  for (const row of matrix) {
    const tr = element.insertRow();
    for (const value of row) tr.insertCell().textContent = value;
  }
  target.replaceChildren(element);
}
function metric(label, value, sub) {
  const element = document.createElement("div"); element.className = "metric";
  const title = document.createElement("span"), main = document.createElement("strong"), note = document.createElement("small");
  title.textContent = label; main.textContent = value; note.textContent = sub;
  element.append(title, main, note); return element;
}
function svg(tag, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}
function buildTimeline() {
  const frames = simulation.frames, pes = simulation.config.rows * simulation.config.cols;
  const parts = [], color = {load: "#a5a2e8", compute: "#7bddc1", store: "#f8b982"};
  // Group phase regions; trace length can be thousands of cycles.
  let start = 0;
  for (let index = 1; index <= frames.length; index++) {
    if (index === frames.length || frames[index].phase !== frames[start].phase) {
      parts.push(svg("rect", {x: start / frames.length * 800, y: 56,
        width: (index - start) / frames.length * 800, height: 5, fill: color[frames[start].phase]}));
      start = index;
    }
  }
  const points = frames.map((frame, index) => `${(index + .5) / frames.length * 800},${50 - frame.active_macs / pes * 43}`).join(" ");
  parts.push(svg("polyline", {points, fill: "none", stroke: "#7bddc1", "stroke-width": "1.5"}));
  parts.push(svg("line", {id: "timeline-cursor", x1: 0, x2: 0, y1: 0, y2: 64, stroke: "#e9eef1", "stroke-width": 1}));
  $("timeline").replaceChildren(...parts);
}
function render() {
  if (!simulation) return;
  const frame = simulation.frames[current], tile = simulation.tiles[frame.tile], config = simulation.config;
  $("phase").textContent = frame.phase.toUpperCase(); $("phase").className = "phase-badge " + frame.phase;
  $("tile-title").textContent = `Tile ${frame.tile + 1} / ${simulation.tiles.length} · C[${tile.row}:${tile.row + tile.height}, ${tile.col}:${tile.col + tile.width}]`;
  $("cycle-label").textContent = `Clock ${frame.cycle} · ${frame.phase} cycle ${frame.phase_cycle}`;
  $("active-label").textContent = `${frame.active_macs} / ${config.rows * config.cols} active MACs`;
  $("array").style.gridTemplateColumns = `repeat(${config.cols}, minmax(90px, 1fr))`;
  const cells = [];
  for (let i = 0; i < config.rows; i++) for (let j = 0; j < config.cols; j++) {
    const cell = frame.cells[i][j], button = document.createElement("button");
    button.className = "pe" + (cell.active ? " active" : "") + (cell.masked ? " masked" : "") + (i === selected[0] && j === selected[1] ? " selected" : "");
    button.setAttribute("aria-label", `PE ${i}, ${j}; ${cell.masked ? "masked" : cell.active ? "active" : "idle"}; accumulator ${cell.acc}`);
    const address = document.createElement("span"), operands = document.createElement("div"), a = document.createElement("span"), b = document.createElement("span"), accumulator = document.createElement("span"), k = document.createElement("span");
    address.className = "address"; address.textContent = `PE ${i},${j}`;
    operands.className = "operands"; a.className = "signal-a"; b.className = "signal-b";
    a.textContent = "A " + (cell.a ?? "·") + " →"; b.textContent = "B " + (cell.b ?? "·") + " ↓";
    accumulator.className = "acc"; accumulator.textContent = cell.masked ? "masked" : cell.acc;
    k.className = "k"; k.textContent = cell.k === null ? "" : `k=${cell.k}`;
    accumulator.append(k); operands.append(a, b); button.append(address, operands, accumulator);
    button.addEventListener("click", () => { selected = [i, j]; render(); }); cells.push(button);
  }
  $("array").replaceChildren(...cells);
  const cell = frame.cells[selected[0]][selected[1]];
  $("pe-detail").textContent = cell.masked ? `PE[${selected}] is outside this tile; it consumes no operands and performs no MAC.` :
    `PE[${selected}] → C[${tile.row + selected[0]},${tile.col + selected[1]}] · ` + (cell.active ? `${cell.acc - cell.a * cell.b} + (${cell.a} × ${cell.b}) = ${cell.acc} · k=${cell.k}` : `accumulator ${cell.acc} · no MAC this cycle`);
  $("clock").value = current; $("clock-total").textContent = `${frame.cycle} / ${simulation.frames.length}`;
  $("back").disabled = current === 0; $("next").disabled = current === simulation.frames.length - 1;
  const cursor = $("timeline-cursor"), x = (current + .5) / simulation.frames.length * 800;
  cursor.setAttribute("x1", x); cursor.setAttribute("x2", x);
  $("memory-title").textContent = frame.phase === "compute" ? "Operands resident in scratchpad" : frame.setup ? `${frame.phase}: transaction setup` : `${frame.phase}: ${frame.transfer_bytes} bytes this cycle`;
  $("memory-progress").max = frame.transaction_bytes || 1; $("memory-progress").value = frame.phase === "compute" ? 1 : frame.transferred_bytes;
  $("memory-description").textContent = frame.phase === "compute" ? `${tile.load_bytes} operand bytes fit in ${number(config.scratchpad)} bytes. No external traffic during compute.` : `${frame.transferred_bytes} / ${frame.transaction_bytes} bytes transferred. ${config.bandwidth} B/cycle bus, ${config.latency} setup cycles per transaction.`;
}
async function run(demo = false) {
  if (busy) return;
  stop(); lock(true); status("Simulating and checking exact dot products…");
  try {
    const data = await fetchSimulation(parameters(demo)); simulation = data; selected = [0, 0];
    current = data.frames.findIndex((f) => f.phase === "compute" && f.phase_cycle === 2);
    if (current < 0) current = data.frames.findIndex((f) => f.phase === "compute");
    $("clock").max = data.frames.length - 1;
    const m = data.metrics;
    $("metrics").replaceChildren(metric("Total cycles", number(m.total_cycles), `${m.load_cycles} load · ${m.compute_cycles} compute · ${m.store_cycles} store`),
      metric("Compute utilization", percent(m.compute_utilization), "Useful MACs / compute PE cycles"),
      metric("Overall utilization", percent(m.overall_utilization), "Includes load and store cycles"),
      metric("External traffic", number(m.external_bytes) + " B", `${m.tile_count} tiles · ${m.link_bytes} B on mesh links`));
    $("traffic").replaceChildren();
    for (const [label, value] of [["Operand loads", `${m.load_bytes} B`], ["Output stores", `${m.store_bytes} B`], ["Mesh operand hops", `${m.link_bytes} B`], ["Operational intensity", `${m.macs_per_external_byte.toFixed(2)} MAC/B`]]) {
      const dt = document.createElement("dt"), dd = document.createElement("dd"); dt.textContent = label; dd.textContent = value; $("traffic").append(dt, dd);
    }
    $("verification").textContent = data.verified ? "Exact reference match ✓" : "Reference mismatch";
    table(data.result, $("result-matrix")); table(data.a, $("matrix-a")); table(data.b, $("matrix-b"));
    $("result-note").textContent = `${m.useful_macs} useful MACs. Final C is shown; PE values above follow the selected cycle.`;
    $("comparison").replaceChildren(); const hint = document.createElement("p"); hint.className = "muted"; hint.textContent = "Run the comparison to see the tradeoff."; $("comparison").append(hint);
    buildTimeline(); render(); status(`${data.input_kind} · ${data.shape.m}×${data.shape.k} · ${data.shape.k}×${data.shape.n}` + (data.seed === null ? "" : ` · seed ${data.seed}`));
  } catch (error) { status(error.message + (simulation ? " Previous result remains shown." : ""), true); }
  finally { lock(false); }
}
form.addEventListener("submit", (event) => { event.preventDefault(); run(); });
$("demo").addEventListener("click", () => {
  for (const [key, value] of Object.entries({m: 2, k: 3, n: 2, rows: 2, cols: 2, bandwidth: 8, latency: 1, scratchpad: 32768})) form.elements[key].value = value;
  run(true);
});
$("clock").addEventListener("input", () => { stop(); current = Number($("clock").value); render(); });
$("back").addEventListener("click", () => { stop(); current = Math.max(0, current - 1); render(); });
$("next").addEventListener("click", () => { stop(); current = Math.min(simulation.frames.length - 1, current + 1); render(); });
$("play").addEventListener("click", () => {
  if (!simulation) return;
  if (timer) { stop(); return; }
  if (current === simulation.frames.length - 1) current = 0;
  $("play").textContent = "Pause"; $("play").setAttribute("aria-label", "Pause cycles");
  timer = setInterval(() => { if (current >= simulation.frames.length - 1) { stop(); return; } current++; render(); }, 420);
});
$("download").addEventListener("click", () => {
  if (!simulation) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(simulation, null, 2) + "\n"], {type: "application/json"}));
  const a = document.createElement("a"); a.href = url; a.download = "systolic-trace.json"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("compare").addEventListener("click", async () => {
  if (!simulation || busy) return;
  stop(); lock(true); status("Comparing array sizes on the loaded workload…");
  try {
    const element = document.createElement("table"), head = element.createTHead().insertRow();
    let failures = 0;
    for (const title of ["Array", "Cycles", "Compute util.", "Overall util.", "External B"]) { const th = document.createElement("th"); th.textContent = title; head.append(th); }
    for (const size of [2, 4, 8]) {
      const p = new URLSearchParams({...simulation.shape, ...simulation.config, seed: simulation.seed ?? 7, rows: size, cols: size, trace: 0, demo: simulation.seed === null ? 1 : 0});
      const row = element.insertRow(); row.insertCell().textContent = `${size}×${size}`;
      try {
        const data = await fetchSimulation(p), m = data.metrics;
        for (const value of [m.total_cycles, percent(m.compute_utilization), percent(m.overall_utilization), m.external_bytes]) row.insertCell().textContent = value;
      } catch (error) { failures++; const td = row.insertCell(); td.colSpan = 4; td.textContent = error.message; }
    }
    $("comparison").replaceChildren(element); status(failures ? `Comparison complete; ${failures} configurations could not run. See the table.` : "Comparison complete. Each result passed the independent reference check.", failures > 0);
  } catch (error) { status(error.message, true); }
  finally { lock(false); }
});
run(true);
