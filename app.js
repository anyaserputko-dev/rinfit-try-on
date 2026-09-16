import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RINGS, METAL, parseColor, bandHex } from "./catalog.js";
import { createRing, setGemEnvironment, INNER_RADIUS, siliconeMat, frostedMat, metalMat, gemMeshes } from "./rings.js";
import { stoneMaterial } from "./gem.js";

const MP = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1";
const MODEL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
// [MCP, PIP] landmark pairs and finger width relative to the hand measure
const FINGERS = { index: [5, 6, 1.05], middle: [9, 10, 1.07], ring: [13, 14, 1.0], pinky: [17, 18, 0.86] };
// where the second ring of a set goes
const NEIGHBOR = { index: "middle", middle: "ring", ring: "middle", pinky: "ring" };
const RING_POS = +(new URLSearchParams(location.search).get("fitpos") ?? 0.42);   // between knuckle and middle joint
const SMOOTH = 0.5;       // landmark smoothing for live video

const $ = (id) => document.getElementById(id);
const stage = $("stage"), canvas = $("gl"), video = $("video"), photo = $("photo");
const hint = $("hint"), loader = $("loader");
const params = new URLSearchParams(location.search);

const state = {
  ring: RINGS.find((r) => r.id === params.get("ring")) || RINGS[4],
  color: null, finger: params.get("finger") || "ring", mode: "3d", facing: "user",
  stream: null, landmarker: null, lmMode: null, hand: null, lastSeen: 0, lastVideoTime: -1, lastDetect: 0,
  w: 0, h: 0, hasSecond: false, viewCount: 0, buildToken: 0
};
state.color = state.ring.colors.includes(params.get("color")) ? params.get("color") : state.ring.colors[0];
// Hand tracking only estimates how wide a finger is; on a hand held close or at an angle it can be off,
// so the shopper can nudge the ring's size and the page remembers it.
let stored = null;
try { stored = localStorage.getItem("rinfit-fit"); } catch { /* private mode */ }
state.fit = clampFit(+(params.get("fitscale") ?? stored ?? 1));
window.__tryon = { ready: false, built: false, placed: false, error: null, debug: null };

/* ---------- renderer & scenes ---------- */
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 3));   // phones are 3x: at 2x the ring looks soft next to the video
renderer.toneMapping = THREE.NeutralToneMapping;   // keeps pastel silicone colors true to the product photos
renderer.toneMappingExposure = 1.0;
// Jewellery studio: grey room with bright softboxes, so metal reads as polished and facets flash white.
function studioEnvironment() {
  const scene = new THREE.Scene();
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(40, 30, 40), new THREE.MeshBasicMaterial({ color: "#8c8c90", side: THREE.BackSide })));
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshBasicMaterial({ color: "#b9b6b2" }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -14;
  scene.add(floor);
  const panel = (w, h, x, y, z, s) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(s, s, s), side: THREE.DoubleSide }));
    m.position.set(x, y, z);
    m.lookAt(0, 0, 0);
    scene.add(m);
  };
  panel(18, 6, 0, 14, 0, 6);
  panel(8, 16, 18, 2, 6, 4);
  panel(8, 16, -18, 2, 6, 3);
  panel(12, 6, 0, 4, 19, 3);
  panel(4, 10, 10, 6, -18, 5);
  panel(4, 10, -10, 6, -18, 5);
  return new THREE.PMREMGenerator(renderer).fromScene(scene, 0.02).texture;
}
const env = studioEnvironment();

// Light tent for stones: bright surroundings with thin dark cards and a few hot spots,
// which gives the mostly-white CZ look with dark facet accents seen in the product photos.
function gemEnvironment() {
  const scene = new THREE.Scene();
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(40, 40, 40), new THREE.MeshBasicMaterial({ color: new THREE.Color(1.1, 1.1, 1.12), side: THREE.BackSide })));
  const card = (w, h, x, y, z, color) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
    m.position.set(x, y, z);
    m.lookAt(0, 0, 0);
    scene.add(m);
  };
  const dark = new THREE.Color(0.02, 0.02, 0.025), hot = new THREE.Color(9, 9, 9);
  for (let i = 0; i < 18; i++) { const a = (i / 18) * Math.PI * 2; card(0.9, 14, Math.cos(a) * 17, 0, Math.sin(a) * 17, dark); }
  for (let i = 0; i < 10; i++) { const a = (i / 10) * Math.PI * 2 + 0.2; card(4, 0.7, Math.cos(a) * 12, 13, Math.sin(a) * 12, dark); }
  for (let i = 0; i < 8; i++) { const a = (i / 8) * Math.PI * 2 + 0.4; card(2.2, 2.2, Math.cos(a) * 15, 8 - (i % 3) * 7, Math.sin(a) * 15, hot); }
  card(8, 8, 0, 17, 0, hot);
  card(14, 14, 0, -17, 0, new THREE.Color(0.35, 0.35, 0.36));
  return new THREE.PMREMGenerator(renderer).fromScene(scene, 0).texture;
}
setGemEnvironment(gemEnvironment());

