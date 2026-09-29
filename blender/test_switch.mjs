// Live try-on, then switch rings the way a shopper does: the size of every ring after a switch must match
// the size it gets when it is the first ring loaded. (Bug 29.09: the new ring's width was read with the old
// ring's pose still on the holder, so every ring after the first came out a fraction of its size.)
//   node blender/test_switch.mjs '{"cam":"blender/test/anna/a1.y4m","first":"emerald","then":["princess","pear","frosted","solitaire","couture"]}'
import puppeteer from "/Users/annserputko/Desktop/штаб/_Технічне/scraper/движок/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js";
import path from "path";
import { fileURLToPath } from "url";
const ROOT = fileURLToPath(new URL("../", import.meta.url));
const OUT = fileURLToPath(new URL("./out/live/", import.meta.url));
const c = JSON.parse(process.argv[2]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ headless: "new", protocolTimeout: 240000,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
         `--use-file-for-fake-video-capture=${path.resolve(ROOT, c.cam)}`, "--disable-background-timer-throttling",
         "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows"] });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
await page.goto(`http://127.0.0.1:8766/index.html?ring=${c.first}&cpu=1`, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => window.__tryon?.built, { timeout: 90000 });
await page.click("#mode-live");
await page.evaluate(() => setInterval(() => window.__tryon.step(), 16));
const read = async (id) => {
  await page.waitForFunction(() => window.__tryon.ring && window.__tryon.debug?.main?.scale, { timeout: 120000, polling: 200 });
  await sleep(2500);                                    // let the size settle
  const r = await page.evaluate(() => ({ scale: window.__tryon.debug.main.scale, width: window.__tryon.ring.width }));
  const box = await page.$("#stage");
  await box.screenshot({ path: `${OUT}switch_${id}.png` });
  return r;
};
const rows = [[c.first, await read(c.first)]];
for (const id of c.then) {
  await page.evaluate((id) => {
    const card = [...document.querySelectorAll("#grid button, .grid button, [data-id]")].find((b) => b.dataset.id === id);
    if (card) card.click(); else window.__tryon.pick?.(id);
  }, id);
  await page.evaluate(() => { window.__tryon.ring = null; });
  rows.push([id, await read(id)]);
}
await browser.close();
for (const [id, r] of rows) console.log(`${id.padEnd(10)} scale=${r.scale} fingerWidth=${r.width.toFixed(1)}`);
