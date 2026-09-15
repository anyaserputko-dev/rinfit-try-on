// Procedural 3D models of Rinfit rings, built from product specs and photos.
// Units: millimetres. Local frame: +Y along the finger, +Z towards the back of the hand (stone side).
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { METAL, parseColor, bandHex } from "./catalog.js";

export const INNER_RADIUS = 8.66; // US size 7: 17.32 mm inner diameter (Rinfit size chart)

/* ---------- materials ---------- */
const luminance = (c) => 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b;

// Silicone: soft satin, low reflections so pastel and dark colors keep their real tone.
function siliconeMat(hex, finish) {
  const color = new THREE.Color(hex);
  const light = Math.min(1, luminance(color) * 1.6);
  return new THREE.MeshPhysicalMaterial({
    color, metalness: 0,
    roughness: finish === "matte" ? 0.72 : 0.55,
    specularIntensity: finish === "matte" ? 0.25 : 0.45,
    sheen: 0.12 + 0.18 * light, sheenRoughness: 0.7, sheenColor: color.clone(),
    envMapIntensity: 0.18 + 0.22 * light,
    side: THREE.DoubleSide
  });
}
const frostedMat = () => new THREE.MeshPhysicalMaterial({
  color: "#eef2f3", roughness: 0.6, metalness: 0, transparent: true, opacity: 0.78,
  envMapIntensity: 0.45, side: THREE.DoubleSide
});
const metalMat = (name) => new THREE.MeshStandardMaterial({
  color: METAL[name] || METAL.Silver, metalness: 1, roughness: 0.1, envMapIntensity: 1.85, side: THREE.DoubleSide
});
// Cut stone without real refraction (live video has nothing behind the stone to bend):
// the inner layer shows the pavilion facets from inside as mirrors, the outer layer adds the glassy surface.
let gemEnv = null;
export function setGemEnvironment(texture) { gemEnv = texture; }
function gemMeshes(geo, black, small = false) {
  const inner = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: black ? "#26262b" : "#ffffff", metalness: 1, roughness: 0.03, envMap: gemEnv,
    envMapIntensity: black ? 0.22 : small ? 2.4 : 1.5, flatShading: true, side: THREE.BackSide,
    emissive: "#ffffff", emissiveIntensity: small && !black ? 0.18 : 0   // tiny pavé stones would average to grey
  }));
  const outer = new THREE.Mesh(geo, new THREE.MeshPhysicalMaterial({
    color: black ? "#0c0c0f" : "#ffffff", metalness: 0, roughness: 0, ior: 2.2, specularIntensity: 1,
    transparent: true, opacity: black ? 0.55 : small ? 0.3 : 0.18, depthWrite: false, envMap: gemEnv,
    envMapIntensity: black ? 0.9 : small ? 2.2 : 1.6, flatShading: true,
    iridescence: black ? 0 : 0.6, iridescenceIOR: 2, iridescenceThicknessRange: [250, 520]
  }));
  inner.renderOrder = 1;
  outer.renderOrder = 2;
  return [inner, outer];
}

function inkFor(hex) {
  const c = new THREE.Color(hex);
  return (luminance(c) < 0.04 ? c.lerp(new THREE.Color(1, 1, 1), 0.1) : c.multiplyScalar(0.72)).getStyle();
}

// Keep only position + normal so pieces of different geometry types can be merged.
function toStd(geo) {
  const g = geo.index ? geo.toNonIndexed() : geo;
  for (const k of Object.keys(g.attributes)) if (k !== "position" && k !== "normal") g.deleteAttribute(k);
  if (!g.attributes.normal) g.computeVertexNormals();
  return g;
}