// 3D product view
const viewScene = new THREE.Scene();
viewScene.environment = env;
const viewCam = new THREE.PerspectiveCamera(30, 1, 1, 1000);
const controls = new OrbitControls(viewCam, canvas);
Object.assign(controls, { enableDamping: true, autoRotate: params.get("spin") !== "0", autoRotateSpeed: 1.4, enablePan: false, minDistance: 30, maxDistance: 140 });
const key = new THREE.DirectionalLight("#ffffff", 0.8);
key.position.set(25, 45, 35);
const fill = new THREE.DirectionalLight("#fff6ee", 0.35);
fill.position.set(-10, -6, 50);
viewScene.add(key, fill, new THREE.HemisphereLight("#ffffff", "#d8d0c8", 0.35));
const shadow = new THREE.Mesh(new THREE.CircleGeometry(19, 48),
  new THREE.MeshBasicMaterial({ map: radialTexture(), transparent: true, depthWrite: false }));
shadow.rotation.x = -Math.PI / 2;
shadow.position.y = -14.5;
viewScene.add(shadow);
const viewHolder = new THREE.Group();
viewScene.add(viewHolder);

// AR overlay: orthographic camera in stage pixels, y up, z towards the viewer
const arScene = new THREE.Scene();
arScene.environment = env;
const arCam = new THREE.OrthographicCamera(0, 1, 0, -1, -20000, 20000);
const arLight = new THREE.DirectionalLight("#ffffff", 0.7);
arLight.position.set(0.3, 1, 1);
arScene.add(arLight, new THREE.HemisphereLight("#ffffff", "#d8d0c8", 0.4));
const arMain = new THREE.Group(), arSecond = new THREE.Group();
arMain.visible = arSecond.visible = false;
arScene.add(arMain, arSecond);

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
    if (o.userData.shared) return;
    if (o.userData.ownsGeometry !== false) o.geometry?.dispose();   // GLB geometry stays in the model cache
    const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
    for (const m of mats) { m.map?.dispose(); m.dispose(); }
  });
  group.clear();
}

/* ---------- ring build ---------- */
// Models built in Blender (blender/rings/*.py) replace the procedural ring when ring.model is set.
// Material names in the GLB say what each part is: Silicone_A / Silicone_B (band colours of the variant),
// Metal (Silver or Rose Gold), CZ / CZ_Black (swapped for the realtime gem shader).
const gltf = new GLTFLoader();
const modelCache = new Map();

function dressModel(ring, scene, band, second, metal) {
  const root = scene.clone(true);
  const swaps = [];
  root.traverse((o) => {
    if (!o.isMesh) return;
    const name = o.material?.name || "";
    o.userData.shared = true;   // geometry belongs to the cached GLB
    if (name.startsWith("Silicone")) {
      const colorName = name.startsWith("Silicone_B") ? second : band;
      o.material = ring.spec.frosted ? frostedMat() : siliconeMat(bandHex(ring, colorName), ring.spec.finish || "satin");
      o.userData.shared = false;
      o.userData.ownsGeometry = false;
    } else if (name.startsWith("Metal")) {
      o.material = metalMat(metal);
      o.material.roughness = 0.28;   // same soft polish as the Blender renders
      o.userData.shared = false;
      o.userData.ownsGeometry = false;
    } else if (name.startsWith("CZ")) {
      swaps.push([o, name.startsWith("CZ_Black"), /pave/i.test(o.name)]);
    }
  });
  for (const [o, black, small] of swaps) {
    if (!small) {   // main stone: one convex solid, ray-traced against its own facets
      o.material = stoneMaterial(o.geometry, { black });
      o.userData.shared = false;
      o.userData.ownsGeometry = false;
      continue;
    }
    for (const g of gemMeshes(o.geometry, black, small)) {
      g.position.copy(o.position);
      g.quaternion.copy(o.quaternion);
      g.scale.copy(o.scale);
      g.userData.ownsGeometry = false;
      o.parent.add(g);
    }
    o.removeFromParent();
  }
  root.scale.setScalar(ring.model.scale ?? 1);
  const group = new THREE.Group();
  group.add(root);
  return group;
}

