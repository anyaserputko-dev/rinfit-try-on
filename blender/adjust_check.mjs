// Can a shopper put the ring on by hand? Drags it with the mouse and checks it moved, then opens photo mode
// with no picture and checks the "take a photo of your hand" card appears.
//   node blender/adjust_check.mjs
import puppeteer from "/Users/annserputko/Desktop/штаб/_Технічне/scraper/движок/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js";

const BASE = "http://127.0.0.1:8766/index.html";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({
  headless: "new", protocolTimeout: 120000,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding"]
});

// 1. drag and pinch on a photo
const page = await browser.newPage();
await page.setViewport({ width: 900, height: 1180 });
await page.goto(`${BASE}?ring=emerald&photo=blender/test/right_hands.jpg&cpu=1&finger=ring&gem=simple`,
                { waitUntil: "domcontentloaded", timeout: 60000 });
const t0 = Date.now();
while (Date.now() - t0 < 120000) {
  const ok = await page.evaluate(() => { window.__tryon.step?.(); return window.__tryon.placed; }).catch(() => false);
  if (ok) break;
  await sleep(300);
}
const before = await page.evaluate(() => { for (let i = 0; i < 10; i++) window.__tryon.step(); return window.__tryon.fit; });

const box = await page.evaluate(() => {
  const r = document.getElementById("stage").getBoundingClientRect();
  return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
});
await page.mouse.move(box.x, box.y);
await page.mouse.down();
for (let i = 1; i <= 8; i++) await page.mouse.move(box.x + i * 5, box.y - i * 3);
await page.mouse.up();
const after = await page.evaluate(() => { for (let i = 0; i < 10; i++) window.__tryon.step(); return window.__tryon.fit; });

console.log(`offset before drag: [${before.offset}]   after dragging +40,-24 px: [${after.offset}]`);
console.log(`size knob: ${before.knob} -> ${after.knob}`);

// 2. photo mode with nothing chosen yet
const page2 = await browser.newPage();
await page2.setViewport({ width: 900, height: 1180 });
await page2.goto(`${BASE}?ring=emerald&gem=simple`, { waitUntil: "domcontentloaded", timeout: 60000 });
await sleep(1500);
const intro = await page2.evaluate(() => {
  document.getElementById("mode-photo").click();
  const card = document.getElementById("photo-intro");
  return {
    shown: !card.hidden,
    title: card.querySelector("b")?.textContent,
    buttons: [...card.querySelectorAll("button")].map((b) => b.textContent.trim())
  };
});
console.log(`photo intro shown: ${intro.shown}  "${intro.title}"  buttons: ${intro.buttons.join(" / ")}`);

// "Take a photo" must open the camera in the page, not a file dialog. Headless has no camera, so the right
// behaviour here is the graceful refusal: back to the card with an explanation, and no crash.
const errs = [];
page2.on("pageerror", (e) => errs.push(String(e).slice(0, 200)));
const camera = await page2.evaluate(async () => {
  const opened = [];
  const input = document.getElementById("file");
  input.addEventListener("click", () => opened.push("file dialog"));
  await document.getElementById("intro-camera").onclick();
  return {
    openedFileDialog: opened.length > 0,
    capturing: window.__tryon ? undefined : undefined,
    introBack: !document.getElementById("photo-intro").hidden,
    hint: document.getElementById("hint").textContent,
    videoShown: !document.getElementById("video").hidden
  };
});
console.log(`take-a-photo: file dialog opened? ${camera.openedFileDialog}  ` +
            `fallback card: ${camera.introBack}  hint: "${camera.hint}"  video: ${camera.videoShown}`);
if (errs.length) console.log("page errors:", errs.join(" || "));
await browser.close();