/* ---------- bands ---------- */
// Closed cross-section in (radius, y), revolved around Y.
function bandProfile({ inner: R, thickness: t, width: w, style = "flat", innerStep = false }) {
  const hw = w / 2, rc = Math.min(t, w) * 0.4, Ro = R + t;
  const outerAt = (y) => {
    if (style === "dome") return Ro - 0.55 * (y / hw) ** 2;
    if (style === "step") return y < -hw + 2.6 ? Ro - 0.6 : Ro;   // Infinity: lower ledge along one edge
    return Ro - 0.1 * (y / hw) ** 2;
  };
  const innerAt = (y) => (innerStep && Math.abs(y) < hw - 1.9 ? R + 0.35 : R); // Inner Step Edge: recessed centre
  const pts = [];
  const add = (x, y) => {
    const last = pts[pts.length - 1];
    if (!last || Math.hypot(last.x - x, last.y - y) > 1e-4) pts.push(new THREE.Vector2(x, y));
  };
  const arc = (cx, cy, a0, a1, n = 6) => {
    for (let i = 0; i <= n; i++) {
      const a = a0 + (a1 - a0) * (i / n);
      add(cx + Math.cos(a) * rc, cy + Math.sin(a) * rc);
    }
  };
  const yA = -hw + rc, yB = hw - rc, N = 32;
  for (let i = 0; i <= N; i++) { const y = yA + (yB - yA) * (i / N); add(innerAt(y), y); }
  arc(R + rc, yB, Math.PI, Math.PI / 2);
  const rTop = outerAt(hw), rBot = outerAt(-hw);
  arc(rTop - rc, yB, Math.PI / 2, 0);
  for (let i = 1; i < N; i++) { const y = yB - (yB - yA) * (i / N); add(outerAt(y), y); }
  arc(rBot - rc, yA, 0, -Math.PI / 2);
  arc(R + rc, yA, -Math.PI / 2, -Math.PI);
  if (pts.length > 2 && pts[0].distanceTo(pts[pts.length - 1]) < 1e-4) pts.pop();
  return pts;
}

function latheBand(spec, material, segs = 160) {
  const pts = bandProfile(spec);
  return new THREE.Mesh(new THREE.LatheGeometry([...pts, pts[0].clone()], segs), material);
}