async function buildPiece(ring, color) {
  if (!ring.model) return createRing(ring, color);
  if (!modelCache.has(ring.model.url)) modelCache.set(ring.model.url, gltf.loadAsync(ring.model.url).then((g) => g.scene));
  const scene = await modelCache.get(ring.model.url);
  const { bands, metals } = parseColor(color);
  const bandLength = ring.model.bandLength ?? 6;
  if (ring.spec.pair === "separate") {   // set of two separate rings: same model, second colour on the neighbouring finger
    return {
      group: dressModel(ring, scene, bands[0], bands[0], metals[0]), bandLength,
      second: { group: dressModel(ring, scene, bands[1] ?? bands[0], bands[1] ?? bands[0], metals[1] ?? metals[0]), bandLength }
    };
  }
  return { group: dressModel(ring, scene, bands[0], bands[1] ?? bands[0], metals[0]), bandLength };
}

// How much of the band the finger swallows. At 0.98 the ring is a hoop drawn over the skin and its sides
// stick out past the finger like a bar; a finger is not a cylinder, so a slightly fatter occluder tucks the
// sides away and the band reads as passing behind the finger.
// 1.12 from a sweep against real hands: at 0.98 the band's ends curl out past the finger like horns,
// at 1.12 they stop at the silhouette, at 1.18 the band is already eaten into.
const OCC = +(new URLSearchParams(location.search).get("occ") ?? 1.12);

function addToAr(holder, piece) {
  const occluder = new THREE.Mesh(
    new THREE.CylinderGeometry(INNER_RADIUS * OCC, INNER_RADIUS * OCC, piece.bandLength + 60, 40),
    new THREE.MeshBasicMaterial({ colorWrite: false })
  );
  occluder.renderOrder = -1;
  holder.add(occluder, piece.group);
  holder.userData.bandLength = piece.bandLength;
}

// Product-photo angles: which way the stone (local Z) and the finger axis (local Y) point.
const VIEWS = {
  front: { z: [0, 0.45, 0.89], y: [0, 1, -0.45] },          // stone at the camera, band as a hoop seen from slightly above
  threeq: { z: [-0.25, 0.5, 0.83], y: [0.35, 0.8, -0.5] },  // three-quarter view, like the Emerald and Halo photos
  top: { z: [0, 0.12, 1], y: [0, 1, -0.12] },               // stone straight at the camera, bands as horizontal strips
  band: { z: [-0.35, 0.05, 0.94], y: [0.85, 0.2, -0.45] },  // band on its edge, logo side to the camera
  couture: { z: [-0.3, 0.88, 0.37], y: [0.8, 0.1, -0.6] }   // V peak up, ring opening to the right
};
function orient(obj, type) {
  const v = VIEWS[type] || VIEWS.front;
  const z = new THREE.Vector3(...v.z).normalize();
  const x = new THREE.Vector3().crossVectors(new THREE.Vector3(...v.y), z).normalize();
  const y = new THREE.Vector3().crossVectors(z, x).normalize();
  obj.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z));
}

function setViewCamera(count) {
  // fit whatever is on the stage: a set of two rings is much wider than a single ring
  const box = new THREE.Box3().setFromObject(viewHolder);
  const radius = box.isEmpty() ? 20 : box.getSize(new THREE.Vector3()).length() / 2;
  const centre = box.isEmpty() ? new THREE.Vector3(0, 2, 0) : box.getCenter(new THREE.Vector3());
  const fov = THREE.MathUtils.degToRad(viewCam.fov);
  const dist = Math.max(40, (radius / Math.tan(fov / 2)) * (count > 1 ? 1.25 : 1.35));
  const az = THREE.MathUtils.degToRad(+(params.get("az") ?? 0));
  const el = THREE.MathUtils.degToRad(+(params.get("el") ?? 17));
  controls.target.copy(centre);
  viewCam.position.set(centre.x + Math.sin(az) * Math.cos(el) * dist, centre.y + Math.sin(el) * dist,
                       centre.z + Math.cos(az) * Math.cos(el) * dist);
  controls.update();
}

