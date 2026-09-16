"""Rinfit GlowStone Black Oval stack — 12 x 8 mm black oval CZ on a 6 x 2 mm silicone band + 2 stackable V bands.

Product page: main band 6 mm x 2 mm; stone 12 x 8 mm (the page text says "Pear-Cut", the product is an oval);
polished brass prong setting; stackable rings 2 mm wide x 2 mm thick. Only colour: Black and Rose Gold.
img_00 (top view): 4 rose-gold prongs with egg-shaped tips; one V band on each side of the main band. The two V bands
are mirror images: both lie flat against the main band round the back and bow AWAY from the stone at phi = 0 to make
room for its tips (edge measurements on img_00 are symmetric to 1 px). Pyramid studs: diamond-based 4-sided pyramids
in a single row covering the outer face, neighbours touching, fine grain texture.
"""
import math
from mathutils import Vector
import _stack_helpers as H

COLORS = ["Black and Rose Gold"]
W, LEN = 8.0, 12.0
MAIN_W = 6.0
V_W, V_BASE_T, STUD_H = 2.0, 1.35, 0.85     # page says 2 mm thick; img_00 needs base outer ~9.9 mm or the far-side
                                            # silhouette shows stud tips only, so total reads ~2.2 mm (estimate)
V_GAP = 0.1                                 # gap where the V lies flat (0.35 fitted the far-side silhouette better but opened see-through slits img_00 does not have)
V_RISE = 3.85                               # extra shift at phi = 0 (img_00: inner edge ~6.4 mm from the centre)
V_S0 = 0.9                                  # |sin(phi)| where the arm meets the flat shoulder (img_00: flat along the sides)
V_POW = 1.5                                 # fitted with a silhouette sweep against img_00 (flat shoulders, sharp apex)
V_ROUND = 0.03
STUDS = 44
STUD_W = 1.9               # img_00: ~11 studs per V arm on the front half, wide and deep
GZ_OFFSET = 0.0        # stone height tweak (mm) on top of band top + pavilion + 0.5
EGG = (0.6, 0.6, 0.88)
STONE_SPEC = 0.25           # img_00 crown facets read 45-105/255; 0.5 renders them ~130
BAND_HEX = "#0f0f10"   # hero render only: img_00 black silicone reads 36/255, catalogue #1e1e20 renders at 66 in the tent
                       # studio (same lift on pear Black/Teal) -> lighting issue; the GLB keeps the catalogue colour

TOP = dict(direction=(0, 0, 1), up=(0, 1, 0), target=(0, 0, 0), dist=80, lens=120)
VIEWS = {
    "hero": dict(camera=TOP, frame=False, color="Black and Rose Gold", photo="img_00.jpg"),
    # video frames 6-11: main band alone from the fingertip side, a little above
    "side": dict(camera=dict(direction=(-1, 0, 0.22), up=(0, 0, 1), dist=220, lens=100)),
    # img_06: front infographic (main band only is shown there)
    "front": dict(camera=dict(direction=(0, -0.35, 1), up=(0, 1, 0.35), dist=220, lens=100), photo="img_06.jpg"),
}


def v_shape(phi):
    flat = MAIN_W / 2 + V_GAP + V_W / 2
    if math.cos(phi) <= 0:
        return flat
    s = abs(math.sin(phi))
    s = math.sqrt(s * s + V_ROUND * V_ROUND) - V_ROUND
    t = max(0.0, 1.0 - s / V_S0)
    return flat + V_RISE * t ** V_POW


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    sil = L.mat_silicone(BAND_HEX if (bands[0] == "Black" and scene != "glb") else bands[0], "Silicone_A")
    metal = L.mat_metal(metals[0])
    stone_mat = L.mat_cz_black()
    stone_mat.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = STONE_SPEC
    stud_mat = sil if scene == "glb" else H.textured_copy(sil, "Silicone_A_grain", roughness=0.62)

    main_p = L.BandProfile(width=MAIN_W, thickness=2.0, dome=0.45, inner_dome=0.08, edge_out=1.05, edge_in=0.35, samples=56)
    main = L.band("band_main", main_p, sil, segments=144)   # mesh budget: the band revolve was 20 k of the 51 k tris
    r_top = main_p.outer_r(0)

    objs = [main]
    v_p = L.BandProfile(width=V_W, thickness=V_BASE_T, dome=0.0, inner_dome=0.0, edge_out=0.2, edge_in=0.2, samples=36)
    R_v = v_p.outer_r(0)
    for side in (1, -1):
        fn = (lambda p, s=side: s * v_shape(p))
        vb = L.band(f"chevron{'_top' if side > 0 else '_bottom'}", v_p, stud_mat, segments=192, y_of_phi=fn)
        L.shade(vb, True, sharp_angle=40)
        studs = H.pyramid_row(L, "studs", R_v, fn, STUDS, across=STUD_W, height=STUD_H, mat=stud_mat)
        ch = L.join([vb, studs], vb.name, stud_mat)
        objs.append(ch)

    cut = dict(table=0.58, star=0.8, crown=0.16, pavilion=0.36, lower=0.3, sectors=8, pav_sectors=8)   # video: stone sits low
    gz = r_top + cut["pavilion"] * W + 0.5 + GZ_OFFSET
    outline = L.outline_ellipse(W, LEN)
    stone = L.brilliant("stone", outline, stone_mat, size_ref=W, **cut)
    stone.location = (0, 0, gz)
    L.bake(stone)
    objs.append(stone)

    parts = []
    crown_h = cut["crown"] * W
    for j in (7, 25, 39, 57):                  # prong tips on img_00 sit ~39 deg from the long axis
        x, y = outline[j]
        g = Vector((x, y, gz))
        out = Vector((x / (W / 2) ** 2, y / (LEN / 2) ** 2, 0)).normalized()     # outline normal
        base = Vector((x * 0.8, y * 0.7, H.band_z(r_top, x * 0.8) - 0.3))
        parts.append(L.tube(f"post{j}", [base, g + out * 0.3 + Vector((0, 0, -1.2)), g + out * 0.28 + Vector((0, 0, 0.15))],
                            0.34, mat=metal, resolution=2))
        axis = (-out * 0.8 + Vector((0, 0, 0.6))).normalized()
        parts.append(L.ellipsoid(f"egg{j}", g + out * 0.12 + Vector((0, 0, 0.45)), EGG, axis=axis,
                                 mat=metal, subdivisions=3))
    objs.append(L.join(parts, "metal", metal, smooth=True, sharp_angle=50))
    L.shade(main, True, sharp_angle=50)
    return objs
