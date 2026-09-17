import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RINGS, METAL, parseColor, bandHex } from "./catalog.js";
import { createRing, setGemEnvironment, INNER_RADIUS, siliconeMat, frostedMat, metalMat, gemMeshes } from "./rings.js";
import { stoneMaterial, simpleStoneMaterial } from "./gem.js";

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
  w: 0, h: 0, hasSecond: false, viewCount: 0, buildToken: 0, offset: { x: 0, y: 0 }, capturing: false
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
// The traced stone keeps its facet planes in a fragment uniform array. Phones have far less room for those
// than a desktop (iOS reports 1024 vectors against 4096 here), so ask the device how much it has and leave
// headroom for three.js's own uniforms; anything over budget falls back to the simple faceted stone.
const GEM_BUDGET = Math.max(64, Math.floor((renderer.capabilities.maxFragmentUniforms || 1024) * 0.35));
const GEM_BOUNCES = renderer.capabilities.maxFragmentUniforms > 2048 ? 7 : 5;
const tracedStones = new Set();
let gemBroken = new URLSearchParams(location.search).get("gem") === "simple" ? "forced by ?gem=simple" : null;
// Documented three.js hook: fires when a program fails to compile or link instead of silently drawing nothing.
renderer.debug.onShaderError = (gl, program, vs, fs) => {
  const log = (gl.getShaderInfoLog(fs) || gl.getShaderInfoLog(vs) || gl.getProgramInfoLog(program) || "").trim();
  gemBroken = log.slice(0, 300) || "shader compile failed";
  console.warn("shader failed, falling back to the simple stone:", gemBroken);
};
function useSimpleStones() {
  for (const o of tracedStones) {
    const black = o.material?.userData?.gem?.black;
    o.material?.dispose?.();
    o.material = simpleStoneMaterial({ black });
  }
  tracedStones.clear();
}
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
      o.material = gemBroken ? simpleStoneMaterial({ black })
                             : stoneMaterial(o.geometry, { black, budget: GEM_BUDGET, bounces: GEM_BOUNCES });
      if (!gemBroken) tracedStones.add(o);
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
const NO_SMOOTH = new URLSearchParams(location.search).get("smooth") === "0";   // for measuring the smoothing