async function rebuild() {
  const token = ++state.buildToken;
  const [view, ar] = await Promise.all([buildPiece(state.ring, state.color), buildPiece(state.ring, state.color)]);
  if (token !== state.buildToken) return;
  dispose(viewHolder);
  dispose(arMain);
  dispose(arSecond);

  const pieces = [view, view.second].filter(Boolean);
  pieces.forEach((p, i) => {
    const pivot = new THREE.Group();
    orient(p.group, state.ring.view);
    if (pieces.length > 1) {   // two rings of a set side by side, like the product photo
      const half = new THREE.Box3().setFromObject(p.group).getSize(new THREE.Vector3()).x / 2 + 1.5;
      pivot.position.set(i ? half : -half, 0, i ? 3 : -3);
      pivot.rotation.y = i ? -0.22 : 0.22;
    }
    pivot.add(p.group);
    viewHolder.add(pivot);
  });
  if (pieces.length !== state.viewCount) { state.viewCount = pieces.length; setViewCamera(pieces.length); }

  addToAr(arMain, ar);
  state.hasSecond = !!ar.second;
  if (ar.second) addToAr(arSecond, ar.second);
  window.__tryon.built = true;
  renderPanel();
}

/* ---------- panel UI ---------- */
function swatchColors(ring, name) {
  const { bands, metals } = parseColor(name);
  const a = bandHex(ring, bands[0]);
  if (bands.length > 1) return { a, b: bandHex(ring, bands[1]) };
  if (name !== bands[0]) return { a, b: METAL[metals[0]] };
  return { a, b: null };
}

