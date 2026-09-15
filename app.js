import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RINGS, SILICONE, METAL, parseColor } from "./catalog.js";
import { createRing, INNER_RADIUS } from "./rings.js";

const MP = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1";
const MODEL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
// [MCP, PIP] landmark pairs and finger width relative to average knuckle spacing
const FINGERS = { index: [5, 6, 1.05], middle: [9, 10, 1.07], ring: [13, 14, 1.0], pinky: [17, 18, 0.86] };
const RING_POS = 0.47;    // position between knuckle and middle joint
const SMOOTH = 0.5;       // landmark smoothing for live video

const $ = (id) => document.getElementById(id);
const stage = $("stage"), canvas = $("gl"), video = $("video"), photo = $("photo");
const hint = $("hint"), loader = $("loader");
const params = new URLSearchParams(location.search);

const state = {
  ring: RINGS.find((r) => r.id === params.get("ring")) || RINGS[4],
  color: null, finger: params.get("finger") || "ring", mode: "3d", facing: "user",
  stream: null, landmarker: null, lmMode: null, hand: null, lastSeen: 0, lastVideoTime: -1,
  w: 0, h: 0
};
state.color = state.ring.colors.includes(params.get("color")) ? params.get("color") : state.ring.colors[0];
window.__tryon = { ready: false, placed: false, error: null, debug: null };

/* ---------- renderer & scenes ---------- */
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
const env = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;

// 3D product view
const viewScene = new THREE.Scene();
viewScene.environment = env;
const viewCam = new THREE.PerspectiveCamera(30, 1, 1, 1000);
viewCam.position.set(0, 22, 66);
const controls = new OrbitControls(viewCam, canvas);
Object.assign(controls, { enableDamping: true, autoRotate: true, autoRotateSpeed: 1.4, enablePan: false, minDistance: 34, maxDistance: 120 });
controls.target.set(0, 2, 0);
const key = new THREE.DirectionalLight("#ffffff", 1.3);
key.position.set(25, 45, 35);
const fill = new THREE.DirectionalLight("#fff6ee", 0.9);
fill.position.set(-10, -6, 50);
viewScene.add(key, fill);
const shadow = new THREE.Mesh(new THREE.CircleGeometry(17, 48),
  new THREE.MeshBasicMaterial({ map: radialTexture(), transparent: true, depthWrite: false }));
shadow.rotation.x = -Math.PI / 2;
shadow.position.y = -13.5;
viewScene.add(shadow);
const viewHolder = new THREE.Group();
viewScene.add(viewHolder);

// AR overlay: orthographic camera in stage pixels, y up, z towards the viewer
const arScene = new THREE.Scene();
arScene.environment = env;
arScene.environmentIntensity = 0.9;
const arCam = new THREE.OrthographicCamera(0, 1, 0, -1, -20000, 20000);
const arLight = new THREE.DirectionalLight("#ffffff", 1.0);
arLight.position.set(0.3, 1, 1);
arScene.add(arLight);
const arHolder = new THREE.Group();
arHolder.visible = false;
arScene.add(arHolder);

function radialTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, "rgba(70,58,50,.34)");
  gr.addColorStop(1, "rgba(70,58,50,0)");
  g.fillStyle = gr;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function dispose(group) {
  group.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) o.material.dispose();
  });
  group.clear();
}

/* ---------- ring build ---------- */
function rebuild() {
  dispose(viewHolder);
  dispose(arHolder);

  const view = createRing(state.ring, state.color).group;
  view.rotation.x = -Math.PI / 2;           // stone up, hole towards the camera
  view.rotation.z = 0.5;
  viewHolder.add(view);

  const { group, length } = createRing(state.ring, state.color);
  state.arLength = length;
  const occluder = new THREE.Mesh(
    new THREE.CylinderGeometry(INNER_RADIUS * 0.98, INNER_RADIUS * 0.98, length + 60, 40),
    new THREE.MeshBasicMaterial({ colorWrite: false })
  );
  occluder.renderOrder = -1;
  arHolder.add(occluder, group);
  renderPanel();
}

/* ---------- panel UI ---------- */
function swatchColors(name) {
  const { band, metal } = parseColor(name);
  return { band: SILICONE[band] || "#ccc", metal: metal ? METAL[metal] : null };
}