function addToAr(holder, piece) {
  const occluder = new THREE.Mesh(
    new THREE.CylinderGeometry(INNER_RADIUS * OCC, INNER_RADIUS * OCC, piece.bandLength + 60, 40),
    new THREE.MeshBasicMaterial({ colorWrite: false })
  );
  // A finger is wider than it is deep, so the hider is an oval, not a circle: a round one either lets the
  // band's ends stick out past the silhouette or eats the band where it crosses the top of the finger.
  occluder.scale.set(1, 1, 0.85);
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
  syncLike();
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

/* ---------- putting it on by hand ----------
   Tracking gets the ring near the right place; the shopper finishes the job the way they would in front of a
   mirror: drag it along the finger, pinch to size it. Photo mode is where this matters — the hand is still. */
const touches = new Map();
let pinchFrom = 0;

function resetAdjust() {
  state.offset.x = state.offset.y = 0;
  touches.clear();
  pinchFrom = 0;
}

stage.addEventListener("pointerdown", (e) => {
  if (state.mode === "3d" || !$("shot-card").hidden || !$("photo-intro").hidden) return;
  if (e.target.closest("button, .modes, .fingers, .fit")) return;   // the controls keep their taps
  stage.setPointerCapture(e.pointerId);
  touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (touches.size === 2) {
    const [a, b] = [...touches.values()];
    pinchFrom = Math.hypot(a.x - b.x, a.y - b.y);
  }
});

stage.addEventListener("pointermove", (e) => {
  const was = touches.get(e.pointerId);
  if (!was) return;
  const now = { x: e.clientX, y: e.clientY };
  touches.set(e.pointerId, now);
  if (touches.size === 1) {
    state.offset.x += now.x - was.x;
    state.offset.y -= now.y - was.y;          // stage y counts upwards
  } else if (touches.size === 2 && pinchFrom > 8) {
    const [a, b] = [...touches.values()];
    const span = Math.hypot(a.x - b.x, a.y - b.y);
    setFit(state.fit * (span / pinchFrom));
    pinchFrom = span;
  }
});

for (const type of ["pointerup", "pointercancel", "pointerleave"]) {
  stage.addEventListener(type, (e) => {
    touches.delete(e.pointerId);
    if (touches.size < 2) pinchFrom = 0;
  });
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
  return {
    lms: result.landmarks[best],
    // Metric 3D landmarks, origin at the hand's own centre, axes aligned with the camera. The flat picture
    // loses a finger's direction the moment it points at the lens; these keep it.
    world: result.worldLandmarks?.[best] || null,
    handed: result.handedness[best][0].categoryName,
  };
}

function onResult(result, live) {
  const hand = pickHand(result);
  if (!hand) return false;
  if (live && state.hand && state.hand.handed === hand.handed && performance.now() - state.lastSeen < 300) {
    const blend = (prev, next) => prev.map((p, i) => {
      const q = next[i];
      return { x: p.x + (q.x - p.x) * SMOOTH, y: p.y + (q.y - p.y) * SMOOTH, z: p.z + (q.z - p.z) * SMOOTH };
    });
    state.hand.lms = blend(state.hand.lms, hand.lms);
    if (state.hand.world && hand.world) state.hand.world = blend(state.hand.world, hand.world);
  } else {
    const copy = (l) => l.map((p) => ({ x: p.x, y: p.y, z: p.z }));
    state.hand = { lms: copy(hand.lms), world: hand.world ? copy(hand.world) : null, handed: hand.handed };
  }
  state.lastSeen = performance.now();
  return true;
}

// Map a normalized landmark to stage pixels. Live video fills the stage (cover),
// photos are shown whole (contain) so no hand gets cropped away.
const fitMode = () => (state.mode === "photo" ? "contain" : "cover");
function frameFitInfo(srcW, srcH) {
  const sc = fitMode() === "contain" ? Math.min(state.w / srcW, state.h / srcH) : Math.max(state.w / srcW, state.h / srcH);
  return { sc, ox: (state.w - srcW * sc) / 2, oy: (state.h - srcH * sc) / 2 };
}
function mapper(srcW, srcH) {
  const { sc, ox, oy } = frameFitInfo(srcW, srcH);
  return (p) => new THREE.Vector3(ox + p.x * srcW * sc, -(oy + p.y * srcH * sc), -p.z * srcW * sc);
}

/* Reading the finger's real width off the camera frame was tried twice and dropped both times, so the ring's
   size comes from the landmarks plus the shopper's own -/+ knob:
     - by skin colour (walk out from the middle until the colour stops being skin): stops on the shading near
       the edge, gave 21 px where the finger was ~33;
     - by strongest change across the finger: latches onto the shadow between fingers or the next finger, gave
       40 px on the same hand. Drawing the found edges over the photo showed them off the finger entirely.
   Anything new here has to be checked the same way — overlay the edges it finds on a real photo first. */

function placeOn(holder, finger, pts, W, m, palm, dt) {
  const [ia, ib, widthK] = FINGERS[finger];
  const A = pts[ia].clone(), B = pts[ib].clone();
  // Direction along the finger is read in 3D. On the picture this segment collapses to a few pixels whenever
  // the finger points at the lens or curls up — and a direction taken from those pixels is noise, which is
  // exactly when the ring used to spin. In metric space the segment keeps its length whatever the pose.
  // The direction the ring sits across comes from the picture, because that is what the shopper sees: a band
  // built from the metric landmarks alone comes out slanted, since that space has its own orientation and
  // does not line up with the frame. The metric pair is used only for how far the finger leans towards the
  // lens, which the picture cannot tell — that keeps the perspective honest without tilting the band.
  const flat = new THREE.Vector3(B.x - A.x, B.y - A.y, 0);
  const seen = flat.length() || 1;
  const spanW = W[ib].clone().sub(W[ia]);
  const sinLean = spanW.length() > 1e-6 ? THREE.MathUtils.clamp(-spanW.z / spanW.length(), -0.85, 0.85) : 0;
  const axis = new THREE.Vector3(flat.x, flat.y, seen * sinLean / Math.sqrt(1 - sinLean * sinLean)).normalize();
  // Size stays on the picture. The metric landmarks are normalised to an average hand, not to this shopper's,
  // so sizing from them came out ~1.7x too wide; these three measures are calibrated against real photos and
  // each only shrinks when the hand turns away, hence the largest.
  const fingerWidth = Math.max(m.spacing2 * 0.86, pts[0].distanceTo(pts[9]) * 0.185, A.distanceTo(B) * 0.42)
                      * widthK * state.fit;
  const scale = fingerWidth / (INNER_RADIUS * 2);
  const zAxis = palm.clone().sub(axis.clone().multiplyScalar(palm.dot(axis))).normalize();
  const xAxis = new THREE.Vector3().crossVectors(axis, zAxis).normalize();
  const quat = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(xAxis, axis, zAxis));
  window.__tryon.fit = { finger, fingerWidth: +fingerWidth.toFixed(1), knob: +state.fit.toFixed(3),
                         offset: [Math.round(state.offset.x), Math.round(state.offset.y)] };
  // Long stacks move further up the finger so they do not sink into the knuckle.
  const seg = Math.max(A.distanceTo(B), 1);
  const t = Math.min(0.65, Math.max(RING_POS, 0.3 + ((holder.userData.bandLength || 6) / 2) * scale / seg));
  const pos = A.lerp(B, t);
  pos.x += state.offset.x;      // where the shopper dragged it
  pos.y += state.offset.y;

  // Hand tracking wobbles by a few pixels every frame, and tracking now runs slower than drawing.
  // Smooth the ring's own pose instead of the landmarks: heavily while the hand is still, lightly while it
  // moves, so the ring neither shivers in place nor lags behind a moving hand.
  let f = holder.userData.pose;
  if (!f || NO_SMOOTH) {
    f = holder.userData.pose = { pos: pos.clone(), quat: quat.clone(), scale };
  } else {
    const move = f.pos.distanceTo(pos);
    const speed = move / Math.max(dt, 0.001);                    // stage pixels per second
    const rate = (base, k) => 1 - Math.exp(-dt * (base + speed * k));
    // dead zones: below these the tracker is only breathing, and a ring that answers it never looks pinned
    if (move > 0.5) f.pos.lerp(pos, rate(7, 0.05));
    if (f.quat.angleTo(quat) > 0.009) f.quat.slerp(quat, rate(6, 0.04));       // ~0.5 degrees
    if (Math.abs(scale - f.scale) > f.scale * 0.006) {
      f.scale += (scale - f.scale) * rate(3, 0.01);              // size changes slowest: the most visible wobble
    }
  }
  holder.position.copy(f.pos);
  holder.quaternion.copy(f.quat);
  holder.scale.setScalar(f.scale);
  holder.visible = true;
  return { finger, scale: +f.scale.toFixed(3), facing: +zAxis.z.toFixed(2) };
}

