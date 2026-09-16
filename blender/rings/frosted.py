"""Rinfit Frosted Clear Thin Silicone Ring with Round cut CZ (GlowStone Thin).

Product page: band 3 mm wide, 2 mm thick; frosted clear silicone; polished brass prong setting.
Stone: title/intro say 7 mm, product details say 8 mm. Video frames: stone ~2.7-2.8 x the 3 mm band
-> 8 mm used (also the width of the other GlowStone Thin stones, oval 11x8 / emerald 10x8).
Setting (img_06 infographic, img_00 front view): 4 claws on the diagonals with big rounded tear-drop tips,
a round gallery wire just under the girdle, and a small flat plate on the band where the claws meet.
RINFIT debossed on the INNER surface under the stone (visible behind the stone on img_00, inside on img_06).

Stone look, front view (diagnosed 16.09): rail / plate / transmissive band / ray depth all render identically
(mean 217, sat 0.6) - none of them darkens the stone. This view looks almost straight down the table, so the
stone returns the light from right above the camera, where the tent world has its dark zenith disc; solitaire's
hero camera is ~40 deg off its table and misses it. Hence, for this ring's views only: zenith 0.25 -> 0.12,
plus the library's thin-film option on the CZ for the pastel fire of Rinfit's render.
Stone crop vs img_00 (mean / colour / dark area %): photo 211 / 18.2 / 7.8, before 217 / 0.6 / ~15, now 228 / 5.5 / 6.6.
"""
import math
from mathutils import Vector

COLORS = ["Frosted Clear"]
STONE = 8.0
BAND = dict(width=3.0, thickness=2.0, dome=0.12, inner_dome=0.05, edge_out=0.55, edge_in=0.3)
GIRDLE_GAP = 0.55               # culet above the band crown
PLATE = dict(ax=2.1, ay=1.4, below=0.3, above=0.45, p=6.0)
# tear-drop bulbs on the girdle edge leaning in over the crown (img_00 bulbs ~1.3 x 1.7 mm, elongated radially)
CLAW = dict(base=(1.55, 1.05), wire=0.3, rc=4.05, hc=0.45, tilt=70.0, radii=(0.56, 0.56, 0.9))
# band colour: library "Frosted Clear" #eef2f3 renders cyan-grey (219, 224, 225) through the transmission;
# img_00 band mid-tone is neutral (235, 236, 238). Sweep: #f6f6f7 -> 228, #ffffff r0.42 -> 240, #ffffff r0.30 -> 236
FROSTED_HEX, FROSTED_ROUGH = "#ffffff", 0.30
CZ_FILM = 300                   # thin-film thickness (nm): pastel fire, colour spread 0.6 -> 5.5 (photo 18.2)
# gallery wire tucked just inside the girdle edge (img_06); lower/smaller rails show through the stone as a metal circle,
# a wider one sticks out past the girdle as an outline in the front view
RAIL = dict(dz=0.65, radius=0.24, scale=0.93)
TEXT = dict(size=2.7, depth=0.12, spacing=1.1)
# library tent defaults with a smaller zenith disc (see the module docstring); everything else as tuned there
STUDIO = dict(tent=dict(cards=18, card_width=0.45, horizon=0.6, floor_gray=0.9, top=1.4, zenith=0.12))

# camera fitted to img_00 (pads + band extremes + far band top, rms 8 px): camera on the +Y side, mild perspective
FRONT = dict(direction=(0, 0.19, 1), up=(0, 1, 0), target=(0, -2.5, 8), dist=125, lens=190)
VIEWS = {
    # img_00 (gift box masked out): front view, the band's inner surface visible behind the stone
    "hero": dict(camera=FRONT, frame=False, photo="img_00_nobox.jpg", studio=STUDIO),
    # img_06 infographic (pink background masked out): 3/4 view from above
    # camera fitted to the 4 tip bulbs, the RINFIT centre and the band silhouette (rms 5 px), re-aimed at the ring
    "angle": dict(camera=dict(direction=(-0.143, -0.389, 0.910), up=(0.454, 0.831, 0.323), target=(0, 0, 5), dist=103,
                              lens=170),
                  frame=False, photo="img_06_clean.jpg", studio=STUDIO),
    "side": dict(camera=dict(direction=(1, 0, 0.05), up=(0, 0, 1), dist=220, lens=100), studio=STUDIO),
    # close-up of the claws / gallery / plate from the img_06 angle
    "setting": dict(camera=dict(direction=(-0.143, -0.389, 0.910), up=(0.454, 0.831, 0.323), target=(0, -1, 12),
                                dist=103, lens=380), frame=False, studio=STUDIO),
}


