const state = {
  shirtUrl: null,
  pantUrl: null,
  modelUrl: null,
  prev: {},
  character: { age: 8, gender: "boy" },
  videos: [],          // every generated video, newest last
};

const $ = (id) => document.getElementById(id);

// ---------- character (class → age) ----------
const CLASSES = [
  ["Playgroup", 3], ["Nursery", 4], ["KG", 5],
  ...Array.from({ length: 12 }, (_, i) => [`Class ${i + 1}`, i + 6]),
  ["O Level / Matric", 15], ["A Level", 17], ["Intermediate", 17],
];
$("charClass").innerHTML = CLASSES.map(([label, age]) => `<option value="${age}">${label}</option>`).join("");

function renderCharacter(c) {
  const opt = [...$("charClass").options].find((o) => o.textContent === c.classLabel)
    || [...$("charClass").options].find((o) => Number(o.value) === c.age);
  if (opt) opt.selected = true;
  $("charGender").value = c.gender;
  $("charNote").textContent = c.detected
    ? `Detected: ${c.classLabel} — change it if needed`
    : "Pick the class so the model matches the age";
  updateCharacter();
}
function updateCharacter() {
  state.character = { age: Number($("charClass").value), gender: $("charGender").value };
  $("charAge").textContent = `~${state.character.age} yrs`;
  $("charAvatar").textContent = state.character.gender === "girl" ? "👧" : "👦";
}
$("charClass").addEventListener("change", updateCharacter);
$("charGender").addEventListener("change", updateCharacter);

// ---------- theme ----------
try {
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.dataset.theme = saved;
} catch {}
$("themeBtn").addEventListener("click", () => {
  const root = document.documentElement;
  const dark = root.dataset.theme
    ? root.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("theme", root.dataset.theme); } catch {}
});

// ---------- helpers ----------
let timer;
function busy(text) {
  $("overlayText").textContent = text;
  $("overlayTimer").textContent = "0s";
  $("overlay").hidden = false;
  const start = Date.now();
  timer = setInterval(() => {
    $("overlayTimer").textContent = `${Math.round((Date.now() - start) / 1000)}s`;
  }, 1000);
}
function idle() {
  clearInterval(timer);
  $("overlay").hidden = true;
}
function showError(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(t._h);
  t._h = setTimeout(() => (t.hidden = true), 8000);
}

async function api(path, options) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Long jobs run in the background on the server: start one, then poll until it finishes.
async function runJob(path, options) {
  const { jobId } = await api(path, options);
  while (true) {
    await sleep(2500);
    const job = await api(`/api/job/${jobId}`);
    if (job.status === "done") return job.result;
    if (job.status === "error") throw new Error(job.error);
  }
}

const postJSON = (path, body) =>
  runJob(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

async function run(text, fn) {
  busy(text);
  try { await fn(); } catch (e) { showError(e.message); } finally { idle(); }
}

function setStep(n) {
  document.querySelectorAll(".step").forEach((el) => {
    const s = Number(el.dataset.step);
    el.classList.toggle("active", s === n);
    el.classList.toggle("done", s < n);
  });
  document.querySelectorAll(".line").forEach((el, i) => el.classList.toggle("done", i + 1 < n));
}

// A tile with a download link and optional "hold to compare with the previous version"
function tile(label, url, { video = false, prev = null } = {}) {
  const media = video
    ? `<video src="${url}" controls loop playsinline></video>`
    : `<img src="${url}" alt="${label}">`;
  const compare = prev && prev !== url
    ? `<button type="button" class="compare" data-prev="${prev}" data-cur="${url}">Hold to see before</button>`
    : "";
  return `<figure class="tile">
      <div class="media">${media}<span class="badge">${label}</span>${compare}</div>
      <figcaption>${label}<a href="${url}" target="_blank" rel="noopener" download>Download ↓</a></figcaption>
    </figure>`;
}

function renderGarments() {
  let html = tile("Shirt", state.shirtUrl, { prev: state.prev.shirt });
  if (state.pantUrl) html += tile("Pant", state.pantUrl, { prev: state.prev.pant });
  $("garments").innerHTML = html;
  $("step2").hidden = false;
}
function renderModel() {
  $("modelResult").innerHTML = tile("Model", state.modelUrl, { prev: state.prev.model });
  $("step3").hidden = false;
}
const reveal = (id) => $(id).scrollIntoView({ behavior: "smooth", block: "start" });

// ---------- global clicks: lightbox, chips ----------
document.addEventListener("click", (e) => {
  const img = e.target.closest(".tile img");
  if (img) {
    $("lightbox").querySelector("img").src = img.src;
    $("lightbox").hidden = false;
  }
  const chip = e.target.closest(".chip");
  if (chip) {
    const ta = chip.closest("form").querySelector("textarea");
    ta.value = ta.value.trim() ? `${ta.value.trim()}, ${chip.textContent.toLowerCase()}` : chip.textContent;
    ta.focus();
  }
});
$("lightbox").addEventListener("click", () => ($("lightbox").hidden = true));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("lightbox").hidden = true; });