// Band whose centre line moves along the finger as it goes round (V-shaped bands).
function sweptBand(spec, yOf, segs = 240) {
  const prof = bandProfile(spec), n = prof.length, pos = [], idx = [];
  for (let i = 0; i < segs; i++) {
    const phi = (i / segs) * Math.PI * 2, s = Math.sin(phi), c = Math.cos(phi), dy = yOf(phi);
    for (const p of prof) pos.push(p.x * s, p.y + dy, p.x * c);
  }
  for (let i = 0; i < segs; i++) {
    const i2 = (i + 1) % segs;
    for (let j = 0; j < n; j++) {
      const j2 = (j + 1) % n;
      const a = i * n + j, b = i2 * n + j, c = i2 * n + j2, d = i * n + j2;
      idx.push(a, b, d, b, c, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

// V peak at the top of the ring (phi = 0) with soft shoulders.
function chevronY(amplitude, halfAngle, sharp = false) {
  const h = sharp ? 0.08 : 0.16, eps = sharp ? 0.002 : 0.006;
  const relu = (s) => (s >= h ? s : s <= -h ? 0 : ((s + h) * (s + h)) / (4 * h));
  return (phi) => {
    const a = Math.atan2(Math.sin(phi), Math.cos(phi));
    return amplitude * relu(1 - Math.sqrt(a * a + eps) / halfAngle);
  };
}

// Pyramid texture on the outer surface.
function studGeometry(R, t, yOf, pitch, size) {
  const Ro = R + t, count = Math.round((2 * Math.PI * Ro) / pitch), geos = [];
  for (let k = 0; k < count; k++) {
    const phi = (k / count) * Math.PI * 2;
    const g = new THREE.ConeGeometry(size, size * 0.62, 4, 1);
    g.translate(0, size * 0.31 - 0.1, 0);
    const n = new THREE.Vector3(Math.sin(phi), 0, Math.cos(phi));
    const tan = new THREE.Vector3(Math.cos(phi), 0, -Math.sin(phi));
    const b = new THREE.Vector3().crossVectors(tan, n);
    g.applyMatrix4(new THREE.Matrix4().makeBasis(tan, n, b).setPosition(n.clone().multiplyScalar(Ro).setY(yOf(phi))));
    geos.push(toStd(g));
  }
  return mergeGeometries(geos);
}

/* ---------- engraving decals ---------- */
function canvasTexture(cv, repeat) {
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  if (repeat) { tex.wrapS = THREE.RepeatWrapping; tex.repeat.set(repeat, 1); }
  return tex;
}

function textCanvas(text, ink, vertical) {
  const cv = document.createElement("canvas");
  cv.width = vertical ? 256 : 512;
  cv.height = vertical ? 256 : 128;
  const g = cv.getContext("2d");
  g.fillStyle = ink;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.font = `700 ${vertical ? 54 : 84}px "Kumbh Sans", Arial, sans-serif`;
  try { g.letterSpacing = vertical ? "8px" : "16px"; } catch { /* older browsers */ }
  g.translate(cv.width / 2, cv.height / 2);
  if (vertical) g.rotate(-Math.PI / 2);
  const maxW = vertical ? 232 : 470, wText = g.measureText(text).width;
  if (wText > maxW) g.scale(maxW / wText, maxW / wText);
  g.fillText(text, 0, 4);
  return cv;
}

// Rinfit infinity mark: two linked rounded squares at 45°.
function logoCanvas(ink, size = 256, line = 16) {
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  const g = cv.getContext("2d");
  const k = size / 256;
  g.strokeStyle = ink;
  g.lineWidth = line * k;
  g.translate(size / 2, size / 2);
  g.rotate(Math.PI / 4);
  for (const x of [-92, -12]) { g.beginPath(); g.roundRect(x * k, -40 * k, 104 * k, 80 * k, 26 * k); g.stroke(); }
  return cv;
}

function decal(cv, radius, height, arc, phi, y, { repeat, side = THREE.FrontSide } = {}) {
  const theta = Math.min(Math.PI * 2, arc / radius);
  const geo = new THREE.CylinderGeometry(radius, radius, height, Math.max(24, Math.ceil(theta * 40)), 1, true, phi - theta / 2, theta);
  geo.translate(0, y, 0);
  return new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    map: canvasTexture(cv, repeat), transparent: true, roughness: 0.75, metalness: 0, envMapIntensity: 0.25,
    depthWrite: false, polygonOffset: true, polygonOffsetFactor: -4, polygonOffsetUnits: -4, side
  }));
}

/* ---------- stones ---------- */
// Girdle outline, counter-clockwise, x across the finger and y along it.
function girdle(cut, w, l) {
  const hw = w / 2, hl = l / 2, pts = [], P = (x, y) => pts.push(new THREE.Vector2(x, y));
  if (cut === "emerald" || cut === "princess") {
    // long edges are split so the stone gets the fine criss-cross facets seen in the photos
    const c = Math.min(w, l) * (cut === "emerald" ? 0.17 : 0.04);
    const corners = [[-hw + c, -hl], [hw - c, -hl], [hw, -hl + c], [hw, hl - c], [hw - c, hl], [-hw + c, hl], [-hw, hl - c], [-hw, -hl + c]];
    corners.forEach(([x, y], i) => {
      const [nx, ny] = corners[(i + 1) % corners.length];
      const k = Math.hypot(nx - x, ny - y) > 1.5 ? 3 : 1;
      for (let s = 0; s < k; s++) P(x + ((nx - x) * s) / k, y + ((ny - y) * s) / k);
    });
  } else if (cut === "marquise") {
    const n = 18, xAt = (y) => hw * Math.pow(Math.max(0, 1 - (y / hl) ** 2), 0.8);
    for (let i = 0; i <= n; i++) { const y = -hl + (2 * hl * i) / n; P(xAt(y), y); }
    for (let i = n - 1; i > 0; i--) { const y = -hl + (2 * hl * i) / n; P(-xAt(y), y); }
  } else if (cut === "pear") {
    const r = hw, cy = -hl + r, n = 14, arcN = 8;
    const taper = (y) => r * Math.pow(Math.max(0, 1 - (y - cy) / (hl - cy)), 0.75);
    P(0, -hl);
    for (let i = 1; i <= arcN; i++) { const a = -Math.PI / 2 + (i / arcN) * (Math.PI / 2); P(r * Math.cos(a), cy + r * Math.sin(a)); }
    for (let i = 1; i < n; i++) { const y = cy + ((hl - cy) * i) / n; P(taper(y), y); }
    P(0, hl);
    for (let i = n - 1; i >= 1; i--) { const y = cy + ((hl - cy) * i) / n; P(-taper(y), y); }
    for (let i = arcN; i >= 1; i--) { const a = -Math.PI / 2 + (i / arcN) * (Math.PI / 2); P(-r * Math.cos(a), cy + r * Math.sin(a)); }
  } else {
    const n = 24;
    for (let i = 0; i < n; i++) { const a = (i / n) * Math.PI * 2; P(hw * Math.cos(a), hl * Math.sin(a)); }
  }
  return pts;
}

// Stack scaled copies of an outline into a faceted solid. levels go from bottom to top.
// A "half" level uses edge midpoints, which turns the band of facets into a zig-zag (star and kite facets).
function loft(base, levels, { top = true, bottom = true } = {}) {
  const n = base.length, pos = [];
  const mids = base.map((p, i) => p.clone().add(base[(i + 1) % n]).multiplyScalar(0.5));
  const rings = levels.map((lv) => (lv.half ? mids : base).map((p) => new THREE.Vector3(p.x * lv.sx, p.y * lv.sy, lv.z)));
  const tri = (a, b, c) => pos.push(a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z);
  const isPoint = (lv) => lv.sx === 0 && lv.sy === 0;
  for (let k = 0; k < rings.length - 1; k++) {
    const a = levels[k], b = levels[k + 1], A = rings[k], B = rings[k + 1];
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      if (isPoint(a)) tri(A[i], B[j], B[i]);
      else if (isPoint(b)) tri(A[i], A[j], B[j]);
      else if (!!a.half === !!b.half) { tri(A[i], A[j], B[j]); tri(A[i], B[j], B[i]); }
      else if (!a.half) { tri(A[i], A[j], B[i]); tri(A[j], B[j], B[i]); }
      else { tri(A[i], B[j], B[i]); tri(A[i], A[j], B[j]); }
    }
  }
  const cap = (ring, z, up) => {
    const c = new THREE.Vector3(0, 0, z);
    for (let i = 0; i < n; i++) { const j = (i + 1) % n; up ? tri(c, ring[i], ring[j]) : tri(c, ring[j], ring[i]); }
  };
  const L0 = levels[0], Lt = levels[levels.length - 1];
  if (bottom && !isPoint(L0)) cap(rings[0], L0.z, false);
  if (top && !isPoint(Lt)) cap(rings[rings.length - 1], Lt.z, true);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  return g;
}

