"""Підгонка геометрії каблучки «Three Round CZ Stones» під CAD-фото Rinfit.

  Blender -b --factory-startup -P blender/fit/fit_three_stone.py -- [rounds=3] [res=220]

Замість підбору параметрів на око: будуємо каблучку з пласкими emission-матеріалами (силікон / камені /
метал — кожен своїм кольором), рендеримо маленьким рендером і рахуємо IoU з масками, знятими з фото
(blender/fit/ref_masks.npy, чорний варіант 5_fefdd110 — там три матеріали розділяються за яскравістю).
Далі покоординатний спуск по 9 параметрах: кут камери, крен, дистанція, розміри каменів, зазор,
висота рундиста, висота й ширина рейла.

Вивід: blender/fit/best.json — найкращі параметри й IoU по кожній масці.
"""
import sys, os, json, math, time

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)
sys.path.insert(0, BLENDER_DIR)
sys.path.insert(0, os.path.join(BLENDER_DIR, "rings"))
import bpy, numpy as np
from mathutils import Matrix, Vector
import rinfit as L
import three_stone as TS

args = dict(a.split("=", 1) for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
ROUNDS = int(args.get("rounds", 3))
RES = int(args.get("res", 220))
N = 180
TMP = os.path.join(HERE, "_probe.png")

REF = np.load(os.path.join(HERE, "ref_masks.npy"))      # [силует, камені, метал, силікон]
REF_SIL, REF_SETTING, REF_BAND = REF[0], REF[1], REF[2]   # силует | оправа (камені+метал) | ободок

# кольори-мітки матеріалів у пробному рендері
TAG = {"silicone": (0.0, 0.0, 1.0), "metal": (1.0, 0.0, 0.0), "stone": (0.0, 1.0, 0.0)}


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
    e.inputs["Strength"].default_value = 1.0
    nt.links.new(e.outputs[0], out.inputs["Surface"])
    return m


def build(p):
    """Гола геометрія без гравіювання й булевих — на маски вони не впливають, а часу їдять більше за все."""
    L.clear_scene()
    sil, metal, cz = flat("sil", TAG["silicone"]), flat("met", TAG["metal"]), flat("cz", TAG["stone"])
    band_kw = dict(TS.BAND, dome=p["dome"], edge_out=p["edge_out"], thickness=p["thick"])
    prof = L.BandProfile(inner=p["r_in"], **band_kw)
    band = L.band("band", prof, sil, segments=128)
    r_top = prof.outer_r(0)
    girdle_r = r_top + p["girdle_h"]
    r_rail = r_top + p["rail_h"]

    chord = (p["center"] + p["side"]) / 2 + p["gap"]
    d = 2 * math.asin(min(0.99, chord / (2 * girdle_r)))
    row = [(-d, p["side"], "_l"), (0.0, p["center"], "_c"), (d, p["side"], "_r")]

    taper = math.radians(TS.RAIL["taper"])
    phi_end = d + (p["side"] / 2 + TS.RAIL["over"]) / girdle_r + taper
    parts = [TS.rail_mesh(L, "rail", prof, r_rail, p["rail_w"], phi_end, taper, metal, n_phi=90, n_y=8)]
    stones = []
    for phi, dia, tag in row:
        M = Matrix.Rotation(phi, 4, "Y") @ Matrix.Translation((0.0, 0.0, girdle_r))
        R = dia / 2
        stones.append(TS.place(L.brilliant("stone" + tag, L.outline_ellipse(dia, dia), cz, size_ref=dia,
                                           **TS.STONE), M))
        z_rail = r_rail - girdle_r
        for k in range(4):
            a = math.radians(45 + 90 * k)
            c, s = math.cos(a), math.sin(a)
            g = Vector((R * c, R * s, 0.0))
            base = Vector(((R - TS.CLAW["back"]) * c, (R - TS.CLAW["back"]) * s, z_rail - 0.30))
            for q in L.prong(f"claw{tag}_{k}", base, g, (0.0, 0.0), TS.STONE["crown"] * dia, metal,
                             radius=TS.CLAW["radius"], tip=TS.CLAW["tip"], lean=TS.CLAW["lean"],
                             tip_height=TS.CLAW["tip_height"]):
                parts.append(TS.place(L.bake(q), M))
    L.join(parts, "metal", metal)
    return band


def render(p):
    a, r = math.radians(p["alpha"]), math.radians(p["roll"])
    L.camera(direction=(0.0, -math.cos(a), math.sin(a)), up=(math.sin(r), 0.0, math.cos(r)),
             target=(0, 0, 2.5), dist=p["dist"], lens=85)
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

    def crop(m):
        c = m[box[2]:box[3], box[0]:box[1]].astype(float)
        yi = (np.arange(N) * (c.shape[0] - 1) / (N - 1)).round().astype(int)
        xi = (np.arange(N) * (c.shape[1] - 1) / (N - 1)).round().astype(int)
        return c[np.ix_(yi, xi)] > 0.5

    rgb = px[..., :3]
    band = al & (rgb[..., 2] > 0.35) & (rgb[..., 1] < 0.35)                  # силікон (синій)
    return crop(al), crop(al & ~band), crop(band)                            # силует | оправа | ободок


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0


def score(p):
    build(p)
    m = masks(render(p))
    if m is None:
        return -1, (0, 0, 0)
    s = (iou(m[0], REF_SIL), iou(m[1], REF_SETTING), iou(m[2], REF_BAND))
    return 0.34 * s[0] + 0.36 * s[1] + 0.30 * s[2], s


# старт — те, що маємо зараз; кроки покоординатного спуску
P = dict(alpha=70.0, roll=10.0, dist=60.0, center=6.95, side=4.70, gap=0.15,
         girdle_h=2.30, rail_h=0.85, rail_w=1.60, r_in=8.66,
         dome=0.85, edge_out=1.0, thick=2.0)
STEPS = dict(alpha=6.0, roll=6.0, dist=10.0, center=0.8, side=0.6, gap=0.2,
             girdle_h=0.5, rail_h=0.3, rail_w=0.4, r_in=0.6,
             dome=0.4, edge_out=0.5, thick=0.35)
BOUNDS = dict(alpha=(50, 86), roll=(-15, 35), dist=(38, 110), center=(5.0, 10.5), side=(3.2, 7.5),
              gap=(0.0, 0.8), girdle_h=(1.4, 3.6), rail_h=(0.45, 1.8), rail_w=(1.0, 2.6),
              r_in=(7.44, 9.88),   # US 4 ... US 10 за таблицею розмірів Rinfit
              dome=(0.1, 1.8), edge_out=(0.2, 2.4), thick=(1.4, 3.0))

t0 = time.time()
best, parts = score(P)
print("СТАРТ %.4f  силует %.3f оправа %.3f ободок %.3f" % (best, *parts), flush=True)
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
                print("  %-9s %.2f -> %.2f   %.4f  (сил %.3f опр %.3f обод %.3f)" %
                      (k, old, v, s, *pr), flush=True)
                break
            P[k] = old
    for k in STEPS:
        STEPS[k] *= 0.5
    print("коло %d: %.4f  %.0fс  %d прогонів" % (rnd + 1, best, time.time() - t0, evals), flush=True)
    if not improved:
        break

m = masks(render(P))
np.save(os.path.join(HERE, "best_masks.npy"), np.stack(m))
json.dump({"params": P, "score": best, "iou": {"sil": parts[0], "setting": parts[1], "band": parts[2]},
           "evals": evals}, open(os.path.join(HERE, "best.json"), "w"), indent=2)
print("ГОТОВО %.0fс" % (time.time() - t0))
print(json.dumps(P, indent=2))