function placeRing(srcW, srcH) {
  const hand = state.hand;
  const now = performance.now();
  const dt = Math.min(0.1, Math.max(0.001, (now - (state.lastPlace || now)) / 1000));
  state.lastPlace = now;
  if (!hand || !srcW || !window.__tryon.built) {
    arMain.visible = arSecond.visible = false;
    arMain.userData.pose = arSecond.userData.pose = null;   // next hand starts in place, not flying in
    state.isRight = undefined; state.handVotes = 0;        // and decides which hand it is from scratch
    return;
  }
  const P = mapper(srcW, srcH);
  const pts = hand.lms.map((p) => P(p));
  // Same axes as the stage: x right, y up, z towards the viewer.
  const W = (hand.world || hand.lms).map((p) => new THREE.Vector3(p.x, -p.y, -p.z));
  // test hook: shake the landmarks the way live tracking does, to measure what the smoothing removes
  const shake = +(window.__tryon.jitter || 0);
  if (shake) for (const p of pts) { p.x += (Math.random() - 0.5) * shake; p.y += (Math.random() - 0.5) * shake; }
  const spacing = (pts[5].distanceTo(pts[9]) + pts[9].distanceTo(pts[13]) + pts[13].distanceTo(pts[17])) / 3;
  const spacing3 = (W[5].distanceTo(W[9]) + W[9].distanceTo(W[13]) + W[13].distanceTo(W[17])) / 3;
  const measure = { spacing2: spacing, spacing: spacing3 };
  // Normal of the back of the hand. The handedness label is unreliable on photos, so decide by anatomy:
  // the thumb and curled fingertips sit on the palm side of the wrist–knuckle plane.
  const raw = W[5].clone().sub(W[0]).cross(W[17].clone().sub(W[0])).normalize();
  let vote = 0;
  for (const [k, w] of [[2, 1], [3, 1], [4, 1], [8, 0.4], [12, 0.4], [16, 0.4], [20, 0.4]]) {
    vote += w * W[k].clone().sub(W[0]).dot(raw);
  }
  const v = vote / Math.max(spacing3, 1e-4);
  // Which side of the finger the stone sits on is one question only: WHICH HAND this is. The cross product
  // above is the chirality of the hand's own landmarks, so for a given hand it always points out of the same
  // face, whatever the pose — and its z then says by itself whether we are looking at the back or the palm.
  // Two independent readings of the hand, because each fails where the other works:
  //   - MediaPipe's label, which it defines for a MIRRORED frame. Every frame we hand it is raw — getUserMedia
  //     gives the sensor image and only the preview is flipped by CSS — so the label always means the other
  //     hand here and is swapped once, for the camera and for photos alike.
  //   - the anatomy vote, which is decisive on a curled hand and ~0 on a flat open one (measured 0.01).
  // Taken in 3D the vote is decisive on an open hand too — the thumb really does sit off the knuckle plane,
  // it only looked flat once the picture flattened it. That is what used to freeze the answer on frame one.
  let isRight = hand.handed === "Left";
  if (Math.abs(v) > 0.25) isRight = v < 0;
  // Hysteresis belongs on the hand, not on the facing: a hand does not change between frames, while turning
  // it over must turn the ring over at once. The old code held the facing instead, and since a flat open hand
  // gives no anatomy vote, it froze on its first guess and never noticed the hand being turned.
  if (state.isRight === undefined) state.isRight = isRight;
  else if (isRight !== state.isRight) {
    state.handVotes = state.handLast === isRight ? (state.handVotes || 0) + 1 : 1;
    state.handLast = isRight;
    if (state.handVotes >= 3) { state.isRight = isRight; state.handVotes = 0; }
  } else state.handVotes = 0;
  // The stone always rides on the back of the finger, so this is where it points. The vector has to live in
  // the same space as the ring's axis — the picture — otherwise the two disagree and the ring rolls round the
  // finger until the stone slides off its middle. Which face of the hand this is was already settled above
  // from the metric landmarks, which is what they are good for.
  // Both readings of that direction carry the tracker's depth guess, which is rough, and a few degrees of
  // error there rolls the ring round the finger until the stone sits on its edge. What a shopper wants is
  // plain: the stone in the middle of the finger, facing them. So the stone is aimed straight at the lens,
  // and the metric landmarks keep only the one call they make reliably — back of the hand, or palm, which
  // decides whether the stone shows at all.
  const towardsCamera = (state.isRight ? raw.z : -raw.z) >= 0 ? 1 : -1;
  const palm = new THREE.Vector3(0, 0, towardsCamera);
  // A finger pointing at the camera or curled up gives a segment barely a few pixels long: its direction is
  // noise, so hold the last good pose instead of throwing the ring around.
  // A finger folded into a fist has no place to wear a ring that the camera can see: its knuckle segment
  // points away, so any ring drawn there floats beside the hand instead of sitting on skin. Both checks are
  // made in 3D, where a folded finger reads as folded no matter which way the hand is turned.
  const straight = (f) => {
    const [a, b] = FINGERS[f];
    const proximal = W[b].clone().sub(W[a]);
    const middle = W[b + 1].clone().sub(W[b]);
    if (proximal.length() < 1e-4 || middle.length() < 1e-4) return false;
    return proximal.normalize().dot(middle.normalize()) > 0.45;      // < ~63 degrees between the phalanges
  };
  const reliable = (f) => W[FINGERS[f][0]].distanceTo(W[FINGERS[f][1]]) > spacing3 * 0.45 && straight(f);
  const debug = { handed: hand.handed, isRight: state.isRight, vote: +v.toFixed(2), nz: +palm.z.toFixed(2), world: !!hand.world };
  if (reliable(state.finger)) {
    debug.main = placeOn(arMain, state.finger, pts, W, measure, palm, dt);
    state.badFinger = 0;
  } else {
    // Hold the last pose for a blink — a single bad frame should not make the ring flicker — then take it off
    // and say why, instead of leaving it hanging in mid-air next to a fist.
    state.badFinger = (state.badFinger || 0) + dt;
    const hold = state.badFinger < 0.4 && arMain.userData.pose;
    arMain.visible = !!hold;
    arSecond.visible = arSecond.visible && !!hold;
    debug.main = hold ? "held" : "finger-folded";
    if (!hold && state.mode === "live") setHint(straight(state.finger) ? "Show the back of your hand" : "Straighten the finger you are trying on");
  }
  window.__tryon.landmarks = pts.map((p) => [+p.x.toFixed(1), +(-p.y).toFixed(1)]);   // stage pixels, y down
  if (state.hasSecond && reliable(NEIGHBOR[state.finger])) {
    debug.second = placeOn(arSecond, NEIGHBOR[state.finger], pts, W, measure, palm, dt);
  } else if (!state.hasSecond) {
    arSecond.visible = false;
  }
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
  $("photo-intro").hidden = true;
  arMain.visible = arSecond.visible = false;
  state.hand = null;
  resetAdjust();
  setHint("Finding your hand…");
  photo.src = src;
  try { await photo.decode(); } catch { setHint("This image could not be opened"); return; }
  const lm = await getLandmarker("IMAGE").catch(() => null);
  if (!lm) return;
  const found = onResult(lm.detect(photo), false);
  setHint(found ? "Drag the ring · pinch to resize" : "No hand found — try a photo with the back of the hand");
}

