"""Rinfit Princess Cut CZ Silicone Ring Set — stackable 2-ring set, 8 x 8 mm princess-cut CZ (GlowStone).
Product page: stone 8 x 8 mm princess CZ, polished brass prong setting, set includes 1 thin silicone ring.
Band width is not stated: main band 6 mm (as the sister pear / marquise sets, matches img_00), thin band ~3.5 mm
(img_00: 0.6 x the main band). Photos: img_00 (Nude / Rose Gold, top), img_11 White, img_12 Pink, img_13 Orchid Ice,
img_14 Black (all Rose Gold except White / Silver), img_07 (3/4 infographic: 4 round claws with tear-drop tips,
rail under the girdle, metal bridge plates on the front and back that go down to the band; the stone sits low).
The thin band sits on the -Y side (image bottom on img_00); both bands are worn together on one finger.
"""
import math
import bpy
from mathutils import Vector
import _rect_helpers as H

TIP_R = (0.58, 0.52, 0.90)    # tear-drop tips (img_00: ~1.2 x 1.7 mm, stretched along the Y sides)

COLORS = ["Nude and Rose Gold", "White and Silver", "Pink and Rose Gold", "Orchid Ice and Rose Gold",
          "Black and Rose Gold"]
S = 8.0                        # stone size
CORNER = 0.12                  # princess corners are almost sharp
MAIN_W, THIN_W = 6.0, 3.0     # overlay on img_00: main 6.1, thin 3.0 mm (page gives neither)
# pavilion >= 0.45: shallower pavilions leak light and show the band through the stone (dark / pink centre)
CUT = dict(table=0.62, star=0.80, crown=0.12, pavilion=0.45, lower=0.25, sectors=16, pav_sectors=16)
PRONG = dict(radius=0.42, tip=(0.50, 0.46, 0.80), lean=-0.05, tip_height=0.60)

# fitted to img_00 (4 tips on the low setting + main band ends, rms 1.1 px): _rect_fitcam.py
TOP = dict(direction=(0.0009, 0.0258, 0.9997), up=(-0.0007, 0.9997, -0.0258), target=(0, 0, 8), dist=61.9, lens=100)
VIEWS = {
    "hero": dict(camera=TOP, frame=False, color="Nude and Rose Gold"),
    "white": dict(camera=TOP, frame=False, color="White and Silver"),
    "pink": dict(camera=TOP, frame=False, color="Pink and Rose Gold"),
    "orchid": dict(camera=TOP, frame=False, color="Orchid Ice and Rose Gold"),
    "black": dict(camera=TOP, frame=False, color="Black and Rose Gold"),
    # second angle: img_07 infographic, main ring only (fitted: 4 tips on the low setting + RINFIT, rms 3.6 px)
    "info": dict(camera=dict(direction=(-0.1578, -0.5048, 0.8487), up=(0.2303, 0.8170, 0.5287), target=(0, 0, 8),
                             dist=54.3, lens=70), frame=False, color="Nude and Rose Gold", scene="main"),
    "side": dict(camera=dict(direction=(1, 0, 0.08), up=(0, 0, 1), dist=220, lens=100), color="Nude and Rose Gold"),
    "front": dict(camera=dict(direction=(0, -1, 0.1), up=(0, 0, 1), dist=220, lens=100), color="Nude and Rose Gold"),
}


