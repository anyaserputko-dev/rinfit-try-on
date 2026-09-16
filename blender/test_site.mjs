// Headless check of the web app (no camera): 3D view and photo try-on snapshots.
//   node blender/test_site.mjs '[{"name":"oval_3d","q":"?ring=oval&spin=0"}, {"name":"oval_photo","q":"?ring=oval&photo=blender/test/right_hands.jpg&cpu=1"}]'
// Needs a static server on the project dir: python3 -m http.server 8766
// Frames are driven through window.__tryon.step(): in this headless Chrome requestAnimationFrame never fires.
import puppeteer from "/Users/annserputko/Desktop/штаб/_Технічне/scraper/движок/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js";
import fs from "fs";
import { fileURLToPath } from "url";

const BASE = "http://127.0.0.1:8766/index.html";
const OUT = fileURLToPath(new URL("./out/site/", import.meta.url));
const cases = JSON.parse(process.argv[2] || "[]");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

// Software WebGL (SwiftShader): with the GPU busy in Blender, GPU-backed headless Chrome stops producing frames.
const browser = await puppeteer.launch({
  headless: "new", protocolTimeout: 240000,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"]
});

async function until(page, fn, timeout, arg) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    const ok = await page.evaluate(fn, arg).catch(() => false);
    if (ok) return true;
    await sleep(400);
  }
  return false;
}

for (const c of cases) {
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errors.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => errors.push("PAGEERROR " + String(e).slice(0, 300)));
  page.on("requestfailed", (r) => errors.push("REQFAIL " + r.url().slice(0, 140)));
  page.on("response", (r) => { if (r.status() >= 400 && !r.url().endsWith("favicon.ico")) errors.push(`HTTP ${r.status()} ${r.url().slice(0, 140)}`); });
  await page.setViewport({ width: c.vw || 1280, height: c.vh || 1000, deviceScaleFactor: 1 });
  for (let i = 0; i < 20; i++) {
    try { await page.goto(BASE + (c.q || ""), { waitUntil: "domcontentloaded", timeout: 60000 }); break; }
    catch { await sleep(500); }
  }
  await page.bringToFront();
  const isPhoto = !!(c.q && c.q.includes("photo="));
  let status = "ok";
  const built = await until(page, () => window.__tryon && typeof window.__tryon.step === "function" && (window.__tryon.built || window.__tryon.error), 90000);
  if (!built) status = "TIMEOUT(build)";
  if (built && isPhoto) {
    const placed = await until(page, () => { window.__tryon.step(); return window.__tryon.placed || !!window.__tryon.error; }, c.timeout || 180000);
    if (!placed) status = "TIMEOUT(place)";
  }
  // a few frames so damping/orbit and materials settle, then read the canvas right after a frame
  const dataUrl = await page.evaluate((n) => {
    for (let i = 0; i < n; i++) window.__tryon.step?.();
    const gl = document.getElementById("gl"), photo = document.getElementById("photo");
    const out = document.createElement("canvas");
    out.width = gl.width; out.height = gl.height;
    const g = out.getContext("2d");
    g.fillStyle = "#e9e4e1";
    g.fillRect(0, 0, out.width, out.height);
    if (!photo.hidden && photo.naturalWidth) {
      const sc = Math.min(out.width / photo.naturalWidth, out.height / photo.naturalHeight);
      g.drawImage(photo, (out.width - photo.naturalWidth * sc) / 2, (out.height - photo.naturalHeight * sc) / 2,
        photo.naturalWidth * sc, photo.naturalHeight * sc);
    }
    g.drawImage(gl, 0, 0);
    const edges = window.__tryon.edges;   // where the finger's edges were measured, in stage pixels
    if (edges) {
      const stage = document.getElementById("stage").getBoundingClientRect();
      const k = out.width / stage.width;
      g.strokeStyle = "#ff2d55";
      g.lineWidth = 2;
      for (const [x, y] of edges) {
        const cx = x * k, cy = -y * k;
        g.beginPath();
        g.moveTo(cx - 9, cy); g.lineTo(cx + 9, cy);
        g.moveTo(cx, cy - 9); g.lineTo(cx, cy + 9);
        g.stroke();
      }
    }
    return out.toDataURL("image/png");
  }, c.frames || 30);
  const info = await page.evaluate(() => ({
    built: window.__tryon?.built, placed: window.__tryon?.placed, error: window.__tryon?.error, debug: window.__tryon?.debug,
    fit: window.__tryon?.fit,
    hint: document.getElementById("hint").hidden ? "" : document.getElementById("hint").textContent
  }));
  const file = `${OUT}${c.name}.png`;
  fs.writeFileSync(file, Buffer.from(dataUrl.split(",")[1], "base64"));
  console.log(`${c.name}: ${status} built=${info.built} placed=${info.placed} err=${info.error || "-"} debug=${JSON.stringify(info.debug)} fit=${JSON.stringify(info.fit)} hint="${info.hint}" -> ${file}`);
  if (errors.length) console.log("  console:", [...new Set(errors)].slice(0, 8).join(" || "));
  await page.close();
}
await browser.close();