// s = scale of the girdle, z = height as a share of the smaller stone dimension (0 = girdle)
const CUTS = {
  brilliant: [
    { s: 0, z: -0.43 }, { s: 0.42, z: -0.3, half: true }, { s: 0.78, z: -0.14 }, { s: 1, z: -0.012 },
    { s: 1, z: 0.012 }, { s: 0.88, z: 0.07, half: true }, { s: 0.6, z: 0.15 }
  ],
  // Rinfit's "emerald" stones are cut with criss-cross (radiant-style) facets
  step: [
    { s: 0, z: -0.42 }, { s: 0.45, z: -0.28, half: true }, { s: 0.8, z: -0.12 }, { s: 1, z: -0.012 },
    { s: 1, z: 0.012 }, { s: 0.88, z: 0.07, half: true }, { s: 0.72, z: 0.13 }
  ],
  princess: [
    { s: 0, z: -0.5 }, { s: 0.4, z: -0.34, half: true }, { s: 0.75, z: -0.16 }, { s: 1, z: -0.012 },
    { s: 1, z: 0.012 }, { s: 0.9, z: 0.06, half: true }, { s: 0.8, z: 0.1 }
  ]
};
const cutLevels = (cut) => (cut === "emerald" ? CUTS.step : cut === "princess" ? CUTS.princess : CUTS.brilliant);