function renderPanel() {
  const r = state.ring;
  $("p-family").textContent = r.family;
  $("p-name").textContent = r.name;
  $("p-price").textContent = `$${r.price.toFixed(2)}`;
  $("p-link").href = r.url;
  $("p-color").textContent = state.color;
  const note = $("p-set");
  note.hidden = r.spec.pair !== "separate";
  note.textContent = "Set of 2 rings. In try-on the second ring goes on the neighbouring finger.";

  $("swatches").replaceChildren(...r.colors.map((c) => {
    const b = document.createElement("button");
    const { a, b: second } = swatchColors(r, c);
    b.className = "swatch" + (second ? " dual" : "");
    b.style.setProperty("--c", a);
    if (second) b.style.setProperty("--m", second);
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

function clampFit(v) {
  return Math.min(1.4, Math.max(0.7, isFinite(v) && v > 0 ? v : 1));
}

function setFit(value) {
  state.fit = clampFit(value);
  $("fit-value").textContent = `${Math.round(state.fit * 100)}%`;
  try { localStorage.setItem("rinfit-fit", String(state.fit)); } catch { /* private mode */ }
}
$("fit-down").onclick = () => setFit(state.fit - 0.06);
$("fit-up").onclick = () => setFit(state.fit + 0.06);
setFit(state.fit);

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
      try {
        state.landmarker = await HandLandmarker.createFromOptions(files, opts(params.get("cpu") === "1" ? "CPU" : "GPU"));
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

function placeOn(holder, finger, pts, spacing, palm) {
  const [ia, ib, widthK] = FINGERS[finger];
  const A = pts[ia].clone(), B = pts[ib].clone();
  const axis = new THREE.Vector3().subVectors(B, A).normalize();
  // Each measure shrinks when the hand turns away from the camera, so take the largest.
  const fingerWidth = Math.max(spacing * 0.86, pts[0].distanceTo(pts[9]) * 0.185, A.distanceTo(B) * 0.42) * widthK * state.fit;
  const scale = fingerWidth / (INNER_RADIUS * 2);
  const zAxis = palm.clone().sub(axis.clone().multiplyScalar(palm.dot(axis))).normalize();
  const xAxis = new THREE.Vector3().crossVectors(axis, zAxis).normalize();
  holder.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xAxis, axis, zAxis));
  window.__tryon.fit = {   // for the fit calibration script
    finger, widthK, fingerWidth: +fingerWidth.toFixed(1),
    bySpacing: +(spacing * 0.86 * widthK).toFixed(1),
    byPalm: +(pts[0].distanceTo(pts[9]) * 0.185 * widthK).toFixed(1),
    bySegment: +(A.distanceTo(B) * 0.42 * widthK).toFixed(1)
  };
  // Long stacks move further up the finger so they do not sink into the knuckle.
  const seg = Math.max(A.distanceTo(B), 1);
  const t = Math.min(0.65, Math.max(RING_POS, 0.3 + ((holder.userData.bandLength || 6) / 2) * scale / seg));
  holder.position.copy(A.lerp(B, t));
  holder.scale.setScalar(scale);
  holder.visible = true;
  return { finger, scale: +scale.toFixed(3), facing: +zAxis.z.toFixed(2) };
}

function placeRing(srcW, srcH) {
  const hand = state.hand;
  if (!hand || !srcW || !window.__tryon.built) { arMain.visible = arSecond.visible = false; return; }
  const P = mapper(srcW, srcH);
  const pts = hand.lms.map((p) => P(p));
  const spacing = (pts[5].distanceTo(pts[9]) + pts[9].distanceTo(pts[13]) + pts[13].distanceTo(pts[17])) / 3;
  // Normal of the back of the hand. The handedness label is unreliable on photos, so decide by anatomy:
  // the thumb and curled fingertips sit on the palm side of the wrist–knuckle plane.
  const raw = new THREE.Vector3().subVectors(pts[5], pts[0]).cross(new THREE.Vector3().subVectors(pts[17], pts[0])).normalize();
  let vote = 0;
  for (const [k, w] of [[2, 1], [3, 1], [4, 1], [8, 0.4], [12, 0.4], [16, 0.4], [20, 0.4]]) {
    vote += w * new THREE.Vector3().subVectors(pts[k], pts[0]).dot(raw);
  }
  const unsure = Math.abs(vote) < spacing * 0.05;
  const palm = (unsure ? hand.handed === "Right" : vote > 0) ? raw.clone().negate() : raw.clone();
  const debug = { handed: hand.handed, vote: +(vote / spacing).toFixed(2), main: placeOn(arMain, state.finger, pts, spacing, palm) };
  window.__tryon.landmarks = pts.map((p) => [+p.x.toFixed(1), +(-p.y).toFixed(1)]);   // stage pixels, y down
  if (state.hasSecond) debug.second = placeOn(arSecond, NEIGHBOR[state.finger], pts, spacing, palm);
  else arSecond.visible = false;
  window.__tryon.placed = true;
  window.__tryon.debug = debug;
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
      // ask for the sharpest stream the phone will give; it falls back on its own if this is too much
      video: {
        facingMode: state.facing, width: { ideal: 1920 }, height: { ideal: 1440 },
        frameRate: { ideal: 30 }, resizeMode: "none"
      },
      audio: false
    });
  } catch {
    setHint("Camera blocked — try the Photo mode");
    return;
  }
  video.srcObject = state.stream;
  await video.play().catch(() => {});
  const s = state.stream.getVideoTracks()[0]?.getSettings?.() || {};
  window.__tryon.camera = `${s.width || video.videoWidth}x${s.height || video.videoHeight}@${Math.round(s.frameRate || 0)}`;
  stage.classList.toggle("mirror", state.facing === "user");
  setHint("Show the back of your hand");
  await getLandmarker("VIDEO").catch(() => {});
}

async function loadPhoto(src) {
  photo.hidden = false;
  arMain.visible = arSecond.visible = false;
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
  $("fit").hidden = !ar;
  if (mode !== "live") stopCamera();
  if (mode !== "photo") photo.hidden = true;
  arMain.visible = arSecond.visible = false;
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
  step();
}

// One frame of work. Exposed for headless tests, where requestAnimationFrame may never fire.
function step() {
  resize();
  if (state.mode === "3d") {
    controls.update();
    renderer.render(viewScene, viewCam);
  } else {
    // Track at ~20 Hz, draw at screen rate: hand tracking on every frame starves the preview on a phone,
    // and the ring keeps following the hand from the smoothed landmarks in between.
    if (state.mode === "live" && state.landmarker && state.lmMode === "VIDEO" && video.readyState >= 2
        && video.currentTime !== state.lastVideoTime && performance.now() - state.lastDetect > 45) {
      state.lastVideoTime = video.currentTime;
      state.lastDetect = performance.now();
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
window.__tryon.step = step;

buildGrid();
setViewCamera(1);
rebuild().catch((e) => { window.__tryon.error = String(e); setHint("This ring could not be loaded"); });
setHint("Drag to rotate · pinch to zoom");
frame();
if (params.get("photo")) setMode("photo");
