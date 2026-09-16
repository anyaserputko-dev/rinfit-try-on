"""Rinfit GlowStone Pear set — 8 x 12 mm pear CZ on a 6 x 2 mm silicone band + 1 thin silicone band (same finger).

Product page: band width 6 mm, thickness 2 mm; stone 8 x 12 mm pear CZ; polished brass prong setting.
Thin band 3 mm wide (estimate: img_00 thin/main = 0.48). Tip of the pear points to the fingertip (+Y) with the thin band
on the knuckle side (lifestyle img_06, img_09; product render img_00 has the same layout).
Setting (img_00, img_07): V claw over the tip, 2 hooked claws with tear-drop tips at the round end joined by a rail
under the girdle, a sloping metal plate from the band up to that rail; the round end overhangs the thin band.
"""
import math
from mathutils import Vector
import _stack_helpers as H

COLORS = ["Nude and Rose Gold", "White and Silver", "Orchid Ice and Rose Gold", "Pink and Rose Gold",
          "Soft Blue and Silver", "Black and Rose Gold", "Teal Ocean Rose Gold"]
W, LEN = 8.0, 12.0
ROUND = 3.8                     # depth of the round end = widest point from the bottom (img_00 rows)
FLANK_POW = 2.8                 # flank fullness fitted to the img_00 outline
MAIN_W, THIN_W, GAP = 6.0, 3.0, 0.12
STACK = MAIN_W + GAP + THIN_W
Y_MAIN = STACK / 2 - MAIN_W / 2
Y_THIN = -(STACK / 2 - THIN_W / 2)
GIRDLE_LIFT = 0.0               # a 0.8 mm lift (bigger stone in perspective) did not improve the top view
STONE_DY = 0.6                  # stone centre relative to the main band centre, towards the tip (img_00)

TOP = dict(direction=(0, 0, 1), up=(0, 1, 0), target=(0, 0, 0), dist=90, lens=135)
VIEWS = {
    "hero": dict(camera=TOP, frame=False, color="Nude and Rose Gold", photo="img_00.jpg"),
    "white": dict(camera=TOP, frame=False, color="White and Silver", photo="img_16.jpg"),
    "orchid": dict(camera=TOP, frame=False, color="Orchid Ice and Rose Gold", photo="img_17.jpg"),
    "pink": dict(camera=TOP, frame=False, color="Pink and Rose Gold", photo="img_18.jpg"),
    "blue": dict(camera=TOP, frame=False, color="Soft Blue and Silver", photo="img_19.jpg"),
    "black": dict(camera=TOP, frame=False, color="Black and Rose Gold", photo="img_20.jpg"),
    "teal": dict(camera=TOP, frame=False, color="Teal Ocean Rose Gold", photo="img_21.jpg"),
    "side": dict(camera=dict(direction=(-1, 0, 0.22), up=(0, 0, 1), dist=220, lens=100), color="Nude and Rose Gold"),
    "threeq": dict(camera=dict(direction=(-0.55, -0.62, 0.56), up=(0, 0.3, 1), dist=220, lens=100),
                   color="Nude and Rose Gold", photo="img_07.jpg"),
}

# V claw over the tip, in (across, outwards) mm with v = 0 at the stone tip (img_00 close-up)
CLAW = [(0.0, 0.62), (0.3, 0.52), (0.55, 0.22), (0.76, -0.2), (0.84, -0.58), (0.74, -0.9), (0.5, -1.02),
        (0.26, -0.9), (0.0, -0.74)]
