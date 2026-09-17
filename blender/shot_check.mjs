// Press the shutter the way a shopper does and keep what comes out: the branded photo, plus a check that
// the heart really saves the ring.
//   node blender/shot_check.mjs "?ring=emerald&photo=blender/test/right_hands.jpg&cpu=1&finger=ring"
import puppeteer from "/Users/annserputko/Desktop/штаб/_Технічне/scraper/движок/node_modules/puppeteer/lib/esm/puppeteer/puppeteer.js";
import fs from "fs";
import { fileURLToPath } from "url";

const BASE = "http://127.0.0.1:8766/index.html";
const query = process.argv[2] || "?ring=emerald&photo=blender/test/right_hands.jpg&cpu=1&finger=ring";
const OUT = fileURLToPath(new URL("./out/site/", import.meta.url));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  headless: "new", protocolTimeout: 240000,
  args: ["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding"]
});
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("PAGEERROR " + String(e).slice(0, 300)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 200)); });
await page.setViewport({ width: 1280, height: 1000 });
await page.goto(BASE + query, { waitUntil: "domcontentloaded", timeout: 60000 });

const t0 = Date.now();
while (Date.now() - t0 < 180000) {
  const ok = await page.evaluate(() => { window.__tryon.step?.(); return window.__tryon.placed; }).catch(() => false);
  if (ok) break;
  await sleep(300);
}

const out = await page.evaluate(() => {
  for (let i = 0; i < 20; i++) window.__tryon.step();
  document.getElementById("shot").click();
  const card = document.getElementById("shot-card");
  const like = document.getElementById("p-like");
  const before = like.getAttribute("aria-pressed");
  like.click();
  const after = like.getAttribute("aria-pressed");
  let saved = null;
  try { saved = localStorage.getItem("rinfit-favs"); } catch { /* private mode */ }
  return {
    cardShown: !card.hidden,
    img: document.getElementById("shot-img").src,
    likeBefore: before, likeAfter: after, saved,
    favRow: !document.getElementById("fav-wrap").hidden,
    shotLike: document.getElementById("shot-like").getAttribute("aria-pressed")
  };
});

if (out.img?.startsWith("data:image/png")) {
  fs.writeFileSync(`${OUT}shot_card.png`, Buffer.from(out.img.split(",")[1], "base64"));
}
console.log(`card shown: ${out.cardShown}   photo written: ${!!out.img}`);
console.log(`like: ${out.likeBefore} -> ${out.likeAfter}   saved row: ${out.favRow}   heart on card: ${out.shotLike}   localStorage: ${out.saved}`);
if (errors.length) console.log("errors:", [...new Set(errors)].slice(0, 5).join(" || "));
await browser.close();