$("file").onchange = (e) => {
  const f = e.target.files?.[0];
  if (f) loadPhoto(URL.createObjectURL(f));
};
$("intro-gallery").onclick = () => $("file").click();

/* ---------- taking the photo here, not in a file dialog ----------
   A file input with capture="environment" only opens the camera on a phone; on a laptop it is just a file
   picker, which is why "Take a photo" looked like it went to the gallery. So the camera opens in the page:
   the shopper sees their hand, presses the button, and that frame goes straight into the try-on. */
$("intro-camera").onclick = async () => {
  $("photo-intro").hidden = true;
  photo.hidden = true;
  state.capturing = true;
  video.hidden = false;
  $("shot").hidden = false;
  $("flip").hidden = false;
  setHint("Hold your hand as shown, then press the big round button");
  stage.classList.add("capturing");
  stopCamera();
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: state.facing, width: { ideal: 1920 }, height: { ideal: 1440 } }, audio: false
    });
  } catch {
    state.capturing = false;
    video.hidden = true;
    stage.classList.remove("capturing");
    $("photo-intro").hidden = false;
    setHint("Camera blocked — choose a photo from the gallery");
    return;
  }
  video.srcObject = state.stream;
  await video.play().catch(() => {});
  stage.classList.toggle("mirror", state.facing === "user");
};