def _rsq(t, ax, ay, p):
    c, s = abs(math.cos(t)), abs(math.sin(t))
    return ((c / ax) ** p + (s / ay) ** p) ** (-1.0 / p)


def plate_mesh(L, name, mat, z_bot, z_top, ax, ay, p=6.0, chamfer=0.1, n=96):
    """Closed rounded-rectangle plate with a chamfered top edge."""
    ts = [2 * math.pi * i / n for i in range(n)]

    def sq(a, b, z):
        return [(_rsq(t, a, b, p) * math.cos(t), _rsq(t, a, b, p) * math.sin(t), z) for t in ts]

    rings = [sq(ax, ay, z_bot), sq(ax, ay, z_top - chamfer), sq(ax - chamfer, ay - chamfer, z_top)]
    verts = [v for r in rings for v in r]
    faces = []
    for k in range(len(rings) - 1):
        for i in range(n):
            i2 = (i + 1) % n
            faces.append((k * n + i, k * n + i2, (k + 1) * n + i2, (k + 1) * n + i))
    ct = len(verts)
    verts.append((0, 0, z_top))
    cb = len(verts)
    verts.append((0, 0, z_bot))
    last = (len(rings) - 1) * n
    for i in range(n):
        i2 = (i + 1) % n
        faces.append((last + i, last + i2, ct))
        faces.append((i2, i, cb))
    ob = L.mesh_object(name, verts, faces, mat, smooth=True)
    L.fix_normals(ob)
    L.shade(ob, True, sharp_angle=30)
    return ob


def claw(L, name, base, t, R, girdle_z, mat, wire=0.3, rc=None, hc=0.5, tilt=45.0, radii=(0.55, 0.55, 0.8)):
    """Round wire from `base` up just outside the girdle, ending in a tear-drop bulb that leans in over the crown."""
    out = Vector((math.cos(t), math.sin(t), 0.0))
    z = Vector((0.0, 0.0, 1.0))
    rc = R if rc is None else rc
    c = out * rc + z * (girdle_z + hc)
    a = math.radians(tilt)
    axis = (z * math.cos(a) - out * math.sin(a)).normalized()
    b = Vector(base)
    p_mid = out * (R + wire * 0.95) + z * (girdle_z - 0.4 * (girdle_z - b.z))
    p_g = out * (R + wire * 0.85) + z * girdle_z
    p_end = c - axis * radii[2] * 0.45
    return [L.tube(name + "_wire", [b, p_mid, p_g, p_end], wire, mat=mat),
            L.ellipsoid(name + "_tip", c, radii, tuple(axis), mat)]


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    sil = L.mat_silicone(FROSTED_HEX if bands[0] == "Frosted Clear" else bands[0], "Silicone_A", frosted=True)
    L._principled(sil).inputs["Roughness"].default_value = FROSTED_ROUGH
    metal = L.mat_metal(metals[0])
    cz = L.mat_cz(film=CZ_FILM)

    prof = L.BandProfile(**BAND)
    band = L.band("band", prof, sil)
    r_top = prof.outer_r(0)

    # round brilliant proportions: 8 sectors (16 turn a round stone into a pinwheel; img_00 shows the classic
    # 8 arrows and kites), table 57 %, pavilion 43 %
    cut = dict(table=0.56, star=0.78, crown=0.15, pavilion=0.435, lower=0.23, sectors=8, pav_sectors=8)
    girdle_z = r_top + cut["pavilion"] * STONE + GIRDLE_GAP
    outline = L.outline_ellipse(STONE, STONE)
    stone = L.brilliant("stone", outline, cz, size_ref=STONE, **cut)
    stone.location.z = girdle_z

    P = PLATE
    parts = [plate_mesh(L, "plate", metal, r_top - P["below"], r_top + P["above"], P["ax"], P["ay"], p=P["p"])]
    R = STONE / 2
    C = CLAW
    for k in range(4):
        t = math.radians(45 + 90 * k)
        sx, sy = (1 if math.cos(t) > 0 else -1), (1 if math.sin(t) > 0 else -1)
        base = Vector((sx * C["base"][0], sy * C["base"][1], r_top + P["above"] - 0.25))
        parts += claw(L, f"claw{k}", base, t, R, girdle_z, metal, wire=C["wire"], rc=C["rc"], hc=C["hc"],
                      tilt=C["tilt"], radii=C["radii"])
    if RAIL:
        parts.append(L.rail("rail", outline, girdle_z - RAIL["dz"], RAIL["radius"], scale=RAIL["scale"], mat=metal))
    setting = L.join(parts, "metal", metal)

    L.engrave(band, prof, "RINFIT", phi_center=math.pi, on_inner=True, **TEXT)
    L.shade(band, True, sharp_angle=50)
    return [band, stone, setting]