function renderPanel() {
  const r = state.ring;
  $("p-family").textContent = r.family;
  $("p-name").textContent = r.name;
  $("p-price").textContent = `$${r.price.toFixed(2)}`;
  $("p-link").href = r.url;
  $("p-color").textContent = state.color;

  const sw = $("swatches");
  sw.replaceChildren(...r.colors.map((c) => {
    const b = document.createElement("button");
    const { band, metal } = swatchColors(c);
    b.className = "swatch" + (metal ? " dual" : "");
    b.style.setProperty("--c", band);
    if (metal) b.style.setProperty("--m", metal);
    b.setAttribute("aria-label", c);
    b.title = c;
    b.setAttribute("aria-pressed", String(c === state.color));
    b.onclick = () => { state.color = c; rebuild(); };
    return b;
  }));

  for (const card of $("grid").children) card.setAttribute("aria-pressed", String(card.dataset.id === r.id));
}

function buildGrid() {
  $("grid").replaceChildren(...RINGS.map((r) => {
    const b = document.createElement("button");
    b.className = "card";
    b.dataset.id = r.id;
    b.innerHTML = `<img alt="" loading="lazy"><b></b><span></span>`;
    b.querySelector("img").src = r.img;
    b.querySelector("b").textContent = r.name;
    b.querySelector("span").textContent = `$${r.price.toFixed(2)}`;
    b.onclick = () => { state.ring = r; state.color = r.colors[0]; rebuild(); };
    return b;
  }));
}

function setHint(text) {
  hint.hidden = !text;
  if (text) hint.textContent = text;
}

for (const b of $("fingers").children) {
  b.onclick = () => {
    state.finger = b.dataset.f;
    for (const x of $("fingers").children) x.setAttribute("aria-pressed", String(x === b));
    if (state.mode === "3d") setMode("live");
  };
  b.setAttribute("aria-pressed", String(b.dataset.f === state.finger));
}

/* ---------- hand tracking ---------- */
async function getLandmarker(runningMode) {
  if (!state.landmarker) {
    loader.hidden = false;
    try {
      const { FilesetResolver, HandLandmarker } = await import(`${MP}/vision_bundle.mjs`);
      const files = await FilesetResolver.forVisionTasks(`${MP}/wasm`);
      const opts = (delegate) => ({
        baseOptions: { modelAssetPath: MODEL, delegate }, runningMode, numHands: 2,
        minHandDetectionConfidence: 0.5, minHandPresenceConfidence: 0.5, minTrackingConfidence: 0.5
      });
      const preferCpu = params.get("cpu") === "1";
      try {
        state.landmarker = await HandLandmarker.createFromOptions(files, opts(preferCpu ? "CPU" : "GPU"));
      } catch {
        state.landmarker = await HandLandmarker.createFromOptions(files, opts("CPU"));
      }
      state.lmMode = runningMode;
    } catch (e) {
      window.__tryon.error = String(e);
      setHint("Hand tracking could not load");
      throw e;
    } finally {
      loader.hidden = true;
    }
  }
  if (state.lmMode !== runningMode) {
    await state.landmarker.setOptions({ runningMode });
    state.lmMode = runningMode;
  }
  return state.landmarker;
}

// Pick the biggest detected hand
function pickHand(result) {
  if (!result.landmarks?.length) return null;
  let best = 0, bestArea = -1;
  result.landmarks.forEach((l, i) => {
    const xs = l.map((p) => p.x), ys = l.map((p) => p.y);
    const area = (Math.max(...xs) - Math.min(...xs)) * (Math.max(...ys) - Math.min(...ys));
    if (area > bestArea) { bestArea = area; best = i; }
  });
  return { lms: result.landmarks[best], handed: result.handedness[best][0].categoryName };
}

