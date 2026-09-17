"""Підгонка каблучки MetalBar під CAD-фото Rinfit (00_mr2).

  Blender -b --factory-startup -P blender/fit/fit_metal_bar.py -- [rounds=9] [res=300]

Три маски з фото (blender/fit/ref_masks_mb.npy): силует · сталева смуга · темний внутрішній тунель.
У пробному рендері матеріали пласкі: силікон синій, метал червоний, а внутрішня поверхня ободка —
зелена (грані, чия нормаль дивиться до осі, отримують окремий матеріал). Далі покоординатний спуск.
"""
import sys, os, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)
sys.path.insert(0, BLENDER_DIR)
sys.path.insert(0, os.path.join(BLENDER_DIR, "rings"))
import bpy, numpy as np
from mathutils import Vector
import rinfit as L
import _band_helpers as H
import metal_bar as MB

args = dict(a.split("=", 1) for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
ROUNDS, RES, N = int(args.get("rounds", 9)), int(args.get("res", 300)), 180
TMP = os.path.join(HERE, "_probe_mb.png")
REF = np.load(os.path.join(HERE, "ref_masks_mb.npy"))          # силует | смуга | тунель


def flat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*rgb, 1.0)
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    return m


def build(p):
    """Без гравіювання: на маски воно не впливає, а булеві з'їдають більшість часу."""
    L.clear_scene()
    outer_m, inner_m, met = flat("o", (0, 0, 1)), flat("i", (0, 1, 0)), flat("m", (1, 0, 0))
    band_kw = dict(MB.BAND, dome=p["dome"], edge_out=p["edge_out"], edge_in=p["edge_in"],
                   inner_dome=p["inner_dome"], thickness=p["thick"])
    prof = L.BandProfile(inner=p["r_in"], **band_kw)
    band = L.band("band", prof, outer_m, segments=160)
    band.data.materials.append(inner_m)
    for poly in band.data.polygons:                              # грані, що дивляться до осі = внутрішні
        c = poly.center
        radial = Vector((c.x, 0.0, c.z))
        if radial.length > 1e-6 and poly.normal.dot(radial.normalized()) < 0:
            poly.material_index = 1
    MB.strip_mesh(L, "strip", prof, math.radians(p["strip_phi"]), p["strip_arc"],
                  MB.STRIP["lift"], MB.STRIP["depth"], met)


def render(p):
    # Нахил від осі пальця на кут alpha, азимут нахилу beta (куди саме відхилена камера навколо кільця),
    # плюс крен roll. Без beta модель могла нахилятись лише «вгору» — а на цьому фото каблучка
    # стиснута по горизонталі, тобто камера відведена вбік.
    a, b, r = math.radians(p["alpha"]), math.radians(p["beta"]), math.radians(p["roll"])
    L.camera(direction=(math.sin(a) * math.sin(b), -math.cos(a), math.sin(a) * math.cos(b)),
             up=(math.sin(r), 0.0, math.cos(r)), target=(0, 0, 0), dist=p["dist"], lens=95)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.render.filepath = TMP
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(TMP, check_existing=False)
    px = np.array(img.pixels[:]).reshape(img.size[1], img.size[0], 4)[::-1]
    bpy.data.images.remove(img)
    return px


def masks(px):
    al = px[..., 3] > 0.5
    if al.sum() < 50:
        return None
    ys, xs = np.nonzero(al)
    box = (xs.min(), xs.max() + 1, ys.min(), ys.max() + 1)
    side = max(box[1] - box[0], box[3] - box[2])                 # квадрат по більшій стороні:
    cx, cy = (box[0] + box[1]) / 2, (box[2] + box[3]) / 2        # співвідношення сторін НЕ можна губити

    def crop(m):
        yi = np.clip((cy - side / 2 + np.arange(N) * side / N).astype(int), 0, m.shape[0] - 1)
        xi = np.clip((cx - side / 2 + np.arange(N) * side / N).astype(int), 0, m.shape[1] - 1)
        return m[np.ix_(yi, xi)]

    rgb = px[..., :3]
    return (crop(al),
            crop(al & (rgb[..., 0] > 0.35) & (rgb[..., 1] < 0.35)),      # смуга (червона)
            crop(al & (rgb[..., 1] > 0.35) & (rgb[..., 0] < 0.35)))      # тунель (зелений)


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def score(p):
    build(p)
    m = masks(render(p))
    if m is None:
        return -1, (0, 0, 0)
    s = tuple(iou(m[i], REF[i]) for i in range(3))
    return 0.40 * s[0] + 0.30 * s[1] + 0.30 * s[2], s


