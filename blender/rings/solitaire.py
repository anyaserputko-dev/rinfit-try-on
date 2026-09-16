"""Rinfit Silicone Ring - 7 mm Round Solitaire CZ, 2 Rings Set (GlowStone Collection).

Product page: 7 mm round CZ, polished brass prong setting. Band width / thickness are NOT stated.
Estimates (pixels on the img_00 / img_14 CAD renders, img_02 / img_08 lifestyle top views, video frames):
  band ~6.2 mm wide (0.85-0.9 x the stone on top views), ~2.4 mm thick, strongly domed outer surface
  square polished block under the stone, about as wide as the band, flat walls slightly tapering towards
  the band, a round bore for the pavilion; its top ~1 mm under the girdle, girdle ~2.7 mm over the band
  4 claws rising from the block corners on the diagonals, bulbous tear-drop tips leaning in over the crown
  RINFIT debossed on the INNER surface opposite the stone (phi = 180), reading round the ring
Set = two separate rings (first colour left, second colour right on img_00).
Conflict: Rinfit's CAD hero shows the stone ~40 % larger relative to the ring than 7 mm on US 7 (camera fits);
the page dimensions are used.
"""
import math
from mathutils import Vector, Matrix

COLORS = ["Black and White Silver", "Black and Nude Rose Gold", "Nude and Pink Rose Gold",
          "Black Rose Gold and Black Silver", "Black and Pink Rose Gold", "Black and Ocean Rose Gold",
          "Pink and Ocean Rose Gold"]
STONE = 7.0
BAND = dict(width=6.2, thickness=2.4, dome=0.75, inner_dome=0.12, edge_out=0.9, edge_in=0.45)
GIRDLE_H = 2.7                  # girdle above the band crown
# block ~6.6 mm square under the 7 mm stone: walls reach the stone edge (img_00), corners peek out (img_08 top view)
BLOCK = dict(a_top=3.3, a_bot=3.1, below=1.6, top_gap=0.95, bore=2.95, p=10.0, chamfer=0.08)
CLAW = dict(base_r=4.0, wire=0.3, rc=3.45, hc=0.5, tilt=65.0, radii=(0.55, 0.55, 0.8))
# reads bottom-to-top on img_00 (R nearest the viewer side of the ring)
TEXT = dict(size=3.2, depth=0.15, spacing=1.1, rotate=math.pi)
SET_OFFSET = (0.0, 11.0, -2.0)  # second ring of the set relative to the first (hero scene)

# direction/up from least-squares fits of the tip bulbs, RINFIT centres and ring silhouettes on img_00
HERO = dict(direction=(0.18, 0.37, 0.91), up=(-0.97, -0.12, 0.22), target=(-0.5, 6.0, 3.0), dist=70, lens=84)
VIEWS = {
    # img_00: Black + White, silver, 3/4 view from the stone side, second ring to the right
    "hero": dict(camera=HERO, frame=False, color="Black and White Silver"),
    # img_14: Black rose gold + Black silver, same angle
    "rose": dict(camera=HERO, frame=False, color="Black Rose Gold and Black Silver", photo="img_14.jpg"),
    "side": dict(camera=dict(direction=(1, 0.12, 0.3), up=(0, 0, 1), dist=200, lens=100), scene="glb",
                 color="Black and White Silver"),
    "top": dict(camera=dict(direction=(0.02, -0.08, 1), up=(0, 1, 0), dist=200, lens=100), scene="glb",
                color="Black and White Silver"),
}
for _f in (200, 300):   # temporary: thin-film fire test against img_00
    VIEWS["s_f%d" % _f] = dict(camera=HERO, frame=False, color="Black and White Silver", scene="film%d" % _f)


def _rsq(t, ax, ay, p):
    """Radius of the superellipse |x/ax|^p + |y/ay|^p = 1 in direction t."""
    c, s = abs(math.cos(t)), abs(math.sin(t))
    return ((c / ax) ** p + (s / ay) ** p) ** (-1.0 / p)


