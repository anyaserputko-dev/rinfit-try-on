// A picture of the screen itself: the try-on, then the same screen after the shutter, with the card and its
// buttons. Page screenshots can stall in this headless Chrome, so each one is given a deadline and the run
// still reports what it managed to take.
//   node blender/card_shot.mjs "?ring=emerald&photo=blender/test/right_hands.jpg&cpu=1&finger=ring"
import puppeteer from "/Users/annserputko/Desktop/штаб/_Технічне/scraper/движок/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js";
import fs from "fs";
import { fileURLToPath } from "url";

const BASE = "http://127.0.0.1:8766/index.html";
const query = process.argv[2] || "?ring=emerald&photo=blender/test/right_hands.jpg&cpu=1&finger=ring";
const OUT = fileURLToPath(new URL("./out/site/", import.meta.url));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const deadline = (p, ms, what) =>
  Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error(`${what} timed out`)), ms))]);
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  headless: "new", protocolTimeout: 120000,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding"]
});
const page = await browser.newPage();
await page.setViewport({ width: 900, height: 1180, deviceScaleFactor: 1 });
await page.goto(BASE + query, { waitUntil: "domcontentloaded", timeout: 60000 });

const t0 = Date.now();
while (Date.now() - t0 < 120000) {
  const ok = await page.evaluate(() => { window.__tryon.step?.(); return window.__tryon.placed; }).catch(() => false);
  if (ok) break;
  await sleep(300);
}
await page.evaluate(() => { for (let i = 0; i < 20; i++) window.__tryon.step(); });

const clip = await page.evaluate(() => {
  const r = document.getElementById("stage").getBoundingClientRect();
  return { x: Math.round(r.x), y: Math.round(r.y), width: Math.round(r.width), height: Math.round(r.height) };
});

for (const [name, before] of [["screen_tryon", null], ["screen_card", () => document.getElementById("shot").click()]]) {
  if (before) {
    await page.evaluate(before);
    await sleep(1500);
  }
  try {
    await deadline(page.screenshot({ path: `${OUT}${name}.png`, clip }), 60000, name);
    console.log(`${name}: written`);
  } catch (e) {
    console.log(`${name}: ${e.message}`);
  }
}
await browser.close();
