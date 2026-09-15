// Procedural 3D rings. Units = millimetres.
// Local frame: hole axis = +Y (along the finger), stone faces +Z (back of the hand).
import * as THREE from "three";
import { SILICONE, METAL, parseColor } from "./catalog.js";

export const INNER_RADIUS = 8.65; // US size 7

function siliconeMat(colorName) {
  if (colorName === "Frosted Clear") {
    return new THREE.MeshPhysicalMaterial({
      color: "#eef3f4", roughness: 0.5, metalness: 0, transmission: 0.55, thickness: 2,
      ior: 1.41, transparent: true, opacity: 0.92, side: THREE.DoubleSide
    });
  }
  return new THREE.MeshPhysicalMaterial({
    color: SILICONE[colorName] || "#cccccc", roughness: 0.46, metalness: 0,
    sheen: 0.7, sheenRoughness: 0.55, sheenColor: new THREE.Color("#ffffff"),
    clearcoat: 0.22, clearcoatRoughness: 0.4, side: THREE.DoubleSide
  });
}
const metalMat = (name) => new THREE.MeshStandardMaterial({
  color: METAL[name] || METAL.Silver, metalness: 1, roughness: 0.28, envMapIntensity: 1.9
});
// Mirror-like facets read as a cut stone without needing real refraction.
const stoneMat = (black) => new THREE.MeshPhysicalMaterial({
  color: black ? "#15151a" : "#eef3f9", metalness: black ? 0.35 : 0.92, roughness: 0.03,
  clearcoat: 1, clearcoatRoughness: 0, iridescence: black ? 0.15 : 0.65, iridescenceIOR: 2.0,
  iridescenceThicknessRange: [200, 600], envMapIntensity: black ? 2.4 : 2.6, flatShading: true
});

// Rounded-rectangle cross-section revolved around Y.
function bandGeometry(inner, thickness, width, grooves = 0) {
  const r = Math.min(thickness, width) * 0.45;
  const x0 = inner, x1 = inner + thickness, y0 = -width / 2, y1 = width / 2;
  const pts = [];
  const arc = (cx, cy, a0, a1, n = 7) => {
    for (let i = 0; i <= n; i++) {
      const a = a0 + (a1 - a0) * i / n;
      pts.push(new THREE.Vector2(cx + Math.cos(a) * r, cy + Math.sin(a) * r));
    }
  };
  arc(x0 + r, y0 + r, Math.PI, 1.5 * Math.PI);
  arc(x1 - r, y0 + r, 1.5 * Math.PI, 2 * Math.PI);
  if (grooves) {
    for (const s of [-0.26, 0.26]) {
      const y = s * width;
      pts.push(new THREE.Vector2(x1, y - 0.45), new THREE.Vector2(x1 - 0.4, y - 0.2),
               new THREE.Vector2(x1 - 0.4, y + 0.2), new THREE.Vector2(x1, y + 0.45));
    }
  }
  arc(x1 - r, y1 - r, 0, 0.5 * Math.PI);
  arc(x0 + r, y1 - r, 0.5 * Math.PI, Math.PI);
  pts.push(pts[0].clone());
  const g = new THREE.LatheGeometry(pts, 128);
  g.computeVertexNormals();
  return g;
}

// 2D outline of a stone in the XY plane (x across the finger, y along it).
function outline(cut, w, l) {
  const s = new THREE.Shape();
  const hw = w / 2, hl = l / 2;
  if (cut === "emerald" || cut === "princess") {
    const c = Math.min(w, l) * (cut === "emerald" ? 0.2 : 0.06);
    s.moveTo(-hw + c, -hl); s.lineTo(hw - c, -hl); s.lineTo(hw, -hl + c); s.lineTo(hw, hl - c);
    s.lineTo(hw - c, hl); s.lineTo(-hw + c, hl); s.lineTo(-hw, hl - c); s.lineTo(-hw, -hl + c);
    s.closePath();
  } else if (cut === "marquise") {
    const n = 24;
    for (let i = 0; i <= n; i++) {
      const t = i / n, y = -hl + l * t, x = hw * Math.pow(Math.sin(Math.PI * t), 0.8);
      i ? s.lineTo(x, y) : s.moveTo(x, y);
    }
    for (let i = n - 1; i > 0; i--) {
      const t = i / n; s.lineTo(-hw * Math.pow(Math.sin(Math.PI * t), 0.8), -hl + l * t);
    }
    s.closePath();
  } else if (cut === "pear") {
    const rad = hw, cy = -hl + rad, n = 28, right = [];
    for (let i = 0; i <= n; i++) {
      const y = -hl + l * i / n;
      const x = y <= cy ? Math.sqrt(Math.max(0, rad * rad - (y - cy) ** 2))
                        : rad * Math.pow(1 - (y - cy) / (hl - cy), 0.75);
      right.push([x, y]);
    }
    s.moveTo(0, -hl);
    right.forEach(([x, y]) => s.lineTo(x, y));
    right.slice().reverse().forEach(([x, y]) => s.lineTo(-x, y));
    s.closePath();
  } else {
    s.absellipse(0, 0, hw, hl, 0, Math.PI * 2, false, 0);
  }
  return s;
}

