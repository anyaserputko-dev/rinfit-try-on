"""Silhouette camera fit (emerald / halo / princess helper, numpy only).

  python3 blender/rings/_rect_silfit.py <config.json>

Projects densely sampled surfaces of the bands, the stone (and halo frame) with a perspective camera and maximises
the IoU between that mask and the photo's object mask (photo pixels darker than the white ground), plus optional
point constraints. Free: camera (az, el, roll, dist, scale, shift) and optionally dz (stone/setting height offset)
and k (ring inner-radius scale, to detect a CAD ring size different from US 7).

config: {"photo": path, "start": cam.json from _rect_fitcam, "free": ["dz", "k"],
         "bands": [{"width":3, "thickness":2, "dome":0.35, "y":0}],
         "stone": {"w":8, "l":10, "corner":0.7, "girdle_z":15.2, "crown":1.12, "pav":4.0, "table":0.56},
         "halo": {"a":4.56, "b":5.56, "rho":2.17, "hw":0.6, "z0":13.9, "z1":14.9, "zb":10.06, "ba":3.6, "bb":2.4},
         "pts": [[x,y,z,u,v,"stone"|"band"], ...], "cell": 6}
Writes <config>_sil_cam.json (same keys as _rect_fitcam) and <config>_sil_masks.png (red = photo only,
green = model only, white = both).
"""
import json, math, sys
import numpy as np
from PIL import Image

R_IN = 17.32 / 2


def basis(az, el, roll):
    D = np.array([math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)])
    fwd = -D
    up0 = np.array([0.0, 0.0, 1.0]) if abs(D[2]) < 0.999 else np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, up0)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    c, s = math.cos(roll), math.sin(roll)
    return D, fwd, c * right + s * up, -s * right + c * up


def from_cam(cam):
    D = np.array(cam["direction"], float)
    D /= np.linalg.norm(D)
    el = math.asin(max(-1, min(1, D[2])))
    az = math.atan2(D[0], -D[1])
    _, fwd, r0, u0 = basis(az, el, 0.0)
    u = np.array(cam["up"], float)
    return [az, el, math.atan2(-(u @ r0), u @ u0), cam["dist"], math.log(abs(cam["sc"])), cam["tx"], cam["ty"]], \
        np.sign(cam["sc"])


def rect_outline(w, l, c, n=240):
    hw, hl = w / 2, l / 2
    poly = np.array([(hw, -hl + c), (hw, hl - c), (hw - c, hl), (-hw + c, hl), (-hw, hl - c), (-hw, -hl + c),
                     (-hw + c, -hl), (hw - c, -hl)])
    seg = np.linalg.norm(np.roll(poly, -1, 0) - poly, axis=1)
    t = np.linspace(0, seg.sum(), n, endpoint=False)
    cum = np.concatenate([[0], np.cumsum(seg)])
    out = []
    for tt in t:
        i = min(np.searchsorted(cum, tt, side="right") - 1, 7)
        f = (tt - cum[i]) / seg[i]
        out.append(poly[i] + (poly[(i + 1) % 8] - poly[i]) * f)
    return np.array(out)


def rrect_outline(a, b, rho, n=300):
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    # superellipse-free rounded rectangle: clamp a circle of radius rho moved to the corners
    cx, cy = np.cos(t), np.sin(t)
    x = np.sign(cx) * (a - rho) + rho * cx
    y = np.sign(cy) * (b - rho) + rho * cy
    return np.stack([x, y], 1)


