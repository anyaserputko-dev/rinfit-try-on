"""Rinfit Thin Silicone Ring — Oval Cut CZ 11 x 8 mm (GlowStone Thin).
Product page: band 3 mm wide, 2 mm thick; stone 11 x 8 mm oval CZ; polished brass prong setting (4 prongs).
Photos: img_00 (White and Silver, top view), img_10 (Nude/Rose Gold + Black/Silver).
"""
import math
from mathutils import Vector

COLORS = ["White and Silver", "Nude and Rose Gold", "Black and Silver"]
W, LEN = 8.0, 11.0            # stone width across the finger, length along the finger

TOP = dict(direction=(0, -0.12, 1), up=(0, 1, 0), target=(0, 0, 11), dist=48, lens=70)
VIEWS = {
    # img_00: almost straight down on the stone, fairly close perspective (band strip ~2.2x the stone width)
    "hero": dict(camera=TOP, frame=False, color="White and Silver"),
    # img_10: Nude / Rose Gold, same angle
    "nude": dict(camera=TOP, frame=False, color="Nude and Rose Gold", photo="img_10.jpg"),
    "band": dict(camera=dict(direction=(0, -0.35, -1), up=(0, 1, 0), dist=60, lens=70), color="White and Silver"),
    "side": dict(camera=dict(direction=(1, 0, 0.05), up=(0, 0, 1), dist=220, lens=100), color="White and Silver"),
}


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    sil = L.mat_silicone(bands[0], "Silicone_A")
    metal = L.mat_metal(metals[0])
    cz = L.mat_cz()

    prof = L.BandProfile(width=3.0, thickness=2.0, dome=0.12, inner_dome=0.05, edge_out=0.55, edge_in=0.3)
    band = L.band("band", prof, sil)
    r_top = prof.outer_r(0)

    # crushed-ice look of Rinfit renders: 16 crown + 16 pavilion sectors (sweep 15.09: closest to img_00)
    cut = dict(table=0.53, star=0.78, crown=0.15, pavilion=0.50, lower=0.22, sectors=16, pav_sectors=16)
    # the culet stops just above the metal seat on the band (side video frames: pavilion almost touches the band)
    girdle_z = r_top + cut["pavilion"] * W + 0.55
    stone = L.brilliant("stone", L.outline_ellipse(W, LEN), cz, size_ref=W, **cut)
    stone.location.z = girdle_z

    parts = []
    crown_h = 0.14 * W
    outline = L.outline_ellipse(W, LEN)
    # 4 prongs placed where they sit on the photo (roughly 60 deg from the long axis)
    n = len(outline)
    for j in (6, 26, 38, 58):   # ~33 deg from the +X axis on the parametric ellipse, as on img_00
        x, y = outline[j]
        g = Vector((x, y, girdle_z))
        base = Vector((x * 0.55, y * 0.25, r_top - 0.3))
        # img_00: claw tip is a rounded drop ~0.9 mm wide and ~1.5 mm long lying over the crown edge
        parts += L.prong(f"prong{j}", base, g, (0, 0), crown_h, metal, radius=0.45, tip=(0.62, 0.55, 0.85),
                         lean=0.35, tip_height=0.35)
    # no gallery rail under the girdle (img_00 / img_10 show none through the stone); a small seat on the band
    parts.append(L.rail("seat", outline, r_top + 0.2, 0.3, scale=0.36, mat=metal))
    setting = L.join(parts, "metal", metal, smooth=True)

    L.engrave(band, prof, "RINFIT", phi_center=math.radians(180), size=1.9, depth=0.15, spacing=1.15)
    L.shade(band, True, sharp_angle=50)
    return [band, stone, setting]