def corner_index(outline, w, l, c):
    tgt = [(sx * (w / 2 - c / 2), sy * (l / 2 - c / 2)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    return [min(range(len(outline)), key=lambda j: (outline[j][0] - x) ** 2 + (outline[j][1] - y) ** 2) for x, y in tgt]


def box(L, name, xy_top, xy_bot, z_top, z_bot, mat):
    """Hexahedron: xy_top / xy_bot = 4 corners (counter-clockwise) at the top / bottom."""
    verts = [(x, y, z_bot) for x, y in xy_bot] + [(x, y, z_top) for x, y in xy_top]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = L.mesh_object(name, verts, faces, mat)
    L.fix_normals(ob)
    return ob


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    sil = L.mat_silicone(bands[0], "Silicone_A")
    metal = L.mat_metal(metals[0])
    cz = L.mat_cz()
    dy = 0.0

    # rounder outer edges than first guessed: the silhouette fit on img_00 shows a notch where the two bands meet
    main = L.BandProfile(width=MAIN_W, thickness=2.0, dome=0.45, inner_dome=0.1, edge_out=1.25, edge_in=0.45)
    thin = L.BandProfile(width=THIN_W, thickness=2.0, dome=0.35, inner_dome=0.08, edge_out=1.05, edge_in=0.4)
    band = L.band("band_main", main, sil, y_offset=dy)
    # scene "main": the main ring alone, as on the img_07 infographic
    band2 = None if scene == "main" else L.band("band_thin", thin, sil, y_offset=dy - (MAIN_W + THIN_W) / 2)
    r_top = main.outer_r(0)
    # low setting (img_07: the front bridge plate is only ~1.5 mm between the girdle and the band); the pavilion sits in
    # a pocket in the silicone, its culet stays above the inner surface
    girdle_z = r_top + 1.65
    pav_d = girdle_z - 0.09 - 8.92
    crown_h = CUT["crown"] * S

    outline = L.outline_rect(S, S, CORNER)
    # explicit crushed-ice brilliant (rinfit.brilliant merges facets on straight sides into big steps)
    stone = H.crushed(L, "stone", outline, cz, crown_h=crown_h, pav_d=pav_d, table=0.66, jitter=0.045, jitter_z=0.05,
                      crown_rings=((0.90, 1, 0.5), (0.80, 2, 0.0)),
                      pav_rings=((0.85, 1, 0.5), (0.62, 2, 0.0), (0.40, 4, 0.5), (0.18, 8, 0.0)))
    stone.location = (0, dy, girdle_z)

    parts = []
    for i, j in enumerate(corner_index(outline, S, S, CORNER)):
        x, y = outline[j]
        g = Vector((x, y + dy, girdle_z))
        base = Vector((x * 0.96, y * 0.86 + dy, r_top - 0.7))
        wire, tip = L.prong(f"prong{i}", base, g, (0, dy), crown_h, metal, **PRONG)
        bpy.data.objects.remove(tip, do_unlink=True)
        sx, sy = math.copysign(1, x), math.copysign(1, y)
        c = Vector((sx * 3.95, sy * 4.05 + dy, girdle_z + crown_h * 0.55))
        parts += [wire, L.ellipsoid(f"tip{i}", c, TIP_R, axis=(0.12 * sx, 0.55 * sy, 0.83), mat=metal)]
    g2 = 0.18 / 2                  # crushed() girdle
    parts.append(L.rail("rail", outline, girdle_z - g2 - 0.14, 0.11, scale=0.96, mat=metal, center=(0, dy)))
    # bridge plates on the +Y / -Y sides (img_07), flaring slightly towards the band; inset so the stone
    # does not refract them into a pink border
    for sgn in (1, -1):
        yo, yi = sgn * (S / 2 - 0.45), sgn * (S / 2 - 0.8)
        top = [(-3.5, yi + dy), (3.5, yi + dy), (3.5, yo + dy), (-3.5, yo + dy)]
        bot = [(-3.8, yi + dy), (3.8, yi + dy), (3.8, yo + dy), (-3.8, yo + dy)]
        if sgn < 0:
            top, bot = top[::-1], bot[::-1]
        parts.append(box(L, f"plate{sgn}", top, bot, girdle_z - g2 - 0.1, r_top - 0.55, metal))
    setting = L.join(parts, "metal", metal, smooth=True, sharp_angle=40)

    # pocket in the main band round the pavilion (the silicone is moulded round the setting): without it the lower
    # pavilion sits inside the opaque band and the stone shows a beige square instead of total internal reflection
    pav_depth = pav_d + 0.09
    ztop, zbot = r_top + 0.6, max(8.75, girdle_z - pav_depth - 0.25)
    half_top = S / 2 * (1 - (girdle_z - ztop) / pav_depth) + 0.3
    pocket = box(L, "pocket", [(-half_top, -half_top), (half_top, -half_top), (half_top, half_top), (-half_top, half_top)],
                 [(-0.35, -0.35), (0.35, -0.35), (0.35, 0.35), (-0.35, 0.35)], ztop, zbot, sil)
    L.boolean(band, pocket, "DIFFERENCE")
    # polished metal cup lining the pocket (the setting's seat): light leaving the shallow pavilion now shows metal
    # (the soft peach centre of Rinfit's renders) instead of beige silicone
    zc = r_top - 0.35      # rim under the band surface: less rose gold reflected into the stone from above
    t = (ztop - zc) / (ztop - zbot)
    hc = half_top + (0.35 - half_top) * t
    cv = [(-0.35, -0.35, zbot), (0.35, -0.35, zbot), (0.35, 0.35, zbot), (-0.35, 0.35, zbot),
          (-hc, -hc, zc), (hc, -hc, zc), (hc, hc, zc), (-hc, hc, zc)]
    cup = L.mesh_object("cup", [(x, y + dy, z) for x, y, z in cv],
                        [(0, 3, 2, 1), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], metal)
    L.fix_normals(cup)
    setting = L.join([setting, cup], "metal", metal, smooth=True, sharp_angle=40)
    L.engrave(band, main, "RINFIT", phi_center=math.pi, size=2.4, depth=0.16, spacing=1.12, on_inner=True,
              y_center=dy)
    H.drop_empty_slots(band)      # the boolean leaves an unused empty material slot (would reach the GLB)
    L.shade(band, True, sharp_angle=50)
    objs = [o for o in (band, band2, stone, setting) if o is not None]
    if scene == "glb":            # centre the 2-band stack on the finger (as rings.js does for stacks)
        for ob in objs:
            ob.location.y += THIN_W / 2
    return objs