def sample(cfg, dz, k):
    pts = []
    rin = R_IN * k
    for bd in cfg.get("bands", []):
        b = bd["width"] / 2
        t = bd.get("thickness", 2.0)
        dome = bd.get("dome", 0.3)
        phi = np.linspace(0, 2 * math.pi, 1100, endpoint=False)
        ys = np.linspace(-b, b, 36)
        P, Y = np.meshgrid(phi, ys)
        ro = rin + t - dome * (np.abs(Y) / b) ** 2
        for R in (ro, np.full_like(ro, rin)):
            pts.append(np.stack([R * np.sin(P), Y + bd.get("y", 0), R * np.cos(P)], -1).reshape(-1, 3))
        for side in (-b, b):
            rr = np.linspace(rin, rin + t - dome, 8)
            P2, R2 = np.meshgrid(phi, rr)
            pts.append(np.stack([R2 * np.sin(P2), np.full_like(P2, side + bd.get("y", 0)), R2 * np.cos(P2)], -1).reshape(-1, 3))
    st = cfg.get("stone")
    if st:
        o = rect_outline(st["w"], st["l"], st["corner"])
        zg = st["girdle_z"] + dz
        tab = st.get("table", 0.56)
        for s in np.linspace(tab, 1, 10):
            z = zg + st["crown"] * (1 - s) / (1 - tab)
            pts.append(np.column_stack([o * s, np.full(len(o), z)]))
        for s in np.linspace(0, tab, 10):
            pts.append(np.column_stack([o * s, np.full(len(o), zg + st["crown"])]))
        for s in np.linspace(0.05, 1, 14):
            pts.append(np.column_stack([o * s, np.full(len(o), zg - st["pav"] * (1 - s))]))
    h = cfg.get("halo")
    if h:
        for off in np.linspace(-h["hw"], h["hw"], 6):
            o = rrect_outline(h["a"] + off, h["b"] + off, max(0.2, h["rho"] + off))
            pts.append(np.column_stack([o, np.full(len(o), h["z1"] + dz)]))
        o = rrect_outline(h["a"] + h["hw"], h["b"] + h["hw"], h["rho"] + h["hw"])
        for z in np.linspace(h["z0"], h["z1"], 5):
            pts.append(np.column_stack([o, np.full(len(o), z + dz)]))
        ob = o * np.array([h["ba"] / (h["a"] + h["hw"]), h["bb"] / (h["b"] + h["hw"])])
        for f in np.linspace(0, 1, 10):
            pts.append(np.column_stack([o * (1 - f) + ob * f, np.full(len(o), (h["z0"] + dz) * (1 - f) + h["zb"] * f)]))
    return np.concatenate(pts)


def project(p, sgn, P, T):
    az, el, roll, dist, lsc, tx, ty = p[:7]
    D, fwd, r, u = basis(az, el, roll)
    q = P - (T + D * dist)
    z = q @ fwd
    sc = sgn * math.exp(lsc)
    return sc * (q @ r) / z + tx, -sc * (q @ u) / z + ty


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def erode(m, r):
    return ~dilate(~m, r)


