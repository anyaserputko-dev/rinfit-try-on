"""Rinfit Halo Silicone Ring — 10 x 8 mm Emerald Cut CZ with a halo (GlowStone Halo).
Product page: band 6 mm wide, 2 mm thick; stone 10 x 8 mm emerald-cut CZ with halo setting; polished brass setting.
Photos: img_00 (White / Silver, 3/4 from above), img_12 (Black / Silver), img_13 (Nude / Rose Gold), img_07 (front infographic).
Halo on img_07 (counted with a 2D peak detector): 30 round stones — 8 on each long side, 5 on each short side,
1 on each corner — pitch ~1.22 mm on a rounded rectangle 9.1 x 11.1 mm (centre line).
Centre stone: radiant-style facets, 4 small faceted claws on the cut corners. U-cut (scalloped) halo gallery with
small beads between the halo stones; the halo sits on a tapered skirt that goes down into the band.
"""
import math
import bmesh, bpy
from mathutils import Vector, Matrix
import _rect_helpers as H

COLORS = ["White and Silver", "Nude and Rose Gold", "Black and Silver"]
W, LEN = 8.0, 10.0
CORNER = 0.8
CUT = dict(table=0.58, star=0.80, crown=0.14, pavilion=0.50, lower=0.25, sectors=16, pav_sectors=16)
HALO_N, HALO_D = 30, 1.15              # halo stones (img_07: they nearly touch, little metal between them)
HALO_A, HALO_B, HALO_RHO = 4.56, 5.56, 2.17   # centre line half-width / half-length / corner radius

# fitted to img_00: claws + RINFIT centre (_rect_fitcam.py), refined on the silhouette (_rect_silfit.py) with the
# lowered halo: IoU 0.911 (halo 0.35 mm under the girdle) -> 0.922 (1.3 mm) -> 0.928 (1.8 mm, setting +0.56 mm);
# a wider halo line (IoU 0.918) or bigger halo stones (0.923) do not fit better
HERO = dict(direction=(-0.1489, -0.4046, 0.9023), up=(0.2913, 0.8540, 0.4310), target=(0, 0, 8), dist=75.3, lens=105)
VIEWS = {
    "hero": dict(camera=HERO, frame=False, color="White and Silver"),
    "black": dict(camera=HERO, frame=False, color="Black and Silver"),
    "nude": dict(camera=HERO, frame=False, color="Nude and Rose Gold"),
    # second angle: img_07 infographic, almost straight down (fitted: 4 claws + band ends, rms 2.2 px)
    "info": dict(camera=dict(direction=(-0.0062, 0.0797, 0.9968), up=(-0.0003, 0.9968, -0.0797), target=(0, 0, 8),
                             dist=168.3, lens=200), frame=False, color="Nude and Rose Gold"),
    "front": dict(camera=dict(direction=(0, 0, 1), up=(0, 1, 0), dist=220, lens=100), color="Nude and Rose Gold"),
    "side": dict(camera=dict(direction=(1, 0, 0.08), up=(0, 0, 1), dist=220, lens=100), color="White and Silver"),
}


def geometry():
    r_top = 8.66 + 2.0
    girdle_z = r_top + CUT["pavilion"] * W + 0.55 + 0.56    # +0.56 mm: silhouette fit on img_00
    # girdle of the halo stones: well below the centre girdle (img_00: the far halo row hides behind the crown,
    # a metal wall shows between the stone edge and the near halo row; silhouette fit best at 1.8 mm)
    halo_z = girdle_z - 1.8
    return r_top, girdle_z, halo_z