function grabFrame() {
  const w = video.videoWidth, h = video.videoHeight;
  if (!w) return;
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d");
  if (state.facing === "user") { g.translate(w, 0); g.scale(-1, 1); }   // keep the picture she was looking at
  g.drawImage(video, 0, 0, w, h);
  state.capturing = false;
  stopCamera();
  video.hidden = true;
  stage.classList.remove("mirror", "capturing");
  loadPhoto(c.toDataURL("image/jpeg", 0.92));
}

async function setMode(mode) {
  state.mode = mode;
  for (const m of ["3d", "live", "photo"]) $(`mode-${m}`).setAttribute("aria-pressed", String(m === mode));
  const ar = mode !== "3d";
  canvas.classList.toggle("ar", ar);
  stage.classList.remove("mirror");
  video.hidden = mode !== "live";
  $("flip").hidden = mode !== "live";
  $("shot").hidden = !ar;
  $("shot-card").hidden = true;
  $("photo-intro").hidden = true;
  state.capturing = false;
  stage.classList.remove("capturing");
  controls.enabled = mode === "3d";   // in try-on a drag moves the ring, it does not orbit the camera
  resetAdjust();
  $("fit").hidden = !ar;
  if (mode !== "live") stopCamera();
  if (mode !== "photo") photo.hidden = true;
  arMain.visible = arSecond.visible = false;
  arMain.userData.pose = arSecond.userData.pose = null;
  state.hand = null;

  if (mode === "3d") setHint("Drag to rotate · pinch to zoom");
  if (mode === "live") startCamera();
  if (mode === "photo") {
    // first the shopper is shown how to hold the hand, then they shoot, then they put the ring on by hand
    if (params.get("photo") && !photo.dataset.used) { photo.dataset.used = "1"; loadPhoto(params.get("photo")); }
    else if (photo.src) { photo.hidden = false; loadPhoto(photo.src); }
    else { setHint(""); $("photo-intro").hidden = false; }
  }
}
$("mode-3d").onclick = () => setMode("3d");
$("mode-live").onclick = () => setMode("live");
$("mode-photo").onclick = () => setMode("photo");
$("flip").onclick = () => {
  state.facing = state.facing === "user" ? "environment" : "user";
  if (state.capturing) $("intro-camera").onclick();   // still framing the hand: restart that camera
  else startCamera();
};