P = dict(alpha=40.0, beta=90.0, roll=0.0, dist=95.0, dome=0.95, edge_out=1.70, edge_in=0.55,
         inner_dome=0.10, thick=2.0, r_in=9.88, strip_arc=7.8, strip_phi=205.0)
STEPS = dict(alpha=8.0, beta=30.0, roll=8.0, dist=14.0, dome=0.4, edge_out=0.6, edge_in=0.3,
             inner_dome=0.15, thick=0.35, r_in=0.7, strip_arc=1.6, strip_phi=14.0)
BOUNDS = dict(alpha=(3, 88), beta=(-180, 180), roll=(-60, 60), dist=(50, 200), dome=(0.15, 1.9), edge_out=(0.3, 3.2),
              edge_in=(0.1, 1.6), inner_dome=(0.0, 0.6), thick=(1.4, 3.0), r_in=(8.3, 11.0),
              strip_arc=(4.0, 14.0), strip_phi=(-180, 360))

t0 = time.time()

# Грубий перебір ракурсу ПЕРЕД спуском: покоординатний спуск сам не вибирається з іншого боку кільця
# (і застрягає на наскрізному отворі, якого на фото немає).
grid_best, grid_p = -1, None
for al in (58, 64, 70, 76, 82):
    for be in (-135, -90, -45, 0, 45, 90, 135, 180):
        for ro in (-20, 0, 20):
            P.update(alpha=al, beta=be, roll=ro)
            s_, pr_ = score(P)
            if s_ > grid_best:
                grid_best, grid_p = s_, (al, be, ro, pr_)
P.update(alpha=grid_p[0], beta=grid_p[1], roll=grid_p[2])
print("СІТКА: кут %d° азимут %d° крен %d° -> %.4f (сил %.3f смуга %.3f тунель %.3f)"
      % (*grid_p[:3], grid_best, *grid_p[3]), flush=True)

best, parts = score(P)
print("СТАРТ %.4f  силует %.3f смуга %.3f тунель %.3f" % (best, *parts), flush=True)
evals = 1
for rnd in range(ROUNDS):
    improved = False
    for k in list(P):
        for sgn in (+1, -1):
            v = P[k] + sgn * STEPS[k]
            lo, hi = BOUNDS[k]
            if not (lo <= v <= hi):
                continue
            old = P[k]
            P[k] = v
            s, pr = score(P)
            evals += 1
            if s > best + 1e-4:
                best, parts, improved = s, pr, True
                print("  %-11s %.2f -> %.2f   %.4f  (сил %.3f смуга %.3f тунель %.3f)" %
                      (k, old, v, s, *pr), flush=True)
                break
            P[k] = old
    for k in STEPS:
        STEPS[k] *= 0.5
    print("коло %d: %.4f  %.0fс  %d прогонів" % (rnd + 1, best, time.time() - t0, evals), flush=True)
    if not improved:
        break

np.save(os.path.join(HERE, "best_masks_mb.npy"), np.stack(masks(render(P))))
json.dump({"params": P, "score": best,
           "iou": {"sil": parts[0], "strip": parts[1], "inner": parts[2]}, "evals": evals},
          open(os.path.join(HERE, "best_mb.json"), "w"), indent=2)
print("ГОТОВО %.0fс" % (time.time() - t0))
print(json.dumps(P, indent=2))