// ---------- hold a tile's button to see the previous version ----------
function swapCompare(e, showPrev) {
  const btn = e.target.closest(".compare");
  if (!btn) return;
  e.preventDefault();
  btn.parentElement.querySelector("img").src = showPrev ? btn.dataset.prev : btn.dataset.cur;
  btn.textContent = showPrev ? "Before" : "Hold to see before";
}
document.addEventListener("pointerdown", (e) => swapCompare(e, true));
["pointerup", "pointerleave", "pointercancel"].forEach((ev) =>
  document.addEventListener(ev, (e) => swapCompare(e, false), true));

// ---------- dropzones ----------
document.querySelectorAll(".drop").forEach((drop) => {
  const input = drop.querySelector("input");
  const preview = drop.querySelector(".drop-preview");
  const clear = drop.querySelector(".clear");

  const show = (file) => {
    if (!file) return;
    preview.src = URL.createObjectURL(file);
    preview.hidden = false;
    drop.classList.add("filled");
    clear.hidden = false;
  };

  input.addEventListener("change", () => show(input.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("drag"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("drag");
    const file = e.dataTransfer.files[0];
    if (!file || !file.type.startsWith("image/")) return showError("Please drop an image file.");
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    show(file);
  });
  clear.addEventListener("click", (e) => {
    e.preventDefault();
    input.value = "";
    preview.hidden = true;
    drop.classList.remove("filled");
    clear.hidden = true;
  });
});

// ---------- step 1: upload ----------
$("uploadForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  if (!form.get("shirt")?.size) return showError("A shirt image is required.");
  if (!form.get("pant")?.size) form.delete("pant");
  run("Creating realistic photos… usually 30–60s", async () => {
    const data = await runJob("/api/upload", { method: "POST", body: form });
    Object.assign(state, { shirtUrl: data.shirtUrl, pantUrl: data.pantUrl, prev: {} });
    renderCharacter(data.character);
    renderGarments();
    setStep(2);
    reveal("step2");
  });
});

// ---------- step 2: improve ----------
$("improveForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const feedback = new FormData(e.target).get("feedback").trim();
  if (!feedback) return showError("Describe what you want changed first.");
  run("Applying your feedback…", async () => {
    const data = await postJSON("/api/improve", { shirtUrl: state.shirtUrl, pantUrl: state.pantUrl, feedback });
    state.prev.shirt = state.shirtUrl;
    state.prev.pant = state.pantUrl;
    state.shirtUrl = data.shirtUrl;
    state.pantUrl = data.pantUrl;
    renderGarments();
    e.target.reset();
  });
});

// ---------- step 3: model ----------
$("toModel").addEventListener("click", () => {
  run("Dressing the model… usually 30–60s", async () => {
    const data = await postJSON("/api/model", {
      shirtUrl: state.shirtUrl,
      pantUrl: state.pantUrl,
      character: state.character,
    });
    state.modelUrl = data.modelUrl;
    state.prev.model = null;
    renderModel();
    setStep(3);
    reveal("step3");
  });
});

$("editForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const instruction = new FormData(e.target).get("instruction").trim();
  if (!instruction) return showError("Describe what you want changed first.");
  run("Editing the model image…", async () => {
    const data = await postJSON("/api/edit-model", { modelUrl: state.modelUrl, instruction });
    state.prev.model = state.modelUrl;
    state.modelUrl = data.modelUrl;
    renderModel();
    e.target.reset();
  });
});

// ---------- step 4: video (generate + edit) ----------
function showVideo(index) {
  const v = state.videos[index];
  $("videoResult").innerHTML = tile(`Video · ${v.duration}s`, v.url, { video: true });
  $("videoPrompt").textContent = v.prompt;
  renderVideoRail(index);
  $("step4").hidden = false;
}

function renderVideoRail(current) {
  const others = state.videos.map((v, i) => ({ v, i })).filter(({ i }) => i !== current);
  $("videoVersions").hidden = others.length === 0;
  $("videoRail").innerHTML = others
    .map(({ v, i }) => `<button type="button" data-index="${i}">
        <video src="${v.url}" muted preload="metadata"></video>
        <span>v${i + 1} · ${v.duration}s</span>
      </button>`)
    .join("");
}

$("videoRail").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-index]");
  if (btn) showVideo(Number(btn.dataset.index));
});

function generateVideo(instruction) {
  const duration = Number($("videoDuration").value);
  const label = instruction ? "Regenerating the video…" : "Generating the video…";
  return run(`${label} this can take 1–3 minutes`, async () => {
    const data = await postJSON("/api/video", {
      modelUrl: state.modelUrl,
      character: state.character,
      instruction: instruction || null,
      duration,
    });
    state.videos.push({ url: data.videoUrl, prompt: data.prompt, duration: data.duration });
    showVideo(state.videos.length - 1);
    setStep(4);
    reveal("step4");
  });
}

$("toVideo").addEventListener("click", () => generateVideo(null));

$("videoEditForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const instruction = new FormData(e.target).get("instruction").trim();
  if (!instruction) return showError("Describe what you want changed in the video.");
  generateVideo(instruction);
});

$("restart").addEventListener("click", () => location.reload());
