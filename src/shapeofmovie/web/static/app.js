// Small progressive enhancements on top of HTMX. No framework, no build step.

// --- upload: file name in the drop zone, progress bar, form reset --------------
document.addEventListener("change", (e) => {
  if (!e.target.matches("#dropzone input[type=file]")) return;
  const text = e.target.closest("#dropzone").querySelector(".dropzone-text");
  const f = e.target.files[0];
  text.textContent = f ? `${f.name} · ${(f.size / 1e6).toFixed(1)} Mo` : text.dataset.empty;
});

for (const type of ["dragenter", "dragover"]) {
  document.addEventListener(type, (e) => {
    const zone = e.target.closest && e.target.closest("#dropzone");
    if (zone) zone.classList.add("dragging");
  });
}
for (const type of ["dragleave", "drop"]) {
  document.addEventListener(type, (e) => {
    const zone = e.target.closest && e.target.closest("#dropzone");
    if (zone) zone.classList.remove("dragging");
  });
}

document.addEventListener("htmx:xhr:progress", (e) => {
  if (e.target.id !== "upload-form" || !e.detail.lengthComputable) return;
  const pct = Math.round((e.detail.loaded / e.detail.total) * 100);
  const bar = document.getElementById("upload-progress");
  bar.hidden = false;
  bar.value = pct;
  document.getElementById("upload-status").textContent = pct < 100 ? `Envoi… ${pct} %` : "Envoi terminé";
});

document.addEventListener("htmx:afterRequest", (e) => {
  if (e.target.id !== "upload-form") return;
  document.getElementById("upload-progress").hidden = true;
  document.getElementById("upload-status").textContent = e.detail.successful ? "" : "Échec de l'envoi";
  if (e.detail.successful) {
    e.target.reset();
    e.target.querySelector("input[type=file]").dispatchEvent(new Event("change", { bubbles: true }));
  }
});

// --- interactive timeline -------------------------------------------------------
function fmtTime(s) {
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  const mm = h ? String(m).padStart(2, "0") : m;
  return (h ? `${h}:` : "") + `${mm}:${String(sec).padStart(2, "0")}`;
}

async function initTimeline(el) {
  const data = await (await fetch(el.dataset.src)).json();
  const colors = data.colors;
  const step = data.step || 1;
  const canvas = el.querySelector("canvas");
  const cursor = el.querySelector(".cursor");
  const tip = el.querySelector(".tooltip");

  function draw() {
    const dpr = window.devicePixelRatio || 1;
    const w = el.clientWidth, h = el.clientHeight;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext("2d");
    const cols = canvas.width;
    // each pixel column shows the average of the samples it covers
    for (let x = 0; x < cols; x++) {
      const a = Math.floor((x / cols) * colors.length);
      const b = Math.max(a + 1, Math.floor(((x + 1) / cols) * colors.length));
      let r = 0, g = 0, bl = 0;
      for (let i = a; i < b; i++) {
        const v = parseInt(colors[i], 16);
        r += v >> 16; g += (v >> 8) & 255; bl += v & 255;
      }
      const n = b - a;
      ctx.fillStyle = `rgb(${r / n | 0},${g / n | 0},${bl / n | 0})`;
      ctx.fillRect(x, 0, 1, canvas.height);
    }
  }

  el.addEventListener("mousemove", (e) => {
    const rect = el.getBoundingClientRect();
    const x = Math.min(Math.max(e.clientX - rect.left, 0), rect.width - 1);
    const i = Math.min(colors.length - 1, Math.floor((x / rect.width) * colors.length));
    cursor.hidden = tip.hidden = false;
    cursor.style.left = `${x}px`;
    tip.querySelector(".swatch").style.background = `#${colors[i]}`;
    tip.querySelector(".tt-text").textContent = `${fmtTime(i * step)} · #${colors[i]}`;
    const tw = tip.offsetWidth;
    tip.style.left = `${Math.min(Math.max(x - tw / 2, 0), rect.width - tw)}px`;
  });
  el.addEventListener("mouseleave", () => { cursor.hidden = tip.hidden = true; });

  draw();
  new ResizeObserver(draw).observe(el);
  el.dataset.ready = "1";
}

document.querySelectorAll(".timeline[data-src]").forEach(initTimeline);
