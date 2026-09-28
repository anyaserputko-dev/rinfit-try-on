/* fit.js — how wide the finger really looks in the picture.

   Hand landmarks say where the finger is, not how wide it is: the tracker normalises every hand to an average
   one, so a slim finger and a broad one get the same width, and the shopper used to fix that with a -/+ knob.
   This reads the width off the pixels instead, in a way the two earlier attempts did not:
     - the colour test is on chroma (Cb/Cr), which barely changes in the shading near the edge of the finger,
       where a plain skin-colour walk stopped early;
     - the walk out from the middle only trusts a change that holds for several pixels in a row, so the shadow
       line between two fingers does not count as an edge;
     - the neighbouring fingers bound the search, so it can never latch onto the next finger;
     - five cuts across the finger have to agree, or the reading is thrown away and the anatomy estimate is kept.
   Everything is in source-image pixels; the caller converts. `?edges=1` draws the cuts it found. */

const CUTS = [0.32, 0.4, 0.48, 0.56, 0.64];     // where across the knuckle–joint segment the width is read
const REACH = 1.7;                             // how far out from the middle to look, in expected widths
const HOLD = 3;                                // pixels in a row that must read as "not this finger"

// [MCP, PIP] of each finger and who sits either side of it (null = open side: thumb or outer edge)
const AXES = { index: [5, 6], middle: [9, 10], ring: [13, 14], pinky: [17, 18] };
const SIDES = { index: [null, "middle"], middle: ["index", "ring"], ring: ["middle", "pinky"], pinky: ["ring", null] };

function median(a) {
  const s = [...a].sort((x, y) => x - y);
  const h = s.length >> 1;
  return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2;
}

function ycc(r, g, b) {
  return [0.299 * r + 0.587 * g + 0.114 * b, 128 - 0.1687 * r - 0.3313 * g + 0.5 * b, 128 + 0.5 * r - 0.4187 * g - 0.0813 * b];
}

/**
 * @param src   video or image element (the raw frame; nothing mirrored)
 * @param lms   normalised hand landmarks, as MediaPipe gives them
 * @param W,H   source size in pixels
 * @param finger  "index" | "middle" | "ring" | "pinky"
 * @param prior   expected finger width from the landmarks, in source pixels
 * @param probe   a reusable 2D canvas
 * @returns {null | {width, ratio, edges: [[x,y],...], cuts, assumed}}
 */
