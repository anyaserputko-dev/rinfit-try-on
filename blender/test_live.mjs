// Headless check of the LIVE try-on with a fake camera: Chrome plays a .y4m file as the webcam.
//   node blender/test_live.mjs '[{"name":"live_up","cam":"blender/test/live/up.y4m","q":"?ring=oval&finger=index&cpu=1"}]'
// Needs a static server on the project dir: python3 -m http.server 8766
import puppeteer from "/Users/annserputko/Desktop/штаб/_Технічне/scraper/движок/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const BASE = "http://127.0.0.1:8766/index.html";
const OUT = fileURLToPath(new URL("./out/live/", import.meta.url));
const cases = JSON.parse(process.argv[2] || "[]");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

for (const c of cases) {
  const browser = await puppeteer.launch({
    headless: "new", protocolTimeout: 240000,
    args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
           "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
           `--use-file-for-fake-video-capture=${path.resolve(ROOT, c.cam)}`,
           "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"]
  });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("PAGEERROR " + String(e).slice(0, 300)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 200)); });
  await page.setViewport({ width: c.vw || 430, height: c.vh || 900, deviceScaleFactor: 2 });
  await page.goto(BASE + (c.q || ""), { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForFunction(() => window.__tryon?.built || window.__tryon?.error, { timeout: 90000 }).catch(() => {});
  await page.click("#mode-live");
  // let the camera and the tracker come up, then pump frames ourselves in case rAF is throttled
  const t0 = Date.now();
  let info = null;
  while (Date.now() - t0 < (c.timeout || 120000)) {
    info = await page.evaluate(() => {
      for (let i = 0; i < 3; i++) window.__tryon.step?.();
      return { tracking: !!window.__tryon.debug || document.getElementById("guide").hidden === false,
               pose: window.__tryon.pose, debug: window.__tryon.debug, fit: window.__tryon.fit,
               guide: document.getElementById("guide").hidden ? "" : document.getElementById("guide-text").textContent,
               hint: document.getElementById("hint").hidden ? "" : document.getElementById("hint").textContent,
               ringOn: window.__tryon.debug?.main && typeof window.__tryon.debug.main === "object",
               camera: window.__tryon.camera, error: window.__tryon.error };
    });
    if (info.tracking && Date.now() - t0 > 6000) break;
    await sleep(500);
  }
  // a second of settling so the smoothed size lands
  for (let i = 0; i < 20; i++) { await page.evaluate(() => { for (let j = 0; j < 3; j++) window.__tryon.step?.(); }); await sleep(50); }
  info = await page.evaluate(() => ({
    pose: window.__tryon.pose, debug: window.__tryon.debug, fit: window.__tryon.fit, camera: window.__tryon.camera,
    guide: document.getElementById("guide").hidden ? "" : document.getElementById("guide-text").textContent.replace(/\n/g, " / "),
    hint: document.getElementById("hint").hidden ? "" : document.getElementById("hint").textContent, error: window.__tryon.error
  }));
  const stage = await page.$("#stage");
  const file = `${OUT}${c.name}.png`;
  await stage.screenshot({ path: file });
  console.log(`${c.name}: pose=${info.pose} cam=${info.camera} ring=${JSON.stringify(info.debug?.main)} fit=${JSON.stringify(info.fit)} guide="${info.guide}" hint="${info.hint}" err=${info.error || "-"} -> ${file}`);
  if (errors.length) console.log("  console:", [...new Set(errors)].slice(0, 6).join(" || "));
  await browser.close();
}