def main():
    cfg_path = sys.argv[1]
    cfg = json.load(open(cfg_path))
    cell = cfg.get("cell", 6)
    img = np.asarray(Image.open(cfg["photo"]).convert("L")).astype(float)
    H, W = img.shape
    gh, gw = H // cell, W // cell
    dark = (img[:gh * cell, :gw * cell] < cfg.get("thresh", 246)).reshape(gh, cell, gw, cell).mean((1, 3)) > 0.3
    photo = erode(dilate(dark, 2), 2)
    cam = json.load(open(cfg["start"]))
    p0, sgn = from_cam(cam)
    T = np.array(cam["target"], float)
    free = cfg.get("free", ["dz", "k"])
    p0 = np.array(p0 + [0.0, 1.0])
    upts = cfg.get("pts", [])
    lam = cfg.get("point_weight", 30.0)

    def model_mask(p):
        P = sample(cfg, p[7], p[8])
        u, v = project(p, sgn, P, T)
        ok = (u >= 0) & (u < gw * cell) & (v >= 0) & (v < gh * cell)
        m = np.zeros((gh, gw), bool)
        m[(v[ok] // cell).astype(int), (u[ok] // cell).astype(int)] = True
        return erode(dilate(m, 2), 1)

    def cost(p):
        if p[3] < 20:
            return 10.0
        m = model_mask(p)
        iou = (m & photo).sum() / max(1, (m | photo).sum())
        c = 1 - iou
        if upts:
            e = 0
            for x, y, z, uu, vv, kind in upts:
                zz = z + (p[7] if kind == "stone" else 0)
                if kind == "band":
                    rr = math.hypot(x, z)
                    s = (R_IN * p[8] + (rr - R_IN)) / rr
                    x, zz = x * s, z * s
                a, b = project(p, sgn, np.array([[x, y, zz]]), T)
                e += ((a[0] - uu) ** 2 + (b[0] - vv) ** 2) / (W * W)
            c += lam * e / len(upts)
        return c

    active = [0, 1, 2, 3, 4, 5, 6] + ([7] if "dz" in free else []) + ([8] if "k" in free else [])
    steps = np.array([0.06, 0.06, 0.06, 12.0, 0.05, 25.0, 25.0, 0.8, 0.06])

    def nm(p, it=900):
        idx = active
        n = len(idx)
        simplex = [p.copy()]
        for i in idx:
            q = p.copy()
            q[i] += steps[i]
            simplex.append(q)
        vals = [cost(s) for s in simplex]
        for _ in range(it):
            order = np.argsort(vals)
            simplex = [simplex[i] for i in order]
            vals = [vals[i] for i in order]
            cen = np.mean(simplex[:-1], 0)
            xr = cen + (cen - simplex[-1])
            fr = cost(xr)
            if fr < vals[0]:
                xe = cen + 2 * (cen - simplex[-1])
                fe = cost(xe)
                simplex[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
            elif fr < vals[-2]:
                simplex[-1], vals[-1] = xr, fr
            else:
                xc = cen + 0.5 * (simplex[-1] - cen)
                fc = cost(xc)
                if fc < vals[-1]:
                    simplex[-1], vals[-1] = xc, fc
                else:
                    for i in range(1, len(simplex)):
                        simplex[i] = simplex[0] + 0.5 * (simplex[i] - simplex[0])
                        vals[i] = cost(simplex[i])
            if abs(vals[-1] - vals[0]) < 1e-6 and _ > 200:
                break
        i = int(np.argmin(vals))
        return simplex[i], vals[i]

    print("start cost %.4f" % cost(p0))
    best = nm(p0)
    for _ in range(2):      # restarts shake the simplex out of flat spots
        best = min([best, nm(best[0], 600)], key=lambda t: t[1])
    p, c = best
    m = model_mask(p)
    iou = (m & photo).sum() / max(1, (m | photo).sum())
    az, el, roll, dist, lsc, tx, ty, dz, k = p
    D, fwd, r, u = basis(az, el, roll)
    sc = sgn * math.exp(lsc)
    print("IoU %.4f cost %.4f  dz %.2f mm  k %.3f (inner diameter %.2f mm)" % (iou, c, dz, k, 2 * R_IN * k))
    print("CAM = dict(direction=(%.4f, %.4f, %.4f), up=(%.4f, %.4f, %.4f), target=(%.2f, %.2f, %.2f), dist=%.1f)"
          % (*D, *u, *T, dist))
    far = max(max(abs(tx), abs(W - tx)), max(abs(ty), abs(H - ty)))
    print("lens_cover %.1f" % (18 * abs(sc) / far))
    out = cfg_path.replace(".json", "_sil_cam.json")
    json.dump(dict(direction=list(D), up=list(u), target=list(T), dist=dist, sc=sc, tx=tx, ty=ty, dz=dz, k=k,
                   iou=iou, lens_cover=18 * abs(sc) / far), open(out, "w"), indent=1)
    vis = np.zeros((gh, gw, 3), np.uint8)
    vis[photo & ~m] = (230, 40, 40)
    vis[m & ~photo] = (40, 200, 40)
    vis[m & photo] = (235, 235, 235)
    Image.fromarray(vis).resize((gw * 3, gh * 3), Image.NEAREST).save(cfg_path.replace(".json", "_sil_masks.png"))
    print(out)


if __name__ == "__main__":
    main()