/* ---------- snapshot and saved rings ---------- */
let favs = new Set();
try { favs = new Set(JSON.parse(localStorage.getItem("rinfit-favs") || "[]")); } catch { /* private mode */ }
let shotUrl = null;

function syncLike() {
  const on = favs.has(state.ring.id);
  for (const id of ["p-like", "shot-like"]) $(id).setAttribute("aria-pressed", String(on));
}

function renderFavs() {
  const list = RINGS.filter((r) => favs.has(r.id));
  $("fav-wrap").hidden = !list.length;
  $("fav-count").textContent = list.length ? `· ${list.length}` : "";
  $("favs").replaceChildren(...list.map((r) => {
    const b = document.createElement("button");
    b.className = "card";
    b.innerHTML = `<img alt="" loading="lazy"><b></b><span></span>`;
    b.querySelector("img").src = r.img;
    b.querySelector("b").textContent = r.name;
    b.querySelector("span").textContent = `$${r.price.toFixed(2)}`;
    b.onclick = () => { state.ring = r; state.color = r.colors[0]; rebuild(); };
    return b;
  }));
}

function toggleFav() {
  const id = state.ring.id;
  if (favs.has(id)) favs.delete(id);
  else favs.add(id);
  try { localStorage.setItem("rinfit-favs", JSON.stringify([...favs])); } catch { /* private mode */ }
  syncLike();
  renderFavs();
}
$("p-like").onclick = toggleFav;
$("shot-like").onclick = toggleFav;

// A shopper keeps this photo or sends it to a friend, so it has to say whose ring it is.
function brand(g, w, h) {
  const pad = Math.round(w * 0.045);
  const strip = Math.round(h * 0.17);
  const grad = g.createLinearGradient(0, h - strip, 0, h);
  grad.addColorStop(0, "rgba(17,17,17,0)");
  grad.addColorStop(1, "rgba(17,17,17,.55)");
  g.fillStyle = grad;
  g.fillRect(0, h - strip, w, strip);
  const big = Math.round(w * 0.042), small = Math.round(w * 0.028);
  g.fillStyle = "#ffffff";
  g.textBaseline = "alphabetic";
  g.font = `700 ${big}px "Kumbh Sans", system-ui, sans-serif`;
  try { g.letterSpacing = `${Math.round(big * 0.18)}px`; } catch { /* older browsers */ }
  g.fillText("RINFIT", pad, h - pad - Math.round(small * 1.9));
  try { g.letterSpacing = "0px"; } catch { /* older browsers */ }
  g.font = `500 ${small}px "Kumbh Sans", system-ui, sans-serif`;
  g.globalAlpha = 0.92;
  g.fillText(`${state.ring.name} · ${state.color}`, pad, h - pad);
  g.textAlign = "right";
  g.fillText(`$${state.ring.price.toFixed(2)} · rinfit.com`, w - pad, h - pad);
  g.textAlign = "left";
  g.globalAlpha = 1;
}