function stoneGeometry(cut, w, l, pavilion = 1) {
  const m = Math.min(w, l);
  return loft(girdle(cut, w, l), cutLevels(cut).map((lv) => ({
    sx: lv.s, sy: lv.s, half: lv.half, z: (lv.z < 0 ? lv.z * pavilion : lv.z) * m
  })));
}

/* ---------- settings ---------- */
function prongPoints({ cut, w, l }) {
  const hw = w / 2, hl = l / 2, V = (x, y) => new THREE.Vector2(x, y);
  if (cut === "emerald" || cut === "princess") {
    const c = Math.min(w, l) * (cut === "emerald" ? 0.17 : 0.04) / 2;
    return [V(hw - c, hl - c), V(-hw + c, hl - c), V(-hw + c, -hl + c), V(hw - c, -hl + c)];
  }
  if (cut === "marquise") {
    const y = hl * 0.38, x = hw * Math.pow(1 - 0.38 ** 2, 0.8);
    return [V(0, hl), V(0, -hl), V(x, y), V(-x, y), V(x, -y), V(-x, -y)];
  }
  if (cut === "pear") {
    const r = hw, cy = -hl + r, y = cy - r * 0.55, x = Math.sqrt(r * r - (y - cy) ** 2);
    return [V(0, hl), V(x, y), V(-x, y)];
  }
  return [1, 3, 5, 7].map((k) => V(hw * Math.cos((k * Math.PI) / 4), hl * Math.sin((k * Math.PI) / 4)));
}

// Short claw from the band (or basket) up the side of the stone and over the girdle, with a rounded tip.
function prongParts(p, zg, crown, baseZ, radius, halfBand) {
  const len = Math.hypot(p.x, p.y) || 1, ux = p.x / len, uy = p.y / len;
  const r = Math.abs(p.x) < 0.01 ? radius * 1.2 : radius;          // tip claws of marquise and pear are heavier
  const clampY = (y) => Math.max(-halfBand, Math.min(halfBand, y));
  const pts = [
    new THREE.Vector3(p.x * 0.72, clampY(p.y * 0.72), baseZ),
    new THREE.Vector3(p.x * 0.97 + ux * 0.12, p.y * 0.97 + uy * 0.12, zg - Math.max(0.6, (zg - baseZ) * 0.45)),
    new THREE.Vector3(p.x + ux * r * 0.8, p.y + uy * r * 0.8, zg + crown * 0.1),
    new THREE.Vector3(p.x * 0.95 + ux * r * 0.25, p.y * 0.95 + uy * r * 0.25, zg + crown * 0.72)
  ];
  const tube = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 18, r, 10, false);
  const tip = new THREE.SphereGeometry(r * 1.25, 12, 10);
  tip.translate(pts[3].x, pts[3].y, pts[3].z);
  return [toStd(tube), toStd(tip)];
}

function railGeometry(cut, w, l, z, radius) {
  const pts = girdle(cut, w, l).map((p) => new THREE.Vector3(p.x, p.y, z));
  return toStd(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true, "centripetal"), pts.length * 4, radius, 6, true));
}

