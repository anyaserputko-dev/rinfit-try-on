// Does the ring sit still? On a photo the hand never moves, so any change between two canvas grabs is our
// own jitter. Grabs the canvas, runs many frames, grabs again, and reports how many pixels changed.
// A second argument shakes the landmarks by that many pixels every frame, the way live tracking does, so the
// smoothing can be measured against ?smooth=0.
//   node blender/stability.mjs "?ring=emerald&photo=blender/test/right_hands.jpg&cpu=1&finger=ring" 3
import puppeteer from "/Users/annserputko/Desktop/штаб/_Технічне/scraper/движок/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js";

const BASE = "http://127.0.0.1:8766/index.html";
const query = process.argv[2] || "?ring=emerald&photo=blender/test/right_hands.jpg&cpu=1&finger=ring";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  headless: "new", protocolTimeout: 240000,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding"]
});
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 1000 });
await page.goto(BASE + query, { waitUntil: "domcontentloaded", timeout: 60000 });

const t0 = Date.now();
while (Date.now() - t0 < 180000) {
  const ok = await page.evaluate(() => { window.__tryon.step?.(); return window.__tryon.placed; }).catch(() => false);
  if (ok) break;
  await sleep(300);
}

const out = await page.evaluate(async (shake) => {
  window.__tryon.jitter = shake;
  const gl = document.getElementById("gl");
  const grab = () => {
    const c = document.createElement("canvas");
    c.width = gl.width; c.height = gl.height;
    c.getContext("2d").drawImage(gl, 0, 0);
    return c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
  };
  const run = (n) => { for (let i = 0; i < n; i++) window.__tryon.step(); };
  run(40);                       // let the filter settle
  const a = grab();
  run(5);
  const b = grab();              // five frames later: what a person sees as shivering
  run(120);
  const c = grab();              // and much later: has it drifted?
  const diff = (x, y) => {
    let moved = 0, sum = 0;
    for (let i = 0; i < x.length; i += 4) {
      const d = Math.abs(x[i] - y[i]) + Math.abs(x[i + 1] - y[i + 1]) + Math.abs(x[i + 2] - y[i + 2]) + Math.abs(x[i + 3] - y[i + 3]);
      if (d > 24) moved++;
      sum += d;
    }
    return { moved, mean: +(sum / (x.length / 4)).toFixed(2) };
  };
  return { short: diff(a, b), long: diff(a, c), debug: window.__tryon.debug, fit: window.__tryon.fit };
}, +(process.argv[3] || 0));

console.log(query, process.argv[3] ? `jitter ${process.argv[3]} px` : "");
console.log(`  5 frames later : ${out.short.moved} pixels changed (mean ${out.short.mean})`);
console.log(`  160 frames later: ${out.long.moved} pixels changed (mean ${out.long.mean})`);
console.log(`  debug: ${JSON.stringify(out.debug)}`);
await browser.close();