function onResult(result, live) {
  const hand = pickHand(result);
  if (!hand) return false;
  if (live && state.hand && state.hand.handed === hand.handed && performance.now() - state.lastSeen < 300) {
    state.hand.lms = state.hand.lms.map((p, i) => {
      const q = hand.lms[i];
      return { x: p.x + (q.x - p.x) * SMOOTH, y: p.y + (q.y - p.y) * SMOOTH, z: p.z + (q.z - p.z) * SMOOTH };
    });
  } else {
    state.hand = { lms: hand.lms.map((p) => ({ x: p.x, y: p.y, z: p.z })), handed: hand.handed };
  }
  state.lastSeen = performance.now();
  return true;
}

// Map a normalized landmark to stage pixels. Live video fills the stage (cover),
// photos are shown whole (contain) so no hand gets cropped away.
const fitMode = () => (state.mode === "photo" ? "contain" : "cover");
function mapper(srcW, srcH) {
  const sc = fitMode() === "contain" ? Math.min(state.w / srcW, state.h / srcH) : Math.max(state.w / srcW, state.h / srcH);
  const ox = (state.w - srcW * sc) / 2, oy = (state.h - srcH * sc) / 2;
  return (p) => new THREE.Vector3(ox + p.x * srcW * sc, -(oy + p.y * srcH * sc), -p.z * srcW * sc);
}

function placeRing(srcW, srcH) {
  const hand = state.hand;
  if (!hand || !srcW) { arHolder.visible = false; return; }
  const P = mapper(srcW, srcH);
  const L = hand.lms;
  const [ia, ib, widthK] = FINGERS[state.finger];
  const A = P(L[ia]), B = P(L[ib]);
  const P0 = P(L[0]), P5 = P(L[5]), P9 = P(L[9]), P13 = P(L[13]), P17 = P(L[17]);

  const axis = new THREE.Vector3().subVectors(B, A).normalize();
  // Each measure shrinks when the hand turns away from the camera, so take the largest.
  const spacing = (P5.distanceTo(P9) + P9.distanceTo(P13) + P13.distanceTo(P17)) / 3;
  const fingerWidth = Math.max(spacing * 0.86, P0.distanceTo(P9) * 0.185, A.distanceTo(B) * 0.42) * widthK;
  const scale = fingerWidth / (INNER_RADIUS * 2);

  // Normal of the back of the hand. Checked on test photos: for a hand labelled "Right"
  // the raw cross product points into the palm, so it is flipped.
  const n = new THREE.Vector3().subVectors(P5, P0).cross(new THREE.Vector3().subVectors(P17, P0)).normalize();
  if (hand.handed === "Right") n.negate();
  const zAxis = n.sub(axis.clone().multiplyScalar(n.dot(axis))).normalize();
  const xAxis = new THREE.Vector3().crossVectors(axis, zAxis).normalize();

  arHolder.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xAxis, axis, zAxis));
  // Long stacks move further up the finger so they do not sink into the knuckle.
  const seg = Math.max(A.distanceTo(B), 1);
  const t = Math.min(0.65, Math.max(RING_POS, 0.3 + (state.arLength / 2) * scale / seg));
  arHolder.position.copy(A.lerp(B, t));
  arHolder.scale.setScalar(scale);
  arHolder.visible = true;
  window.__tryon.placed = true;
  window.__tryon.debug = { handed: hand.handed, scale: +scale.toFixed(3), facing: +zAxis.z.toFixed(2) };
}

/* ---------- sources ---------- */
function stopCamera() {
  state.stream?.getTracks().forEach((t) => t.stop());
  state.stream = null;
  video.srcObject = null;
}

async function startCamera() {
  stopCamera();
  if (!navigator.mediaDevices?.getUserMedia) { setHint("This browser has no camera access — use Photo"); return; }
  setHint("Allow camera access");
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: state.facing, width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false
    });
  } catch {
    setHint("Camera blocked — try the Photo mode");
    return;
  }
  video.srcObject = state.stream;
  await video.play().catch(() => {});
  stage.classList.toggle("mirror", state.facing === "user");
  setHint("Show the back of your hand");
  await getLandmarker("VIDEO").catch(() => {});
}

async function loadPhoto(src) {
  photo.hidden = false;
  arHolder.visible = false;
  state.hand = null;
  setHint("Finding your hand…");
  photo.src = src;
  try { await photo.decode(); } catch { setHint("This image could not be opened"); return; }
  const lm = await getLandmarker("IMAGE").catch(() => null);
  if (!lm) return;
  const found = onResult(lm.detect(photo), false);
  setHint(found ? "" : "No hand found — try a photo with the back of the hand");
}