function stoneRing(ring, bandName, metalName) {
  const s = ring.spec, R = INNER_RADIUS, bw = s.band.width, t = s.band.thickness, Ro = R + t;
  const g = new THREE.Group();
  const hex = s.frosted ? "#eef2f3" : bandHex(ring, bandName);
  const bandM = s.frosted ? frostedMat() : siliconeMat(hex, "satin");
  const metal = metalMat(metalName);

  g.add(latheBand({ inner: R, thickness: t, width: bw, style: s.band.style }, bandM));
  if (s.engrave) {
    const h = Math.min(bw * 0.52, 2.6);
    g.add(decal(textCanvas("RINFIT", inkFor(hex), false), Ro + 0.02, h, h * 4, Math.PI / 2, 0));
  }

  // Stone height taken from photos: GlowStone stones sit close to the band, the Solitaire basket is taller.
  const m = Math.min(s.w, s.l), levels = cutLevels(s.cut);
  const crown = levels[levels.length - 1].z * m, depth = -levels[0].z * m;
  const zg = Ro + ({ basket: 2.9, high: 1.9, low: 1.25, halo: 1.9 }[s.mount] ?? 1.9);
  // the pavilion stops just above the band, so the band never shows through the stone
  const pavilion = Math.min(1, Math.max(0.2, (zg - Ro - 0.05) / depth));
  for (const mesh of gemMeshes(stoneGeometry(s.cut, s.w, s.l, pavilion), !!s.blackStone)) {
    mesh.position.z = zg;
    g.add(mesh);
  }

  const metalGeos = [];
  const radius = { basket: 0.6, high: 0.5, low: 0.55, halo: 0.4 }[s.mount];
  const baseZ = s.mount === "halo" ? zg - 0.9 : Ro - 0.2;
  const halfBand = s.mount === "halo" ? Infinity : bw / 2 - 0.35;
  for (const p of prongPoints(s)) metalGeos.push(...prongParts(p, zg, crown, baseZ, radius, halfBand));
  if (s.mount === "basket") {
    metalGeos.push(railGeometry(s.cut, s.w * 0.86, s.l * 0.86, zg - 0.9, 0.34));
    metalGeos.push(railGeometry(s.cut, s.w * 0.62, s.l * 0.62, zg - 2.1, 0.34));
  }
  if (s.mount === "high") metalGeos.push(railGeometry(s.cut, s.w * 0.84, s.l * 0.84, zg - 0.85, 0.3));
  if (s.mount === "low") metalGeos.push(railGeometry(s.cut, s.w * 0.86, s.l * 0.86, zg - 0.7, 0.3));

  if (s.mount === "halo") {
    const pad = 2.6;
    const shape = (w, l) => new THREE.Shape(girdle(s.cut, w, l));
    const plateShape = shape(s.w + pad, s.l + pad);
    plateShape.holes.push(new THREE.Path(girdle(s.cut, s.w - 0.6, s.l - 0.6)));
    const plate = new THREE.ExtrudeGeometry(plateShape, { depth: 0.6, bevelEnabled: false, curveSegments: 12 });
    plate.translate(0, 0, zg - 0.95);
    const rimShape = shape(s.w + pad + 0.5, s.l + pad + 0.5);
    rimShape.holes.push(new THREE.Path(girdle(s.cut, s.w + pad - 0.05, s.l + pad - 0.05)));
    const rim = new THREE.ExtrudeGeometry(rimShape, { depth: 0.95, bevelEnabled: true, bevelThickness: 0.08, bevelSize: 0.08, bevelSegments: 2 });
    rim.translate(0, 0, zg - 1.05);
    const base = girdle(s.cut, s.w, s.l);
    const bottomW = Math.min(s.w * 0.62, bw - 0.8), bottomL = Math.min(s.l * 0.62, bw - 0.8);
    const skirt = loft(base, [
      { sx: bottomW / s.w, sy: bottomL / s.l, z: Ro - 0.4 },
      { sx: (s.w + pad - 0.3) / s.w, sy: (s.l + pad - 0.3) / s.l, z: zg - 0.95 }
    ], { top: false, bottom: false });
    // the halo frame is polished and catches more light than the claws
    const haloMetal = metalMat(metalName);
    haloMetal.envMapIntensity = 2.6;
    haloMetal.color.offsetHSL(0, 0, 0.04);
    g.add(new THREE.Mesh(mergeGeometries([toStd(plate), toStd(rim), toStd(skirt)]), haloMetal));

    const path = new THREE.CatmullRomCurve3(girdle(s.cut, s.w + 1.55, s.l + 1.55).map((p) => new THREE.Vector3(p.x, p.y, 0)), true, "centripetal");
    const count = Math.floor(path.getLength() / 1.62);
    const small = stoneGeometry("round", 1.55, 1.55);
    const pave = path.getSpacedPoints(count).slice(0, count).map((p) => { const q = small.clone(); q.translate(p.x, p.y, zg - 0.05); return q; });
    g.add(...gemMeshes(mergeGeometries(pave), false, true));
  }
  g.add(new THREE.Mesh(mergeGeometries(metalGeos), metal));

  // extra bands in the set
  let yMin = -bw / 2, yMax = bw / 2;
  if (s.thin) {
    const tw = s.thin.width, y = -(bw / 2 + 0.3 + tw / 2);
    const thin = latheBand({ inner: R, thickness: t, width: tw }, bandM);
    thin.position.y = y;
    g.add(thin);
    yMin = y - tw / 2;
  }
  if (s.chevrons) {
    // both V bands point the same way, as in the product photo
    const cw = s.chevrons.width, A = s.chevrons.amplitude, off = bw / 2 + 0.25 + cw / 2, v = chevronY(A, 1.0);
    const yOf = (phi) => -v(phi);
    for (const sign of [1, -1]) {
      for (const geo of [sweptBand({ inner: R, thickness: t, width: cw }, yOf), studGeometry(R, t, yOf, 1.35, 0.75)]) {
        const mesh = new THREE.Mesh(geo, bandM);
        mesh.position.y = sign * off;
        g.add(mesh);
      }
    }
    yMin = -off - cw / 2 - A * 0.9;
    yMax = off + cw / 2;
  }
  const shift = -(yMin + yMax) / 2;   // centre the band stack on the finger
  for (const c of g.children) c.position.y += shift;
  return { group: g, bandLength: yMax - yMin };
}