def rrect_point(s, a, b, rho):
    """Point and outward normal on a rounded rectangle at arc length s, s = 0 at (0, +b), going towards +X."""
    top = a - rho
    side = b - rho
    arc = math.pi * rho / 2
    quarter = top + arc + side
    per = 4 * quarter
    s = s % per
    # build first quarter (from (0,b) clockwise to (a,0)), mirror for the rest
    def quad(t):
        if t <= top:
            return (t, b), (0, 1)
        if t <= top + arc:
            ang = (t - top) / rho       # 0 .. pi/2
            n = (math.sin(ang), math.cos(ang))
            return (top + rho * n[0], side + rho * n[1]), n
        return (a, b - rho - (t - top - arc)), (1, 0)
    q = int(s // (2 * quarter))
    t = s - q * 2 * quarter
    if t <= quarter:
        p, n = quad(t)
    else:
        p, n = quad(2 * quarter - t)
        p, n = (p[0], -p[1]), (n[0], -n[1])
    if q == 1:
        p, n = (-p[0], -p[1]), (-n[0], -n[1])
    return p, n


def rrect_perimeter(a, b, rho):
    return 4 * (a - rho) + 4 * (b - rho) + 2 * math.pi * rho


def rrect_outline(a, b, rho, n=128):
    per = rrect_perimeter(a, b, rho)
    return [rrect_point(per * i / n, a, b, rho)[0] for i in range(n)]


def loft(name, rings, mat, cap_top=True, cap_bottom=True):
    """Closed solid through outlines of equal point count: rings = [(pts2d, z), ...] from bottom to top."""
    verts, faces = [], []
    n = len(rings[0][0])
    for pts, z in rings:
        verts += [(x, y, z) for x, y in pts]
    for k in range(len(rings) - 1):
        for i in range(n):
            i2 = (i + 1) % n
            faces.append((k * n + i, k * n + i2, (k + 1) * n + i2, (k + 1) * n + i))
    return verts, faces


def solid_between(name, inner, outer, z_top_fn, z_bot, mat, L):
    """Frame: region between two outlines (same point count), flat bottom at z_bot, top height per point index."""
    n = len(inner)
    verts, faces = [], []
    for i in range(n):
        zt = z_top_fn(i)
        verts += [(outer[i][0], outer[i][1], zt), (inner[i][0], inner[i][1], zt),
                  (inner[i][0], inner[i][1], z_bot), (outer[i][0], outer[i][1], z_bot)]
    for i in range(n):
        a, b = 4 * i, 4 * ((i + 1) % n)
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((a + k, b + k, b + k2, a + k2))
    ob = L.mesh_object(name, verts, faces, mat)
    L.fix_normals(ob)
    return ob


def claw(L, name, corner_xy, girdle_z, crown_h, mat):
    """Small faceted claw on a cut corner (img_00 / img_07: a pointed tab, not a ball)."""
    cx, cy = corner_xy
    out = Vector((cx, cy, 0)).normalized()
    side = Vector((-out.y, out.x, 0))
    g = Vector((cx, cy, girdle_z))
    pts = []
    # small tab (hero overlay: the bigger block read as a white cube next to the photo's small claws)
    for zo, off, w in ((-2.1, 0.32, 0.36), (0.0, 0.36, 0.36), (0.45, 0.24, 0.28)):   # base reaches the lowered halo frame
        c = g + out * off + Vector((0, 0, zo))
        pts += [c + side * w, c - side * w, c + out * 0.24 + side * w * 0.7, c + out * 0.24 - side * w * 0.7]
    tip = g - out * 0.22 + Vector((0, 0, crown_h * 0.48))
    pts += [tip + side * 0.17, tip - side * 0.17]
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = L.link(bpy.data.objects.new(name, me))
    me.materials.append(mat)
    L.fix_normals(ob)
    L.shade(ob, True, sharp_angle=35)
    return ob


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    sil = L.mat_silicone(bands[0], "Silicone_A")
    metal = L.mat_metal(metals[0])
    cz = L.mat_cz()

    prof = L.BandProfile(width=6.0, thickness=2.0, dome=0.5, inner_dome=0.12, edge_out=1.0, edge_in=0.45)
    band = L.band("band", prof, sil)
    r_top, girdle_z, halo_z = geometry()
    crown_h = CUT["crown"] * W

    # explicit crushed-ice brilliant (rinfit.brilliant merges facets on straight sides into big steps)
    stone = H.crushed(L, "stone", L.outline_rect(W, LEN, CORNER), cz, crown_h=crown_h, pav_d=4.3, table=0.62,
                      jitter=0.045, jitter_z=0.05,
                      crown_rings=((0.88, 1, 0.5), (0.75, 2, 0.0)),
                      pav_rings=((0.85, 1, 0.5), (0.62, 2, 0.0), (0.40, 4, 0.5), (0.18, 8, 0.0)))
    stone.location.z = girdle_z

    # ---- halo stones: one small brilliant copied round the rounded-rectangle centre line
    small = L.brilliant("pave_src", L.outline_ellipse(HALO_D, HALO_D, 32), cz, size_ref=HALO_D,
                        table=0.55, star=0.8, crown=0.16, pavilion=0.45, lower=0.3, sectors=8, pav_sectors=8)
    per = rrect_perimeter(HALO_A, HALO_B, HALO_RHO)
    pitch = per / HALO_N
    bm = bmesh.new()
    for k in range(HALO_N):
        (x, y), _ = rrect_point(k * pitch, HALO_A, HALO_B, HALO_RHO)
        me = small.data.copy()
        me.transform(Matrix.Translation((x, y, halo_z)))
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    pave_me = bpy.data.meshes.new("pave")
    bm.to_mesh(pave_me)
    bm.free()
    bpy.data.objects.remove(small, do_unlink=True)
    pave = L.link(bpy.data.objects.new("pave", pave_me))
    pave_me.materials.append(cz)
    L.shade(pave, False)

    # ---- halo frame (U-cut gallery): top dips under each stone, rises into a bead between stones
    NP = HALO_N * 12
    samples = [rrect_point(per * i / NP, HALO_A, HALO_B, HALO_RHO) for i in range(NP)]
    hw = HALO_D / 2 + 0.08
    inner = [(p[0] - n[0] * hw, p[1] - n[1] * hw) for p, n in samples]
    outer = [(p[0] + n[0] * hw, p[1] + n[1] * hw) for p, n in samples]
    z_frame_top = halo_z - 0.12
    z_frame_bot = halo_z - 1.0

    def ztop(i):
        t = (i / 12.0) % 1.0               # 0 at a stone centre, 0.5 between stones
        return z_frame_top - 0.38 * math.cos(math.pi * t) ** 2
    frame = solid_between("frame", inner, outer, ztop, z_frame_bot, metal, L)
    parts = [frame]
    # beads between the stones, on the outer and inner edge of the halo
    for k in range(HALO_N):
        (x, y), (nx, ny) = rrect_point((k + 0.5) * pitch, HALO_A, HALO_B, HALO_RHO)
        for side in (1, -1):
            off = side * (HALO_D / 2 - 0.02)
            parts.append(L.ellipsoid(f"bead{k}_{side}", (x + nx * off, y + ny * off, halo_z + 0.08),
                                     (0.17, 0.17, 0.19), mat=metal, subdivisions=2))
    # gallery wall from just under the centre girdle down to the inner edge of the halo frame
    wall_top = [rrect_point(per * i / NP, W / 2 - 0.02, LEN / 2 - 0.02, 0.55)[0] for i in range(NP)]
    wall_in_top = [(x * 0.965, y * 0.97) for x, y in wall_top]
    wall_in_bot = [(p[0] - n[0] * (hw + 0.12), p[1] - n[1] * (hw + 0.12)) for p, n in samples]
    verts, faces = [], []
    zt_w, zb_w = girdle_z - 0.85, z_frame_top - 0.05     # top well under the girdle: only a thin metal line shows
    for i in range(NP):
        verts += [(*wall_top[i], zt_w), (*inner[i], zb_w), (*wall_in_bot[i], zb_w), (*wall_in_top[i], zt_w)]
    for i in range(NP):
        a, b = 4 * i, 4 * ((i + 1) % NP)
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((a + k, b + k, b + k2, a + k2))
    wall = L.mesh_object("wall", verts, faces, metal)
    L.fix_normals(wall)
    parts.append(wall)
    # tapered skirt from the halo frame down into the band
    skirt_top = [(p[0] + n[0] * (hw - 0.05), p[1] + n[1] * (hw - 0.05)) for p, n in samples]
    bot_a, bot_b = 3.6, 2.4
    skirt_bot = [(x * bot_a / (HALO_A + hw), y * bot_b / (HALO_B + hw)) for x, y in skirt_top]
    skirt_in_top = [(x * 0.9, y * 0.9) for x, y in skirt_top]
    skirt_in_bot = [(x * 0.82, y * 0.82) for x, y in skirt_bot]
    zb = r_top - 0.6
    n = len(skirt_top)
    verts, faces = [], []
    for i in range(n):
        verts += [(*skirt_top[i], z_frame_bot + 0.02), (*skirt_in_top[i], z_frame_bot + 0.02),
                  (*skirt_in_bot[i], zb), (*skirt_bot[i], zb)]
    for i in range(n):
        a, b = 4 * i, 4 * ((i + 1) % n)
        for k in range(4):
            k2 = (k + 1) % 4
            faces.append((a + k, b + k, b + k2, a + k2))
    skirt = L.mesh_object("skirt", verts, faces, metal)
    L.fix_normals(skirt)
    parts.append(skirt)

    outline = L.outline_rect(W, LEN, CORNER)
    # chamfer middles (outline_rect puts them at j = 4, 20, 36, 52, not 8, 24, 40, 56 as its docstring says)
    tgt = [(sx * (W / 2 - CORNER / 2), sy * (LEN / 2 - CORNER / 2)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    idx = [min(range(len(outline)), key=lambda j: (outline[j][0] - x) ** 2 + (outline[j][1] - y) ** 2) for x, y in tgt]
    claws = [claw(L, f"claw{j}", outline[j], girdle_z, crown_h, metal) for j in idx]
    setting = L.join(parts + claws, "metal", metal, smooth=True, sharp_angle=40)

    L.engrave(band, prof, "RINFIT", phi_center=math.pi, size=3.8, depth=0.24, spacing=1.10, on_inner=True)
    H.drop_empty_slots(band)      # the boolean leaves an unused empty material slot (would reach the GLB)
    L.shade(band, True, sharp_angle=50)
    return [band, stone, pave, setting]