$("file").onchange = (e) => {
  const f = e.target.files?.[0];
  if (f) loadPhoto(URL.createObjectURL(f));
};

async function setMode(mode) {
  state.mode = mode;
  for (const m of ["3d", "live", "photo"]) $(`mode-${m}`).setAttribute("aria-pressed", String(m === mode));
  const ar = mode !== "3d";
  canvas.classList.toggle("ar", ar);
  stage.classList.remove("mirror");
  video.hidden = mode !== "live";
  $("flip").hidden = mode !== "live";
  $("shot").hidden = !ar;
  if (mode !== "live") stopCamera();
  if (mode !== "photo") photo.hidden = true;
  arHolder.visible = false;
  state.hand = null;

  if (mode === "3d") setHint("Drag to rotate · pinch to zoom");
  if (mode === "live") startCamera();
  if (mode === "photo") {
    if (params.get("photo") && !photo.dataset.used) { photo.dataset.used = "1"; loadPhoto(params.get("photo")); }
    else { setHint("Upload a photo of your hand"); photo.hidden = !photo.src; $("file").click(); if (photo.src) loadPhoto(photo.src); }
  }
}
$("mode-3d").onclick = () => setMode("3d");
$("mode-live").onclick = () => setMode("live");
$("mode-photo").onclick = () => setMode("photo");
$("flip").onclick = () => { state.facing = state.facing === "user" ? "environment" : "user"; startCamera(); };

$("shot").onclick = () => {
  const out = document.createElement("canvas");
  out.width = canvas.width; out.height = canvas.height;
  const g = out.getContext("2d");
  const src = state.mode === "live" ? video : photo;
  const sw = src.videoWidth || src.naturalWidth, sh = src.videoHeight || src.naturalHeight;
  if (sw) {
    g.fillStyle = "#e9e4e1";
    g.fillRect(0, 0, out.width, out.height);
    const sc = fitMode() === "contain" ? Math.min(out.width / sw, out.height / sh) : Math.max(out.width / sw, out.height / sh);
    g.save();
    if (stage.classList.contains("mirror")) { g.translate(out.width, 0); g.scale(-1, 1); }
    g.drawImage(src, (out.width - sw * sc) / 2, (out.height - sh * sc) / 2, sw * sc, sh * sc);
    g.drawImage(canvas, 0, 0);
    g.restore();
  }
  const a = document.createElement("a");
  a.download = `rinfit-${state.ring.id}.png`;
  a.href = out.toDataURL("image/png");
  a.click();
};

/* ---------- loop ---------- */
function resize() {
  const w = stage.clientWidth, h = stage.clientHeight;
  if (w === state.w && h === state.h) return;
  state.w = w; state.h = h;
  renderer.setSize(w, h, false);
  viewCam.aspect = w / h;
  viewCam.updateProjectionMatrix();
  Object.assign(arCam, { left: 0, right: w, top: 0, bottom: -h });
  arCam.updateProjectionMatrix();
}

function frame() {
  requestAnimationFrame(frame);
  resize();
  if (state.mode === "3d") {
    controls.update();
    renderer.render(viewScene, viewCam);
  } else {
    if (state.mode === "live" && state.landmarker && state.lmMode === "VIDEO" && video.readyState >= 2
        && video.currentTime !== state.lastVideoTime) {
      state.lastVideoTime = video.currentTime;
      const seen = onResult(state.landmarker.detectForVideo(video, performance.now()), true);
      if (seen) setHint("");
      else if (performance.now() - state.lastSeen > 400) { state.hand = null; setHint("Show the back of your hand"); }
    }
    const srcW = state.mode === "live" ? video.videoWidth : photo.naturalWidth;
    const srcH = state.mode === "live" ? video.videoHeight : photo.naturalHeight;
    placeRing(srcW, srcH);
    renderer.render(arScene, arCam);
  }
  window.__tryon.ready = true;
}

buildGrid();
rebuild();
setHint("Drag to rotate · pinch to zoom");
frame();
if (params.get("photo")) setMode("photo");
