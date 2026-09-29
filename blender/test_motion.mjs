// How well the ring keeps up with a MOVING hand: a fake camera plays a clip of a hand panning about; on every
// sample the page freezes the displayed frame, draws the ring for it, then a separate still-image tracker finds
// where the finger really is on that same frame. Error = distance from the ring to that spot, in finger widths.
//   node blender/test_motion.mjs '{"name":"base","cam":"blender/test/anna/move.y4m","q":"?ring=emerald&cpu=1","secs":14}'
import puppeteer from "/Users/annserputko/Desktop/штаб/_Технічне/scraper/движок/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js";
import path from "path";
import { fileURLToPath } from "url";
const ROOT = fileURLToPath(new URL("../", import.meta.url));
const c = JSON.parse(process.argv[2]);
const browser = await puppeteer.launch({
  headless: "new", protocolTimeout: 240000,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
         `--use-file-for-fake-video-capture=${path.resolve(ROOT, c.cam)}`,
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"]
});
const page = await browser.newPage();
await page.setViewport({ width: 1100, height: 800, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:8766/index.html" + (c.q || ""), { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => window.__tryon?.built, { timeout: 90000 });
await page.click("#mode-live");
await page.waitForFunction(() => { window.__tryon.step?.(); return window.__tryon.ring; }, { timeout: 120000, polling: 200 });
await page.evaluate(async () => {
  const MP = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1";
  const { FilesetResolver, HandLandmarker } = await import(`${MP}/vision_bundle.mjs`);
  const files = await FilesetResolver.forVisionTasks(`${MP}/wasm`);
  window.__gt = await HandLandmarker.createFromOptions(files, { baseOptions: {
    modelAssetPath: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task", delegate: "CPU" },
    runningMode: "IMAGE", numHands: 1 });
  window.__snap = document.createElement("canvas");
  setInterval(() => window.__tryon.step(), 16);      // the screen keeps drawing between samples, like rAF would
});
const rows = [];
const t0 = Date.now();
while (Date.now() - t0 < (c.secs || 14) * 1000) {
  const r = await page.evaluate(async () => {
    const v = document.getElementById("video"), st = document.getElementById("stage");
    const s = window.__snap; s.width = v.videoWidth; s.height = v.videoHeight;
    s.getContext("2d").drawImage(v, 0, 0);           // the frame on screen right now
    window.__tryon.ring = null;
    window.__tryon.step();                             // the ring drawn for that same frame
    const ring = window.__tryon.ring;
    const res = window.__gt.detect(s);
    if (!ring || !res.landmarks?.length) return { ring: !!ring, gt: !!res.landmarks?.length };
    const w = st.clientWidth, h = st.clientHeight, sc = Math.max(w / s.width, h / s.height);
    const ox = (w - s.width * sc) / 2, oy = (h - s.height * sc) / 2;
    const L = res.landmarks[0], P = (i) => [ox + L[i].x * s.width * sc, oy + L[i].y * s.height * sc];
    const a = P(13), b = P(14);
    const ex = a[0] + (b[0] - a[0]) * ring.t, ey = a[1] + (b[1] - a[1]) * ring.t;
    return { ms2: window.__tryon.detectMs, ring: true, gt: true, err: Math.hypot(ring.x - ex, ring.y - ey) / ring.width, width: ring.width, gx: ex, gy: ey };
  });
  r.ms = Date.now() - t0;
  rows.push(r);
}
await browser.close();
const ok = rows.filter((r) => r.err !== undefined);
for (let i = 1; i < ok.length; i++) ok[i].move = Math.hypot(ok[i].gx - ok[i - 1].gx, ok[i].gy - ok[i - 1].gy) / ok[i].width;
const q = (a, p) => { const s = [...a].sort((x, y) => x - y); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : NaN; };
const still = ok.filter((r) => r.move !== undefined && r.move < 0.05), moving = ok.filter((r) => r.move >= 0.05);
const f = (x) => (isNaN(x) ? "-" : x.toFixed(3));
const widths = ok.map((r) => r.width), mw = widths.reduce((a, b) => a + b, 0) / (widths.length || 1);
const sd = Math.sqrt(widths.reduce((a, b) => a + (b - mw) ** 2, 0) / (widths.length || 1));
const dms = rows.length; console.log(`${c.name}: samples=${rows.length} ringShown=${rows.filter((r) => r.ring).length}/${rows.filter((r) => r.gt).length} ` +
  `still: med=${f(q(still.map((r) => r.err), 0.5))} p90=${f(q(still.map((r) => r.err), 0.9))} (n=${still.length}) ` +
  `moving: med=${f(q(moving.map((r) => r.err), 0.5))} p90=${f(q(moving.map((r) => r.err), 0.9))} (n=${moving.length}) ` +
  `fingerWidth: mean=${mw.toFixed(1)} sd=${sd.toFixed(2)} detectMs=${ok.length ? ok[ok.length-1].ms2 : '-'}`);
