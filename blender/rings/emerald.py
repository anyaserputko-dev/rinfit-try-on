"""Rinfit Thin Silicone Ring — 10 x 8 mm Emerald Cut CZ (GlowStone Thin).
Product page: band 3 mm wide, 2 mm thick; stone 10 x 8 mm emerald-cut CZ; polished brass prong setting.
Photos: img_00 (Nude / Rose Gold, 3/4 from above), img_12 (Black / Silver), img_13 (White / Silver), img_07 (infographic),
video sheet (stone long side along the finger, stone sits high like a solitaire).
Rinfit's "emerald" is faceted like a radiant: brilliant facets on a rectangle with small cut corners.
"""
import math
import bmesh, bpy
from mathutils import Vector, Matrix
import _rect_helpers as H

COLORS = ["Nude and Rose Gold", "White and Silver", "Black and Silver"]
W, LEN = 8.0, 10.0            # stone width across the finger (X), length along the finger (Y)
CORNER = 0.7                  # cut corners of the rectangle (estimate from img_00 / img_07)
CUT = dict(table=0.56, star=0.80, crown=0.14, pavilion=0.50, lower=0.25, sectors=16, pav_sectors=16)
# facet sweep with the plane-cut generator (_rect_helpers.faceted); crown / pav = heights as fractions of W
def _tiers(nq=8, cm=(34, 31, 37), star=(20, 24), table=0.62, pm=(42, 44, 40.5), p2=(37, 39), a2=0.62,
           p3=(30, 33), a3=0.30, p4=None, a4=0.5):
    t = [dict(side="crown", nq=nq, slopes=cm),
         dict(side="crown", nq=nq, offset=0.5, slopes=star, a=table, anchor="table"),
         dict(side="pav", nq=nq, slopes=pm),
         dict(side="pav", nq=nq, offset=0.5, slopes=p2, a=a2, ref=pm[0], lift=0.02),
         dict(side="pav", nq=nq, offset=0.25, slopes=p3, a=a3, ref=pm[0], lift=0.03)]
    if p4:
        t.append(dict(side="pav", nq=nq, offset=0.75, slopes=p4, a=a4, ref=pm[0], lift=0.025))
    return t


_C3 = dict(crown_rings=((0.88, 1, 0.5), (0.75, 2, 0.0)),
           pav_rings=((0.85, 1, 0.5), (0.62, 2, 0.0), (0.40, 4, 0.5), (0.18, 8, 0.0)))
SWEEP = [   # crushed(): crown / pav heights in mm
    dict(crown=1.12, pav=4.3),
    dict(crown=1.12, pav=4.3, jitter=0.05, jitter_z=0.06),
    dict(crown=1.12, pav=4.3, jitter=0.0, jitter_z=0.0),
    dict(crown=1.12, pav=4.3, **_C3),
    dict(crown=1.12, pav=4.3, jitter=0.045, jitter_z=0.05, **_C3),
    dict(crown=1.12, pav=4.3, metal_rough=0.16, rail_r=0.10),
]

# fitted to img_00: ball tips on the corners + RINFIT centre (_rect_fitcam.py, rms 5.5 px), refined on the silhouette
# (_rect_silfit.py, IoU 0.89)
HERO = dict(direction=(-0.0469, -0.3320, 0.9421), up=(0.5017, 0.8077, 0.3096), target=(0, 0, 8), dist=95.9, lens=140)
VIEWS = {
    "hero": dict(camera=HERO, frame=False, color="Nude and Rose Gold"),
    "black": dict(camera=HERO, frame=False, color="Black and Silver"),
    "white": dict(camera=HERO, frame=False, color="White and Silver"),
    # second angle: img_07 infographic (fitted: 4 ball tips + RINFIT, rms 3.0 px)
    "info": dict(camera=dict(direction=(-0.1486, -0.3841, 0.9113), up=(0.4572, 0.7904, 0.4077), target=(0, 0, 8),
                             dist=95.0, lens=90), frame=False, color="Nude and Rose Gold"),
    "side": dict(camera=dict(direction=(1, 0, 0.08), up=(0, 0, 1), dist=220, lens=100), color="White and Silver"),
    "front": dict(camera=dict(direction=(0, -1, 0.25), up=(0, 0, 1), dist=220, lens=100), color="White and Silver"),
}
for _k in range(len(SWEEP)):
    VIEWS[f"s{_k}"] = dict(camera=HERO, frame=False, color="Nude and Rose Gold", scene=f"sweep{_k}")

# domes ~1.4 mm sitting right on the cut corners (img_07 second angle: no neck above the corner, wire runs down the
# corner below the ball) -> no outward lean, ball centre ~0.6 mm over the girdle
PRONG = dict(radius=0.28, tip=(0.72, 0.72, 0.80), lean=0.0, tip_height=0.55)   # thin wire: no lump under the ball


def geometry():
    """Key numbers shared by build() and the camera fit."""
    r_top = 8.66 + 2.0
    girdle_z = r_top + CUT["pavilion"] * W + 0.55
    crown_h = CUT["crown"] * W
    return r_top, girdle_z, crown_h


