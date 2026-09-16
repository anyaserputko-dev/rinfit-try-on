"""Camera fit for matching a Rinfit CAD render (helper used only by emerald / halo / princess).

  python3 blender/rings/_rect_fitcam.py <points.json>

points.json: {"target": [x,y,z], "pts": [[X,Y,Z, u_px, v_px], ...], "fill": 0.8}
Model: perspective camera at target + D*dist looking at target, roll about the view axis;
photo px = s * (x/z, -y/z) + t  (free scale + shift, because compare.py crops both images to the object).
Prints a camera dict for rinfit.camera() (direction, up, target, dist, lens).
"""
import json, math, sys
import numpy as np


def basis(az, el, roll):
    D = np.array([math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)])
    fwd = -D
    up0 = np.array([0.0, 0.0, 1.0]) if abs(D[2]) < 0.98 else np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, up0)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    c, s = math.cos(roll), math.sin(roll)
    r2 = c * right + s * up
    u2 = -s * right + c * up
    return D, fwd, r2, u2


def project(p, P, T):
    az, el, roll, dist, sc, tx, ty = p
    D, fwd, r, u = basis(az, el, roll)
    C = T + D * dist
    q = P - C
    z = q @ fwd
    return np.stack([sc * (q @ r) / z + tx, -sc * (q @ u) / z + ty], 1)


def resid(p, P, T, uv):
    return (project(p, P, T) - uv).ravel()


def lm(p, P, T, uv, it=300):
    lam = 1e-3
    r = resid(p, P, T, uv)
    for _ in range(it):
        J = np.zeros((len(r), len(p)))
        for i in range(len(p)):
            dp = np.zeros(len(p))
            dp[i] = 1e-6 * max(1.0, abs(p[i]))
            J[:, i] = (resid(p + dp, P, T, uv) - r) / dp[i]
        A = J.T @ J
        g = J.T @ r
        while True:
            step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
            pn = p + step
            pn[3] = max(pn[3], 15.0)
            rn = resid(pn, P, T, uv)
            if rn @ rn < r @ r:
                p, r, lam = pn, rn, lam * 0.3
                break
            lam *= 10
            if lam > 1e12:
                return p, r
    return p, r


def main():
    cfg = json.load(open(sys.argv[1]))
    T = np.array(cfg["target"], float)
    arr = np.array(cfg["pts"], float)
    P, uv = arr[:, :3], arr[:, 3:5]
    fix_dist = cfg.get("dist")
    best = None
    span = np.ptp(uv, 0).max()
    for az in np.radians(np.arange(-180, 180, 30)):
        for el in np.radians([10, 30, 50, 70, 85]):
            for roll in np.radians(np.arange(-180, 180, 45)):
                for dist in ([fix_dist] if fix_dist else [60, 150]):
                    p0 = np.array([az, el, roll, dist, span * dist / 25.0, uv[:, 0].mean(), uv[:, 1].mean()])
                    try:
                        p, r = lm(p0, P, T, uv, it=60)
                    except np.linalg.LinAlgError:
                        continue
                    e = math.sqrt((r @ r) / len(r))
                    if best is None or e < best[0]:
                        best = (e, p)
    e, p = best
    p, r = lm(p, P, T, uv, it=400)
    e = math.sqrt((r @ r) / len(r))
    az, el, roll, dist, sc, tx, ty = p
    D, fwd, rr, uu = basis(az, el, roll)
    # lens so that the fitted points span `fill` of the frame (render crop is re-fitted anyway)
    pr = project(p, P, T)
    ext = np.ptp(pr, 0).max() / abs(sc)
    fill = cfg.get("fill", 0.62)
    lens = fill * 36.0 / ext
    print("rms_px %.1f  (photo span %.0f px)" % (e, span))
    for i, (a, b) in enumerate(zip(pr, uv)):
        print("  pt%d fit (%.0f, %.0f) photo (%.0f, %.0f)" % (i, a[0], a[1], b[0], b[1]))
    print("CAM = dict(direction=(%.4f, %.4f, %.4f), up=(%.4f, %.4f, %.4f), target=(%.2f, %.2f, %.2f), dist=%.1f, lens=%.1f)"
          % (*D, *uu, *T, dist, lens))
    # lens at which a square render still covers the whole photo (for the overlay check)
    size = cfg.get("photo_size", 1500)
    far = max(abs(cx - tx) for cx in (0, size)) if True else 0
    far = max(far, max(abs(cy - ty) for cy in (0, size)))
    print("lens_cover %.1f  (sc %.1f tx %.1f ty %.1f)" % (18.0 * abs(sc) / far, sc, tx, ty))
    out = sys.argv[1].replace(".json", "_cam.json")
    json.dump(dict(direction=list(D), up=list(uu), target=list(T), dist=dist, sc=sc, tx=tx, ty=ty,
                   lens_cover=18.0 * abs(sc) / far), open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