CLAW = CLAW + [(-u, v) for u, v in reversed(CLAW[1:-1])]


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    sil = L.mat_silicone(bands[0], "Silicone_A")
    metal = L.mat_metal(metals[0])
    cz = L.mat_cz()

    main_p = L.BandProfile(width=MAIN_W, thickness=2.0, dome=0.4, inner_dome=0.1, edge_out=1.15, edge_in=0.4, samples=56)
    thin_p = L.BandProfile(width=THIN_W, thickness=2.0, dome=0.25, inner_dome=0.05, edge_out=0.9, edge_in=0.35, samples=48)
    main = L.band("band_main", main_p, sil, y_offset=Y_MAIN, segments=144)   # mesh budget for phones
    thin = L.band("band_thin", thin_p, sil, y_offset=Y_THIN, segments=144)
    r_top = main_p.outer_r(0)

    cut = dict(table=0.53, star=0.78, crown=0.15, pavilion=0.45, lower=0.22, sectors=16, pav_sectors=16)
    gz = r_top + cut["pavilion"] * W + 0.5 + GIRDLE_LIFT
    ys = Y_MAIN + STONE_DY
    # L.outline_pear: circular flanks are too slim for Rinfit's stone and belly shortens the stone -> fitted outline
    outline = H.outline_pear_full(W, LEN, ROUND, FLANK_POW)
    stone = L.brilliant("stone", outline, cz, size_ref=W, **cut)
    stone.location = (0, ys, gz)
    L.bake(stone)
    crown_h = cut["crown"] * W
    yc = -LEN / 2 + ROUND                     # centre of the round-end ellipse (stone frame)

    parts = []
    # --- round end: rail under the girdle between the two claws, claws with tear-drop tips
    j_left, j_right = 39, 57
    rail_idx = list(range(j_left, j_right + 1))
    rail2d = H.polyline_offset(outline, 0.3, rail_idx)
    rail = [Vector((x, ys + y, gz - 0.62 - 0.25 * math.sin(math.pi * i / (len(rail2d) - 1))))
            for i, (x, y) in enumerate(rail2d)]
    parts.append(L.tube("rail_round", rail, 0.28, mat=metal))
    for j in (j_left, j_right):
        gx, gy = outline[j]
        g = Vector((gx, ys + gy, gz))
        out = Vector((gx / (W / 2) ** 2, (gy - yc) / ROUND ** 2, 0)).normalized()   # outline normal
        base = Vector((gx - out.x * 0.3, ys + gy - out.y * 0.3, gz - 0.62))
        # img_00: drops lie on the girdle, long axis pointing at the centre of the round end, half outside the stone
        tipc = g + out * 0.42 + Vector((0, 0, 0.4))
        axis = (-out * 0.9 + Vector((0, 0, 0.42))).normalized()
        parts.append(L.tube(f"hook{j}", [base, g + out * 0.9 + Vector((0, 0, -0.4)), g + out * 0.85 + Vector((0, 0, 0.25))],
                            0.32, mat=metal))
        parts.append(L.ellipsoid(f"drop{j}", tipc, (0.6, 0.6, 0.95), axis=axis, mat=metal))
    # sloping plate from the band up to the rail (img_07)
    plate_idx = list(range(43, 54))
    plate2d = H.polyline_offset(outline, 0.55, plate_idx)
    top = [Vector((x, ys + y, gz - 0.95)) for x, y in plate2d]
    xb = [x * 0.8 for x, _ in plate2d]
    bot = [Vector((x, Y_MAIN - MAIN_W / 2 + 0.45, H.band_z(r_top, x) - 0.3)) for x in xb]
    parts.append(H.sheet(L, "plate", top, bot, 0.36, (0, 1, 0), metal))
    # V claw over the tip
    yt = ys + LEN / 2
    parts.append(L.tube("tippost", [Vector((0, yt - 0.25, gz - 0.6)), Vector((0, yt + 0.22, gz - 0.2)),
                                    Vector((0, yt + 0.1, gz + 0.25))], 0.36, mat=metal))
    parts.append(H.pillow(L, "vclaw", CLAW, 0.7, (0, yt + 0.35, gz + 0.45), (1, 0, 0), (0, 1, -0.28), metal, levels=2,
                          scale=1.4))
    setting = L.join(parts, "metal", metal, smooth=True, sharp_angle=50)

    L.shade(main, True, sharp_angle=50)
    L.shade(thin, True, sharp_angle=50)
    return [main, thin, stone, setting]