export function measureFingerWidth(src, lms, W, H, finger, prior, probe) {
  if (!prior || prior < 12) return null;   // a finger a few pixels wide has no edges to read
  const [ia, ib] = AXES[finger];
  const px = (i) => ({ x: lms[i].x * W, y: lms[i].y * H });
  const A = px(ia), B = px(ib);
  const ux = B.x - A.x, uy = B.y - A.y, len = Math.hypot(ux, uy) || 1;
  const u = { x: ux / len, y: uy / len }, n = { x: -u.y, y: u.x };   // n: across the finger

  // where the next finger's axis lies on each side, so the search never crosses into it
  const bound = [null, null];
  SIDES[finger].forEach((g, k) => {
    if (!g) return;
    const [ga, gb] = AXES[g];
    const Ga = px(ga), Gb = px(gb);
    const gx = Gb.x - Ga.x, gy = Gb.y - Ga.y, gl = Math.hypot(gx, gy) || 1;
    const vx = gx / gl, vy = gy / gl;
    // a neighbour only bounds the search while it lies alongside ours: a finger curled under the knuckle
    // points elsewhere, and its skin next to ours is then just skin the walk has to cross
    if (u.x * vx + u.y * vy < 0.75) return;
    const denom = n.x * vy - n.y * vx;                              // n × v
    const C = { x: A.x + ux * 0.48, y: A.y + uy * 0.48 };
    if (Math.abs(denom) < 0.2) return;
    const d = ((Ga.x - C.x) * vy - (Ga.y - C.y) * vx) / denom;      // signed distance along n to that axis
    if (Math.abs(d) < prior * 0.6) return;                          // on top of ours: not a usable bound
    bound[k] = Math.abs(d);
    bound[k === 0 ? "sign0" : "sign1"] = Math.sign(d);
  });
  // side 0 of the walk is the -n direction. If the neighbour we called "side 0" actually lies at +n, swap.
  let bLeft = bound[0], bRight = bound[1];
  if (bound.sign0 > 0 || bound.sign1 < 0) [bLeft, bRight] = [bRight, bLeft];
  const reach = (b) => (b ? Math.min(prior * REACH, b * 0.62) : prior * REACH);
  const reachL = reach(bLeft), reachR = reach(bRight);

  // crop the strip we need at a sensible resolution
  const pts = [];
  for (const t of CUTS) {
    const P = { x: A.x + ux * t, y: A.y + uy * t };
    pts.push({ x: P.x - n.x * reachL, y: P.y - n.y * reachL }, { x: P.x + n.x * reachR, y: P.y + n.y * reachR });
  }
  const pad = 3;
  const x0 = Math.max(0, Math.floor(Math.min(...pts.map((p) => p.x)) - pad));
  const y0 = Math.max(0, Math.floor(Math.min(...pts.map((p) => p.y)) - pad));
  const x1 = Math.min(W, Math.ceil(Math.max(...pts.map((p) => p.x)) + pad));
  const y1 = Math.min(H, Math.ceil(Math.max(...pts.map((p) => p.y)) + pad));
  const bw = x1 - x0, bh = y1 - y0;
  if (bw < 4 || bh < 4) return null;
  const s = Math.min(1, 180 / Math.max(bw, bh));                   // never more than ~180 px across
  const cw = Math.max(2, Math.round(bw * s)), ch = Math.max(2, Math.round(bh * s));
  const c = probe.canvas, g = probe.ctx;
  if (c.width !== cw || c.height !== ch) { c.width = cw; c.height = ch; }
  try { g.drawImage(src, x0, y0, bw, bh, 0, 0, cw, ch); } catch { return null; }
  let data;
  try { data = g.getImageData(0, 0, cw, ch).data; } catch { return null; }   // tainted canvas: cross-origin photo
  const at = (x, y) => {                                            // source px -> Y, Cb, Cr (nearest)
    const cx = Math.min(cw - 1, Math.max(0, Math.round((x - x0) * s)));
    const cy = Math.min(ch - 1, Math.max(0, Math.round((y - y0) * s)));
    const i = (cy * cw + cx) * 4;
    return ycc(data[i], data[i + 1], data[i + 2]);
  };

  // sample every cut, one source pixel apart (or one crop pixel when the crop was shrunk)
  const step = 1 / s;
  const lines = CUTS.map((t) => {
    const P = { x: A.x + ux * t, y: A.y + uy * t };
    const side = (dir, reach) => {
      const out = [];
      for (let d = 0; d <= reach; d += step) out.push({ d, c: at(P.x + n.x * d * dir, P.y + n.y * d * dir) });
      return out;
    };
    return { P, L: side(-1, reachL), R: side(1, reachR) };
  });

  // reference colour: the middle of the finger on every cut
  const core = [];
  for (const l of lines) for (const arr of [l.L, l.R]) for (const p of arr) if (p.d <= prior * 0.28) core.push(p.c);
  if (core.length < 6) return null;
  const Y0 = median(core.map((c) => c[0])), Cb0 = median(core.map((c) => c[1])), Cr0 = median(core.map((c) => c[2]));
  const spread = median(core.map((c) => Math.hypot(c[1] - Cb0, c[2] - Cr0)));
  const sigma = Math.max(2.5, spread * 1.6);                        // camera noise on the chroma, at least a little
  const isSkin = (c) => Math.hypot(c[1] - Cb0, c[2] - Cr0) < sigma * 3.2 && Math.abs(c[0] - Y0) < 0.55 * Y0 + 28;

  // Two ways to see the edge of the finger, and the nearer of the two wins:
  //  - colour: walk out until the picture stops being this finger's colour for HOLD pixels in a row (snapped
  //    to the sharpest brightness step next to that spot). Fails on skin over skin and on grey photos;
  //  - shading: the first clear brightness step out from the middle — a finger always has a shadow line
  //    along its side, on a face or a palm behind it as much as on a wall. Skin texture is far weaker than
  //    that line, so the step has to be a local peak well above the ripple inside the finger.
  const gradAt = (arr, i) => (i > 0 && i < arr.length - 1 ? Math.abs(arr[i + 1].c[0] - arr[i - 1].c[0]) / 2 : 0);
  const edge = (arr) => {
    let colour = null, run = 0;
    for (let i = 0; i < arr.length; i++) {
      run = isSkin(arr[i].c) ? 0 : run + 1;
      if (run >= HOLD) {
        let k = i - HOLD + 1, best = 0, bestK = k;
        for (let j = Math.max(1, k - 3); j <= Math.min(arr.length - 1, k + 3); j++) {
          const gr = Math.abs(arr[j].c[0] - arr[j - 1].c[0]);
          if (gr > best) { best = gr; bestK = j; }
        }
        colour = best > 6 ? arr[bestK].d - step / 2 : arr[k].d;
        break;
      }
    }
    // ripple: how much the brightness wobbles inside the finger, from the inner quarter of the walk
    const inner = Math.max(3, Math.floor((prior * 0.25) / step));
    let ripple = 0;
    for (let i = 1; i < inner && i < arr.length - 1; i++) ripple = Math.max(ripple, gradAt(arr, i));
    const need = Math.max(7, ripple * 2.2);
    let shade = null;
    for (let i = inner; i < arr.length - 1; i++) {
      const g = gradAt(arr, i);
      if (g >= need && g >= gradAt(arr, i - 1) && g >= gradAt(arr, i + 1)) { shade = arr[i].d; break; }
    }
    if (colour === null) return shade === null ? null : { d: shade, how: "shade" };
    if (shade === null) return { d: colour, how: "colour" };
    return shade < colour ? { d: shade, how: "shade" } : { d: colour, how: "colour" };
  };

  const widths = [], edges = [], hows = {};
  let assumed = 0, seen = 0;
  lines.forEach((l, i) => {
    const rL = edge(l.L), rR = edge(l.R);
    let eL = rL ? rL.d : null, eR = rR ? rR.d : null;
    for (const r of [rL, rR]) if (r) hows[r.how] = (hows[r.how] || 0) + 1;
    seen += (eL !== null) + (eR !== null);
    // no edge before the next finger: the two are touching, so the edge is halfway between their axes
    if (eL === null && bLeft) { eL = bLeft * 0.5; assumed++; }
    if (eR === null && bRight) { eR = bRight * 0.5; assumed++; }
    if (eL === null || eR === null) return;
    widths.push(eL + eR);
    edges.push([l.P.x - n.x * eL, l.P.y - n.y * eL], [l.P.x + n.x * eR, l.P.y + n.y * eR]);
  });
  if (widths.length < 3 || seen < 3) return null;                   // mostly assumptions: nothing new was read
  const width = median(widths);
  const mad = median(widths.map((w) => Math.abs(w - width)));
  if (mad > width * 0.14) return null;                              // the cuts disagree: nothing to trust
  return { width, ratio: width / prior, edges, cuts: widths.length, assumed, how: hows };
}

/* What the shopper should do with the hand, judged from the landmarks in stage pixels (y up).
   Returns "ok" or a reason, in the order they should be fixed. */
export function handPose(pts, stageH) {
  const wrist = pts[0], mid = pts[9];
  const dx = mid.x - wrist.x, dy = mid.y - wrist.y;
  const l = Math.hypot(dx, dy) || 1;
  const up = dy / l;                                                // 1 = fingers straight up, -1 = down
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  const size = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
  return { up, size, sizeFrac: size / Math.max(stageH, 1) };
}
