"""Rinfit GlowStone Marquise set — 14 x 7 mm marquise CZ on a silicone band + 1 thin silicone band (same finger).

Product page: stone 14 x 7 mm, polished brass prong setting, set includes 1 thin silicone ring.
Band width is not stated: 6 mm like the sister pear set (page) — img_00 gives thin/main = 0.46 -> thin band 3 mm (estimate).
Setting (img_00, img_07, video frames): 4 straight side posts with ball tips near the band edges, flat metal side walls
between them (visible as strips beside the stone on img_00 and as a plate on img_07), rails under the girdle from the
posts to 2 elongated claws at the tips.
Thin band on the knuckle side (-Y); video: fingertip up = image up on img_00.
"""
import math
from mathutils import Vector
import _stack_helpers as H

COLORS = ["Pink and Rose Gold", "Nude and Rose Gold", "White and Silver", "Orchid Ice and Rose Gold",
          "Soft Blue and Silver", "Black and Rose Gold"]
W, LEN = 7.0, 14.0
MAIN_W, THIN_W, GAP = 6.0, 2.7, 0.12     # thin band: img_00 band_top->seam 0.317 vs seam->bottom 0.146 of ring width
STACK = MAIN_W + GAP + THIN_W
Y_MAIN = STACK / 2 - MAIN_W / 2          # +Y (fingertip side)
Y_THIN = -(STACK / 2 - THIN_W / 2)

TOP = dict(direction=(0, 0, 1), up=(0, 1, 0), target=(0, 0, 0), dist=75, lens=112)
VIEWS = {
    "hero": dict(camera=TOP, frame=False, color="Pink and Rose Gold", photo="img_00.jpg"),
    "nude": dict(camera=TOP, frame=False, color="Nude and Rose Gold", photo="img_14.jpg"),
    "white": dict(camera=TOP, frame=False, color="White and Silver", photo="img_15.jpg"),
    "orchid": dict(camera=TOP, frame=False, color="Orchid Ice and Rose Gold", photo="img_16.jpg"),
    "blue": dict(camera=TOP, frame=False, color="Soft Blue and Silver", photo="img_17.jpg"),
    "black": dict(camera=TOP, frame=False, color="Black and Rose Gold", photo="img_18.jpg"),
    # video frames 5-8: stack seen from the side, fingertip to the left, stone up
    "side": dict(camera=dict(direction=(-1, 0, 0.22), up=(0, 0, 1), dist=220, lens=100), color="White and Silver"),
    # img_07: three-quarter infographic (Nude band)
    "threeq": dict(camera=dict(direction=(-0.62, -0.62, 0.55), up=(0, 0.3, 1), dist=220, lens=100),
                   color="Nude and Rose Gold", photo="img_07.jpg"),
}


def half_width(y, w=W, l=LEN):
    """Half width of the marquise outline at distance y from its centre (two circular arcs)."""
    cx = (w * w - l * l) / (4 * w)
    R = w / 2 - cx
    return max(0.0, cx + math.sqrt(max(0.0, R * R - y * y)))


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

    cut = dict(table=0.53, star=0.78, crown=0.15, pavilion=0.45, lower=0.22, sectors=16, pav_sectors=16)   # 0.36 (girdle ~3 mm above band as in the video) shows the pink band through the stone
    gz = r_top + cut["pavilion"] * W + 0.5
    # L.outline_marquise returns the lower half in the wrong order (j = 32 jumps back to +X): rebuild it CCW
    upper = L.outline_marquise(W, LEN)[:32]
    outline = upper + [(-x, -y) for x, y in upper]
    stone = L.brilliant("stone", outline, cz, size_ref=W, **cut)
    stone.location = (0, Y_MAIN, gz)
    L.bake(stone)

    parts = []
    post_r, ball_r = 0.3, 0.55
    yp = 2.55                                   # posts just inside the band edges
    xg = half_width(yp)
    xp = xg + 0.45
    for sy in (1, -1):
        for sx in (1, -1):
            x, y = sx * xp, Y_MAIN + sy * yp
            zb = H.band_z(r_top, x) - 0.35
            parts.append(L.tube(f"post{sx}{sy}", [Vector((x, y, zb)), Vector((x, y, gz - 0.6)),
                                                   Vector((x - sx * 0.05, y, gz + 0.3))], post_r, mat=metal))
            parts.append(L.ellipsoid(f"ball{sx}{sy}", (x - sx * 0.06, y, gz + 0.45), (ball_r, ball_r, ball_r * 1.05),
                                     axis=(1, 0, 0), mat=metal))
    for sx in (1, -1):
        # side wall between the two posts on this side
        x = sx * xp
        ys = [Y_MAIN - yp + 2 * yp * i / 8 for i in range(9)]
        top = [Vector((x, y, gz - 0.8)) for y in ys]
        bot = [Vector((x, y, H.band_z(r_top, x) - 0.35)) for y in ys]
        parts.append(H.sheet(L, f"wall{sx}", top, bot, 0.34, (1, 0, 0), metal))
        # no girdle rails: with the shallow pavilion they tint the whole stone pink (img_00 is only faintly warm)
    for sy in (1, -1):
        yt = Y_MAIN + sy * LEN / 2
        parts.append(L.tube(f"tippost{sy}", [Vector((0, yt - sy * 0.35, gz - 0.7)), Vector((0, yt + sy * 0.1, gz - 0.35)),
                                             Vector((0, yt + sy * 0.02, gz + 0.15))], 0.34, mat=metal))
        parts.append(L.ellipsoid(f"claw{sy}", (0, yt - sy * 0.08, gz + 0.42), (0.5, 0.5, 0.72),
                                 axis=(0, sy * 1.0, 0.35), mat=metal))
    setting = L.join(parts, "metal", metal, smooth=True, sharp_angle=50)

    # RINFIT on the inner surface of the main band (img_07). engrave() has no y_offset: shifted profile proxy
    L.engrave(main, H.Shifted(main_p, Y_MAIN), "RINFIT", phi_center=math.radians(180), size=2.6, depth=0.18,
              spacing=1.15, y_center=Y_MAIN, on_inner=True)
    L.shade(main, True, sharp_angle=50)
    L.shade(thin, True, sharp_angle=50)
    return [main, thin, stone, setting]