function stoneGeometry(cut, w, l) {
  if (cut === "round" || cut === "oval") {
    const p = [[0, -0.43], [0.5, -0.02], [0.5, 0.02], [0.3, 0.17], [0, 0.17]]
      .map(([x, y]) => new THREE.Vector2(x, y));
    const g = new THREE.LatheGeometry(p, 16);
    g.rotateX(Math.PI / 2);
    g.scale(w, l, (w + l) / 2);
    return g;
  }
  // Two bevel steps give a step-cut look; outline is shrunk so the bevel keeps the real size.
  const m = Math.min(w, l), bev = m * 0.12, h = m * 0.1;
  const g = new THREE.ExtrudeGeometry(outline(cut, w - bev * 2, l - bev * 2), {
    depth: h, bevelEnabled: true, bevelThickness: m * 0.13, bevelSize: bev,
    bevelSegments: 2, curveSegments: 18
  });
  return g;
}

function bezelGeometry(cut, w, l, wall, depth) {
  const outer = outline(cut, w + wall * 2, l + wall * 2);
  outer.holes.push(outline(cut, w - 0.2, l - 0.2));
  return new THREE.ExtrudeGeometry(outer, { depth, bevelEnabled: true, bevelThickness: 0.15, bevelSize: 0.15, bevelSegments: 2, curveSegments: 24 });
}

function stoneRing(shape, colorName) {
  const { band, metal } = parseColor(colorName);
  const g = new THREE.Group();
  const R = INNER_RADIUS, t = shape.thickness;
  g.add(new THREE.Mesh(bandGeometry(R, t, shape.width), siliconeMat(shape.frosted ? "Frosted Clear" : band)));

  const top = R + t - 0.4;
  const metalM = metalMat(metal || "Silver");
  const m = Math.min(shape.w, shape.l);
  // basket: widens from the band up to the stone
  const seat = new THREE.Mesh(new THREE.CylinderGeometry(m * 0.42, m * 0.22, 1.9, 24), metalM);
  seat.rotation.x = Math.PI / 2; seat.position.z = top + 0.9;
  g.add(seat);

  const holder = new THREE.Group();
  holder.position.z = top + 1.7;
  const bezel = new THREE.Mesh(bezelGeometry(shape.cut, shape.w, shape.l, 0.4, 0.7), metalM);
  holder.add(bezel);
  const stone = new THREE.Mesh(stoneGeometry(shape.cut, shape.w, shape.l), stoneMat(shape.blackStone));
  stone.position.z = shape.cut === "round" || shape.cut === "oval" ? 0.95 : 0.55;
  holder.add(stone);

  if (shape.halo) {
    // flat metal plate with a thin outer rim and a row of small round stones set flush
    const pad = 3.2;
    const plate = new THREE.Mesh(new THREE.ExtrudeGeometry(outline(shape.cut, shape.w + pad, shape.l + pad),
      { depth: 0.35, bevelEnabled: false, curveSegments: 24 }), metalM);
    holder.add(plate);
    holder.add(new THREE.Mesh(bezelGeometry(shape.cut, shape.w + pad - 0.5, shape.l + pad - 0.5, 0.25, 0.75), metalM));
    const path = outline(shape.cut, shape.w + pad / 2 + 0.4, shape.l + pad / 2 + 0.4);
    const n = Math.round(path.getLength() / 1.3);
    const gemGeo = stoneGeometry("round", 1.15, 1.15), sm = stoneMat(false);
    path.getSpacedPoints(n).slice(0, n).forEach((p) => {
      const gem = new THREE.Mesh(gemGeo, sm);
      gem.position.set(p.x, p.y, 0.75);
      holder.add(gem);
    });
  }
  g.add(holder);
  return g;
}

// Returns { group, length } where length = axial extent in mm.
export function createRing(ring, colorName) {
  const s = ring.shape;
  const group = new THREE.Group();
  const gap = 0.35;

  if (s.type === "band") {
    group.add(new THREE.Mesh(bandGeometry(INNER_RADIUS, s.thickness, s.width, s.grooves), siliconeMat(colorName)));
    return { group, length: s.width };
  }
  if (s.type === "stack") {
    const total = s.count * s.width + (s.count - 1) * gap;
    for (let i = 0; i < s.count; i++) {
      const m = new THREE.Mesh(bandGeometry(INNER_RADIUS, s.thickness, s.width), siliconeMat(colorName));
      m.position.y = -total / 2 + s.width / 2 + i * (s.width + gap);
      group.add(m);
    }
    return { group, length: total };
  }
  // stone ring, optionally with a plain stacking band next to it
  const main = stoneRing(s, colorName);
  group.add(main);
  let length = Math.max(s.width, s.l * 0.6);
  if (s.stackBand) {
    const { band } = parseColor(colorName);
    const extra = new THREE.Mesh(bandGeometry(INNER_RADIUS, s.thickness, s.width), siliconeMat(band));
    const off = s.l / 2 + s.width / 2 + 0.9;
    extra.position.y = -off;
    main.position.y = off / 2; extra.position.y = -off / 2;
    group.add(extra);
    length = off + s.width;
  }
  return { group, length };
}