def corner_index(outline, w, l, c):
    """Index of the chamfer middle in each quadrant (+X+Y, -X+Y, -X-Y, +X-Y).
    Library note: outline_rect's docstring says corners at j = 8, 24, 40, 56, but its rotation puts them at 4, 20, 36, 52."""
    tgt = [(sx * (w / 2 - c / 2), sy * (l / 2 - c / 2)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    return [min(range(len(outline)), key=lambda j: (outline[j][0] - x) ** 2 + (outline[j][1] - y) ** 2) for x, y in tgt]


def ball(L, name, center, radii, axis, mat, subdiv=3):
    """Ellipsoid from an icosphere (a UV sphere's pole facing the camera shows a star-shaped shading artifact)."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    rot = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
    me.transform(Matrix.Translation(center) @ rot @ Matrix.Diagonal((*radii, 1)))
    ob = L.link(bpy.data.objects.new(name, me))
    me.materials.append(mat)
    L.shade(ob, True)
    return ob


def prong(L, name, base, girdle_point, center_xy, crown_h, mat, radius, tip, lean, tip_height):
    """Like rinfit.prong but the wire stays tucked against the stone (rinfit.prong bows it out by 0.9 * radius, which
    shows as a second lobe under the lower balls on img_00) and ends inside the tip."""
    g = Vector(girdle_point)
    out = Vector((g.x - center_xy[0], g.y - center_xy[1], 0)).normalized()
    b = Vector(base)
    p_mid = g + out * radius * 0.3 + Vector((0, 0, -(g.z - b.z) * 0.35))
    p_g = g + out * radius * 0.25
    p_tip = g - out * lean + Vector((0, 0, crown_h * tip_height))
    end = p_tip - (p_tip - p_g).normalized() * 0.25
    parts = [L.tube(name + "_wire", [b, p_mid, p_g, end], radius, mat=mat)]
    parts.append(ball(L, name + "_tip", p_tip, tip, (p_tip - p_g).normalized(), mat))
    return parts


def tip_centers(L):
    r_top, girdle_z, crown_h = geometry()
    outline = L.outline_rect(W, LEN, CORNER) if L else None
    pts = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        g = Vector((sx * (W / 2 - CORNER / 2), sy * (LEN / 2 - CORNER / 2), girdle_z))
        out = Vector((g.x, g.y, 0)).normalized()
        pts.append(g - out * PRONG["lean"] + Vector((0, 0, crown_h * PRONG["tip_height"])))
    return pts


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    sil = L.mat_silicone(bands[0], "Silicone_A")
    metal = L.mat_metal(metals[0])
    cz = L.mat_cz()
    prof = L.BandProfile(width=3.0, thickness=2.0, dome=0.35, inner_dome=0.08, edge_out=0.75, edge_in=0.35)
    band = L.band("band", prof, sil)
    r_top, girdle_z, crown_h = geometry()

    outline = L.outline_rect(W, LEN, CORNER)
    rail_r = 0.09      # thinner and lower: a thicker rail shows through the crown as a rose outline on all sides
    if scene.startswith("sweep"):
        c = dict(SWEEP[int(scene[5:])])
        if "metal_rough" in c:
            metal.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = c.pop("metal_rough")
        rail_r = c.pop("rail_r", rail_r)
        stone = H.crushed(L, "stone", outline, cz, crown_h=c.pop("crown"), pav_d=c.pop("pav"), **c)
    else:
        # sweep winner (s4, 16.09): explicit crushed-ice brilliant, 2 crown + 4 pavilion rings, jitter 0.045 / 0.05 mm
        stone = H.crushed(L, "stone", outline, cz, crown_h=1.12, pav_d=4.3, jitter=0.045, jitter_z=0.05, **_C3)
    stone.location.z = girdle_z

    parts = []
    for i, j in enumerate(corner_index(outline, W, LEN, CORNER)):
        g = Vector((outline[j][0], outline[j][1], girdle_z))
        base = Vector((g.x * 0.80, math.copysign(1.05, g.y), r_top - 0.35))
        parts += L.prong(f"prong{i}", base, g, (0, 0), crown_h, metal, **PRONG)
    # thin rail right under the girdle (img_00: rose-gold line along the lower edge of the stone)
    g2 = 0.022 * W / 2
    parts.append(L.rail("rail", outline, girdle_z - 0.09 - 0.22, rail_r, scale=0.975, mat=metal))
    setting = L.join(parts, "metal", metal, smooth=True)

    # RINFIT on the inside of the band, opposite the stone (seen through the hoop on img_00 / img_12 / img_13)
    L.engrave(band, prof, "RINFIT", phi_center=math.pi, size=2.95, depth=0.2, spacing=1.05, on_inner=True)
    H.drop_empty_slots(band)      # the boolean leaves an unused empty material slot (would reach the GLB)
    L.shade(band, True, sharp_angle=50)
    return [band, stone, setting]