$("shot").onclick = () => {
  if (state.capturing) return grabFrame();   // still taking the picture of the hand
  const out = document.createElement("canvas");
  out.width = canvas.width; out.height = canvas.height;
  const g = out.getContext("2d");
  const src = state.mode === "live" ? video : photo;
  const sw = src.videoWidth || src.naturalWidth, sh = src.videoHeight || src.naturalHeight;
  g.fillStyle = "#e9e4e1";
  g.fillRect(0, 0, out.width, out.height);
  if (sw) {
    const sc = fitMode() === "contain" ? Math.min(out.width / sw, out.height / sh) : Math.max(out.width / sw, out.height / sh);
    g.save();
    if (stage.classList.contains("mirror")) { g.translate(out.width, 0); g.scale(-1, 1); }
    g.drawImage(src, (out.width - sw * sc) / 2, (out.height - sh * sc) / 2, sw * sc, sh * sc);
    g.drawImage(canvas, 0, 0);
    g.restore();
  }
  brand(g, out.width, out.height);
  shotUrl = out.toDataURL("image/png");
  $("shot-img").src = shotUrl;
  $("shot-card").hidden = false;
  syncLike();
};
$("shot-close").onclick = () => { $("shot-card").hidden = true; };
$("shot-save").onclick = () => {
  const a = document.createElement("a");
  a.download = `rinfit-${state.ring.id}.png`;
  a.href = shotUrl;
  a.click();
};
$("shot-share").onclick = async () => {
  try {
    const blob = await (await fetch(shotUrl)).blob();
    const file = new File([blob], `rinfit-${state.ring.id}.png`, { type: "image/png" });
    if (navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], text: `${state.ring.name} · Rinfit` });
      return;
    }
  } catch { /* cancelled, or sharing files is not supported */ }
  $("shot-save").click();
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
  if (gemBroken && tracedStones.size) useSimpleStones();
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
// ?diag=1 — one tap on a phone tells us what the device actually did with the stone shader.
function diagnostics() {
  const c = renderer.capabilities, gl = renderer.getContext();
  const stone = [...tracedStones][0]?.material?.userData?.gem;
  return {
    gpu: gl.getParameter(gl.getExtension("WEBGL_debug_renderer_info")?.UNMASKED_RENDERER_WEBGL || gl.RENDERER),
    webgl2: c.isWebGL2, fragUniformVectors: c.maxFragmentUniforms, budget: GEM_BUDGET, bounces: GEM_BOUNCES,
    ring: state.ring.id, stone: stone || (gemBroken ? "simple (shader failed)" : "simple"),
    shaderError: gemBroken || null, pixelRatio: renderer.getPixelRatio(), camera: window.__tryon.camera || null,
    mode: state.mode, cameraFacing: state.facing, hand: window.__tryon.debug || null
  };
}
window.__tryon.diagnostics = diagnostics;
if (params.get("diag") === "1") {
  const box = document.createElement("pre");
  box.style.cssText = "position:fixed;left:8px;right:8px;bottom:8px;z-index:99;margin:0;padding:10px 12px;" +
    "background:rgba(20,20,20,.92);color:#eee;font:11px/1.5 ui-monospace,Menlo,monospace;border-radius:10px;" +
    "white-space:pre-wrap;max-height:45vh;overflow:auto";
  document.body.appendChild(box);
  setInterval(() => { box.textContent = JSON.stringify(diagnostics(), null, 1); }, 700);
}
window.__tryon.step = step;

buildGrid();
renderFavs();
setViewCamera(1);
rebuild().catch((e) => { window.__tryon.error = String(e); setHint("This ring could not be loaded"); });
setHint("Drag to rotate · pinch to zoom");
frame();
if (params.get("photo")) setMode("photo");