def block_mesh(L, name, mat, z_bot, z_top, ax_bot, ay_bot, ax_top, ay_top, p=10.0, bore=None, z_floor=None,
               chamfer=0.08, n=128):
    """Closed rounded-square block (tapered walls, chamfered top edge), optional round bore with a floor."""
    ts = [2 * math.pi * i / n for i in range(n)]

    def sq(ax, ay, z):
        return [(_rsq(t, ax, ay, p) * math.cos(t), _rsq(t, ax, ay, p) * math.sin(t), z) for t in ts]

    def circ(r, z):
        return [(r * math.cos(t), r * math.sin(t), z) for t in ts]

    f = (z_top - chamfer - z_bot) / (z_top - z_bot)
    rings = [sq(ax_bot, ay_bot, z_bot),
             sq(ax_bot + (ax_top - ax_bot) * f, ay_bot + (ay_top - ay_bot) * f, z_top - chamfer),
             sq(ax_top - chamfer, ay_top - chamfer, z_top)]
    inner_z = z_top
    if bore:
        rings += [circ(bore + chamfer, z_top), circ(bore, z_top - chamfer), circ(bore, z_floor)]
        inner_z = z_floor
    verts = [v for r in rings for v in r]
    faces = []
    for k in range(len(rings) - 1):
        for i in range(n):
            i2 = (i + 1) % n
            faces.append((k * n + i, k * n + i2, (k + 1) * n + i2, (k + 1) * n + i))
    ct = len(verts)
    verts.append((0, 0, inner_z))
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


def one_ring(L, sil, metal, cz, tag=""):
    prof = L.BandProfile(**BAND)
    band = L.band("band" + tag, prof, sil)
    r_top = prof.outer_r(0)
    girdle_z = r_top + GIRDLE_H
    B = BLOCK
    z_top = girdle_z - B["top_gap"]
    z_bot = r_top - B["below"]

    # silicone pocket under the metal block (the pavilion sinks into the band, hidden by the block)
    tool = block_mesh(L, "pocket", None, z_bot + 0.03, r_top + 1.0, B["a_bot"] - 0.03, B["a_bot"] - 0.03,
                      B["a_bot"] - 0.03, B["a_bot"] - 0.03, p=B["p"], chamfer=0.01, n=64)
    L.boolean(band, tool, "DIFFERENCE")
    L.engrave(band, prof, "RINFIT", phi_center=math.pi, on_inner=True, **TEXT)
    L.shade(band, True, sharp_angle=50)

    # round brilliant proportions: 8 sectors (the library's 16 turn a round stone into a pinwheel; img_00 shows
    # the classic 8 arrows and kites), table 57 %, pavilion 43 %
    stone = L.brilliant("stone" + tag, L.outline_ellipse(STONE, STONE), cz, size_ref=STONE,
                        table=0.56, star=0.78, crown=0.15, pavilion=0.435, lower=0.23, sectors=8, pav_sectors=8)
    stone.location.z = girdle_z
    L.bake(stone)

    parts = [block_mesh(L, "block", metal, z_bot, z_top, B["a_bot"], B["a_bot"], B["a_top"], B["a_top"],
                        p=B["p"], bore=B["bore"], z_floor=z_bot + 0.15, chamfer=B["chamfer"])]
    R = STONE / 2
    C = CLAW
    for k in range(4):
        t = math.radians(45 + 90 * k)
        base = Vector((C["base_r"] * math.cos(t), C["base_r"] * math.sin(t), z_top - 0.3))
        parts += claw(L, f"claw{k}", base, t, R, girdle_z, metal, wire=C["wire"], rc=C["rc"], hc=C["hc"],
                      tilt=C["tilt"], radii=C["radii"])
    setting = L.join(parts, "metal" + tag, metal)
    return [band, stone, setting]


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    cz = L.mat_cz(film=int(scene[4:])) if scene.startswith("film") else L.mat_cz()
    sil_a = L.mat_silicone(bands[0], "Silicone_A")
    metal_a = L.mat_metal(metals[0], "Metal")
    objs = one_ring(L, sil_a, metal_a, cz)
    if scene == "glb" or len(bands) < 2:
        return objs
    sil_b = sil_a if bands[1] == bands[0] else L.mat_silicone(bands[1], "Silicone_B")
    metal_b = metal_a if metals[1] == metals[0] else L.mat_metal(metals[1], "Metal_B")
    objs2 = one_ring(L, sil_b, metal_b, cz, tag="_2")
    for ob in objs2:
        ob.data.transform(Matrix.Translation(SET_OFFSET))
        ob.data.update()
    return objs + objs2