function plainBand(ring, colorName) {
  const s = ring.spec, R = INNER_RADIUS, hex = bandHex(ring, colorName), Ro = R + s.thickness;
  const g = new THREE.Group();
  const mat = siliconeMat(hex, s.finish);
  g.add(latheBand({ inner: R, thickness: s.thickness, width: s.width, style: s.style, innerStep: s.innerStep }, mat));
  const ink = inkFor(hex);
  if (s.logo) {
    // on the raised part of the band: logo on one side of the front, RINFIT on the other
    const y = (-s.width / 2 + 2.6 + s.width / 2) / 2;
    g.add(decal(logoCanvas(ink), Ro + 0.02, 6.0, 6.0, -0.5, y));
    g.add(decal(textCanvas("RINFIT", ink, true), Ro + 0.02, 6.2, 6.2, 0.45, y));
  }
  if (s.engrave) g.add(decal(textCanvas("RINFIT", ink, true), Ro + 0.02, 5.2, 5.2, 0.7, 0));
  if (s.innerStep) {
    g.add(decal(logoCanvas(ink, 128, 12), R + 0.33, s.width - 4, 2 * Math.PI * (R + 0.33), 0, 0, { repeat: 16, side: THREE.BackSide }));
  }
  return { group: g, bandLength: s.width };
}

function chevronRing(ring, colorName) {
  const s = ring.spec, R = INNER_RADIUS, hex = bandHex(ring, colorName), yOf = chevronY(s.amplitude, 1.1, true);
  const mat = siliconeMat(hex, "satin");
  const g = new THREE.Group();
  g.add(new THREE.Mesh(sweptBand({ inner: R, thickness: s.thickness, width: s.width }, yOf), mat));
  g.add(new THREE.Mesh(studGeometry(R, s.thickness, yOf, 1.5, 0.92), mat));
  const h = Math.min(s.width * 0.62, 1.6);
  g.add(decal(textCanvas("RINFIT", inkFor(hex), false), R + s.thickness + 0.25, h, h * 4, 1.9, 0));
  for (const c of g.children) c.position.y -= s.amplitude * 0.2;
  return { group: g, bandLength: s.width + s.amplitude * 0.3 };
}

// Returns { group, bandLength, second? }. "second" is the other ring of a set, worn on a neighbouring finger.
export function createRing(ring, colorName) {
  const { bands, metals } = parseColor(colorName);
  const s = ring.spec;
  if (s.kind === "band") return plainBand(ring, bands[0]);
  if (s.kind === "chevron") return chevronRing(ring, bands[0]);
  const main = stoneRing(ring, bands[0], metals[0]);
  if (s.pair === "separate") main.second = stoneRing(ring, bands[1] ?? bands[0], metals[1] ?? metals[0]);
  return main;
}
