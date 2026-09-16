"""Rinfit ring modelling library for Blender 5.x (run headless through build.py).

Units: 1 Blender unit = 1 mm.
Modelling frame: ring axis = +Y (along the finger), stone side = +Z (phi = 0), X across the finger.
Angle phi goes round the ring from +Z towards +X.
export_glb() rotates everything into the web app frame (glTF +Y along the finger, +Z towards the stone).

Object/material naming contract with the web app (app.js):
  materials "Silicone_A" / "Silicone_B"  -> recoloured from the variant (first / second band colour)
  material  "Metal"                       -> Silver or Rose Gold from the variant
  materials "CZ" / "CZ_Black"             -> replaced by the realtime gem shader
"""
import bpy, bmesh, math, os
from mathutils import Vector, Matrix

BLENDER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BLENDER_DIR)
FONT_DIR = os.path.join(BLENDER_DIR, "fonts")
REF_DIR = os.path.join(BLENDER_DIR, "ref")
OUT_DIR = os.path.join(BLENDER_DIR, "out")
R_IN = 17.32 / 2   # US size 7 inner radius (Rinfit size chart)

# Colours sampled from the variant photos (kept in sync with catalog.js)
SILICONE = {
    "White": "#ebebec", "Black": "#1e1e20", "Nude": "#dcc9b4", "Pink": "#f2d2d1",
    "Orchid Ice": "#e8dce3", "Soft Blue": "#d2dce7", "Teal Ocean": "#21646d", "Ocean": "#2a6a74",
    "Red": "#c21f30", "Olive": "#4f5530", "Blue": "#2f3ea8", "Light Gray": "#a6a7a9",
    "Steel Blue": "#4d6a86", "Burgundy": "#9d5784", "Grayish Green": "#a3c1b7", "Pastel Pink": "#e3abbb",
    "Pastel Peach": "#deb6a6", "Pastel Purple": "#d3b7eb", "Grayish Purple": "#827b89",
    "Turquoise": "#5ccdbb", "Frosted Clear": "#eef2f3",
}
METAL = {"Silver": "#e2e3e6", "Rose Gold": "#e7ab93"}


def parse_color(name):
    """'Black and White Silver' -> (['Black', 'White'], ['Silver', 'Silver'])"""
    parts = []
    for p in [s.strip() for s in name.split(" and ")]:
        metal = None
        for m in ("Rose Gold", "Silver"):
            if p.endswith(m):
                metal, p = m, p[: -len(m)].strip()
        parts.append([p, metal])
    metal = "Silver"
    for part in reversed(parts):
        if part[1]:
            metal = part[1]
        else:
            part[1] = metal
    parts = [p for p in parts if p[0]]
    return [p[0] for p in parts], [p[1] for p in parts]


def hex_lin(h, alpha=True):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*c, 1.0) if alpha else tuple(c)


# ---------------------------------------------------------------- scene

def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras, bpy.data.worlds, bpy.data.node_groups):
        for x in list(coll):
            coll.remove(x)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"
    return sc


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mesh_object(name, verts, faces, mat=None, smooth=False, sharp_angle=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    ob = link(bpy.data.objects.new(name, me))
    if mat:
        me.materials.append(mat)
    shade(ob, smooth, sharp_angle)
    return ob


def shade(ob, smooth=True, sharp_angle=None):
    me = ob.data
    if smooth:
        me.shade_smooth()
        if sharp_angle is not None:
            me.set_sharp_from_angle(angle=math.radians(sharp_angle))
    else:
        me.shade_flat()


def fix_normals(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def bake(ob):
    """Apply modifiers and object transform into the mesh data."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    me.transform(ob.matrix_world)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    ob.matrix_world = Matrix.Identity(4)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def join(objs, name, mat=None, smooth=None, sharp_angle=None):
    """Merge several objects (world space) into one mesh object."""
    bm = bmesh.new()
    for ob in objs:
        bake(ob)
        bm.from_mesh(ob.data)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    mats = [m for ob in objs for m in ob.data.materials]
    for ob in objs:
        bpy.data.objects.remove(ob, do_unlink=True)
    out = link(bpy.data.objects.new(name, me))
    me.materials.clear()
    me.materials.append(mat or (mats[0] if mats else None))
    for p in me.polygons:
        p.material_index = 0
    if smooth is not None:
        shade(out, smooth, sharp_angle)
    return out


def boolean(target, tool, op="DIFFERENCE", keep_tool=False):
    mod = target.modifiers.new("bool", "BOOLEAN")
    mod.operation = op
    mod.solver = "EXACT"
    mod.object = tool
    tool.hide_render = True
    bake(target)
    if not keep_tool:
        bpy.data.objects.remove(tool, do_unlink=True)
    return target


# ---------------------------------------------------------------- 2D profiles

def resample(points, n, closed=True):
    pts = [Vector((p[0], p[1])) for p in points]
    if closed:
        pts.append(pts[0].copy())
    seg = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seg)
    out, i, acc = [], 0, 0.0
    for k in range(n if closed else n + 1):
        target = total * k / n
        while i < len(seg) - 1 and acc + seg[i] < target:
            acc += seg[i]
            i += 1
        f = (target - acc) / seg[i] if seg[i] > 1e-12 else 0.0
        q = pts[i].lerp(pts[i + 1], min(1.0, max(0.0, f)))
        out.append((q.x, q.y))
    return out


def _bezier2(a, c, b, n=10):
    return [((1 - t) ** 2 * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0],
             (1 - t) ** 2 * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]) for t in (i / n for i in range(n + 1))]


class BandProfile:
    """Closed cross-section of a silicone band in (r, y).

    width, thickness : from the product page (mm)
    dome             : how much the outer surface drops from the centre line to the edges (mm)
    inner_dome       : comfort-fit, how much the inner surface moves away from the finger at the edges (mm)
    edge_out/edge_in : fillet size of the outer / inner corners (mm)
    """

    def __init__(self, width, thickness=2.0, dome=0.3, inner_dome=0.1, edge_out=0.6, edge_in=0.35,
                 inner=R_IN, dome_power=2.0, samples=96):
        self.width, self.thickness, self.inner = width, thickness, inner
        self.dome, self.inner_dome, self.dome_power = dome, inner_dome, dome_power
        b = width / 2
        side = (self.outer_r(b) - self.inner_r(b))
        edge_out = min(edge_out, b * 0.98)
        edge_in = min(edge_in, b * 0.98)
        k = min(1.0, side * 0.999 / max(1e-6, edge_out + edge_in))
        eo, ei = edge_out * k, edge_in * k
        N = 60
        pts = []
        # outer curve, y from -b to +b
        ys = [-b + eo + (2 * b - 2 * eo) * i / N for i in range(N + 1)]
        outer = [(self.outer_r(y), y) for y in ys]
        inner_pts = [(self.inner_r(y), y) for y in reversed([-b + ei + (2 * b - 2 * ei) * i / N for i in range(N + 1)])]
        c_ot, c_it = (self.outer_r(b), b), (self.inner_r(b), b)
        c_ib, c_ob = (self.inner_r(-b), -b), (self.outer_r(-b), -b)
        pts += outer
        pts += _bezier2(outer[-1], c_ot, (c_ot[0] - eo, b))[1:]
        pts += _bezier2((c_it[0] + ei, b), c_it, inner_pts[0])
        pts += inner_pts[1:]
        pts += _bezier2(inner_pts[-1], c_ib, (c_ib[0] + ei, -b))[1:]
        pts += _bezier2((c_ob[0] - eo, -b), c_ob, outer[0])[:-1]
        self.points = resample(pts, samples)

    def outer_r(self, y):
        return self.inner + self.thickness - self.dome * (abs(y) / (self.width / 2)) ** self.dome_power

    def inner_r(self, y):
        return self.inner + self.inner_dome * (abs(y) / (self.width / 2)) ** 2


def revolve(name, profile_pts, segments=192, mat=None, y_of_phi=None, smooth=True):
    """Spin a (r, y) profile round the Y axis. y_of_phi shifts the section along the finger (V bands)."""
    n = len(profile_pts)
    verts, faces = [], []
    for i in range(segments):
        phi = 2 * math.pi * i / segments
        dy = y_of_phi(phi) if y_of_phi else 0.0
        s, c = math.sin(phi), math.cos(phi)
        for r, y in profile_pts:
            verts.append((r * s, y + dy, r * c))
    for i in range(segments):
        i2 = (i + 1) % segments
        for j in range(n):
            j2 = (j + 1) % n
            faces.append((i * n + j, i * n + j2, i2 * n + j2, i2 * n + j))
    ob = mesh_object(name, verts, faces, mat, smooth)
    fix_normals(ob)
    return ob


def band(name, profile, mat, segments=192, y_offset=0.0, y_of_phi=None):
    prof = [(r, y + y_offset) for r, y in profile.points]
    ob = revolve(name, prof, segments, mat, y_of_phi)
    ob["band_width"] = profile.width
    return ob


# ---------------------------------------------------------------- lettering

def text_mesh(text, font="Montserrat-SemiBold.ttf", size=2.0, spacing=1.0, depth=1.0, resolution=5):
    """Extruded text as a mesh, centred on its bounding box, lying in XY (x = reading direction)."""
    cu = bpy.data.curves.new("text", "FONT")
    cu.body = text
    cu.font = bpy.data.fonts.load(os.path.join(FONT_DIR, font), check_existing=True)
    cu.size = size
    cu.space_character = spacing
    cu.extrude = depth / 2
    cu.resolution_u = resolution
    cu.fill_mode = "BOTH"
    ob = link(bpy.data.objects.new("text", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    me.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, 0)))
    return me


def wrap_on_band(me, profile, phi_center, y_center=0.0, below=0.25, above=0.6, on_inner=False, rotate=0.0,
                 y_of_phi=None):
    """Bend a flat XY mesh round the band surface.
    Text x runs round the ring (increasing phi), text y along the finger (+Y).
    The solid spans from `below` under the surface to `above` over it (for booleans).
    on_inner mirrors x (phi = phi_center - x/r) so lettering reads correctly when you look INTO the ring;
    a mark drawn for an outer face therefore comes out mirrored inside - flip it in the source mesh."""
    zs = [v.co.z for v in me.vertices]
    z0, z1 = min(zs), max(zs)
    cr, sr = math.cos(rotate), math.sin(rotate)
    for v in me.vertices:
        x, y = v.co.x * cr - v.co.y * sr, v.co.x * sr + v.co.y * cr
        t = (v.co.z - z0) / max(1e-9, z1 - z0)
        if on_inner:
            rs = profile.inner_r(y_center + y)
            r = rs + below - t * (below + above)
            phi = phi_center - x / rs
        else:
            rs = profile.outer_r(y_center + y)
            r = rs - below + t * (below + above)
            phi = phi_center + x / rs
        yy = y_center + y + (y_of_phi(phi) if y_of_phi else 0.0)
        v.co = (r * math.sin(phi), yy, r * math.cos(phi))
    ob = link(bpy.data.objects.new("wrap", me))
    return ob


def engrave(band_ob, profile, text, phi_center, size=2.0, depth=0.18, emboss=False, y_center=0.0,
            font="Montserrat-SemiBold.ttf", spacing=1.0, on_inner=False, rotate=0.0, y_of_phi=None):
    me = text_mesh(text, font, size, spacing, depth=1.0)
    if emboss:
        tool = wrap_on_band(me, profile, phi_center, y_center, below=0.3, above=depth, on_inner=on_inner,
                            rotate=rotate, y_of_phi=y_of_phi)
        return boolean(band_ob, tool, "UNION")
    tool = wrap_on_band(me, profile, phi_center, y_center, below=depth, above=0.6, on_inner=on_inner,
                        rotate=rotate, y_of_phi=y_of_phi)
    return boolean(band_ob, tool, "DIFFERENCE")


# ---------------------------------------------------------------- stones

GIRDLE_N = 64   # girdle points of every stone outline (multiple of 16)


def outline_ellipse(w, l, n=GIRDLE_N):
    return [(w / 2 * math.cos(2 * math.pi * j / n), l / 2 * math.sin(2 * math.pi * j / n)) for j in range(n)]


def outline_marquise(w, l, n=GIRDLE_N):
    """Vesica (two circular arcs). j = 0 at +X, tips at j = n/4 (+Y) and 3n/4 (-Y)."""
    q = n // 4
    cx = (w * w - l * l) / (4 * w)
    R = w / 2 - cx
    a0 = math.atan2(l / 2, -cx)
    right = [(cx + R * math.cos(a0 * i / q), R * math.sin(a0 * i / q)) for i in range(q + 1)]
    # one quarter per side, each traversed counter-clockwise: mirroring the whole upper half instead
    # walks the lower half backwards and the stone comes out self-intersecting
    return (right[:q] + [(-x, y) for x, y in reversed(right)][:q]
            + [(-x, -y) for x, y in right][:q] + [(x, -y) for x, y in reversed(right)][:q])


def outline_pear(w, l, n=GIRDLE_N, belly=0.0):
    """Round end at -Y, point at +Y (j = n/4). belly moves the widest point towards the tip (mm)."""
    q = n // 4
    r = w / 2
    yc = -l / 2 + r + belly
    Rs = (r * r + (l / 2 - yc) ** 2) / w
    cxr = r - Rs
    a_tip = math.atan2(l / 2 - yc, 0 - cxr)
    right = [(cxr + Rs * math.cos(a_tip * i / q), yc + Rs * math.sin(a_tip * i / q)) for i in range(q + 1)]
    pts = right[:-1] + [(-x, y) for x, y in reversed(right)][:-1]
    for i in range(n // 2):   # round end, from (-r, yc) through -Y back to (r, yc)
        a = math.pi + math.pi * i / (n // 2)
        pts.append((r * math.cos(a), yc + r * math.sin(a)))
    return pts


def outline_rect(w, l, corner=0.6, n=GIRDLE_N):
    """Rectangle with cut corners. j = 0 at the middle of the +X side; corners (chamfer middles) at j = n/8 + k*n/4."""
    c = max(corner, 0.04)
    hw, hl = w / 2, l / 2
    poly = [(hw, -hl + c), (hw, hl - c), (hw - c, hl), (-hw + c, hl), (-hw, hl - c), (-hw, -hl + c), (-hw + c, -hl), (hw - c, -hl)]
    side, cham = 3 * n // 16, n // 16
    segs = [side, cham] * 4
    pts = []
    for i, (a, b) in enumerate(zip(poly, poly[1:] + poly[:1])):
        for s in range(segs[i]):
            pts.append((a[0] + (b[0] - a[0]) * s / segs[i], a[1] + (b[1] - a[1]) * s / segs[i]))
    k = side // 2
    return pts[-k:] + pts[:-k] if k else pts


def _plane_z(p0, p1, d, xy):
    n = (p1 - p0).cross(d)
    if abs(n.z) < 1e-9:
        return p0.z
    return p0.z - (n.x * (xy[0] - p0.x) + n.y * (xy[1] - p0.y)) / n.z


def _plane3_z(a, b, c, xy):
    n = (b - a).cross(c - a)
    if abs(n.z) < 1e-9:
        return a.z
    return a.z - (n.x * (xy[0] - a.x) + n.y * (xy[1] - a.y)) / n.z


def brilliant(name, girdle, mat, size_ref, table=0.53, star=0.78, crown=0.15, pavilion=0.50, lower=0.22,
              girdle_h=0.022, sectors=16, pav_sectors=16, phase=0):
    """Brilliant-style stone on any closed girdle outline (counter-clockwise, len = multiple of 16, centre at 0).

    Crown: table, `sectors` star + bezel facets, 2*sectors upper-girdle facets.
    Pavilion: `pav_sectors` main facets, 2*pav_sectors lower-girdle facets, culet point.
    Every facet is a true plane: the girdle edge gets the scalloped shape of a real cut stone.
    Heights are fractions of size_ref (the smaller stone dimension). Table up (+Z), girdle centred on z = 0.
    phase shifts the facet pattern round the outline (in girdle points)."""
    n = len(girdle)
    G = [Vector((girdle[(j + phase) % n][0], girdle[(j + phase) % n][1], 0)) for j in range(n)]
    g2 = girdle_h * size_ref / 2
    ch, pd = crown * size_ref, pavilion * size_ref
    zt = g2 + ch
    C = Vector((0, 0, -g2 - pd))
    tan = [(G[(j + 1) % n] - G[(j - 1) % n]).normalized() for j in range(n)]

    def ring_top(j):
        return Vector((G[j].x, G[j].y, g2))

    def ring_bot(j):
        return Vector((G[j].x, G[j].y, -g2))

    cs, ch_half = n // sectors, n // sectors // 2
    T = [Vector((G[cs * k + ch_half].x * table, G[cs * k + ch_half].y * table, zt)) for k in range(sectors)]
    S = []
    for k in range(sectors):
        j = cs * k
        xy = (G[j].x * star, G[j].y * star)
        zs = [_plane_z(T[(k - 1) % sectors], ring_top((j - ch_half) % n), tan[(j - ch_half) % n], xy),
              _plane_z(T[k], ring_top((j + ch_half) % n), tan[(j + ch_half) % n], xy)]
        S.append(Vector((xy[0], xy[1], sum(zs) / 2)))
    ps, ph = n // pav_sectors, n // pav_sectors // 2
    Lp = []
    for m in range(pav_sectors):
        j = ps * m
        xy = (G[j].x * lower, G[j].y * lower)
        zs = [_plane_z(C, ring_bot((j - ph) % n), tan[(j - ph) % n], xy),
              _plane_z(C, ring_bot((j + ph) % n), tan[(j + ph) % n], xy)]
        Lp.append(Vector((xy[0], xy[1], sum(zs) / 2)))

    # scalloped girdle: points inside an upper/lower girdle facet lie on that facet's plane
    top = [ring_top(j) for j in range(n)]
    bot = [ring_bot(j) for j in range(n)]
    for k in range(sectors):
        j = cs * k
        for j0 in (j - ch_half, j):
            a, b = ring_top(j0 % n), ring_top((j0 + ch_half) % n)
            for i in range(1, ch_half):
                jj = (j0 + i) % n
                top[jj].z = max(-g2 * 0.4, _plane3_z(S[k], a, b, (G[jj].x, G[jj].y)))
    for m in range(pav_sectors):
        j = ps * m
        for j0 in (j - ph, j):
            a, b = ring_bot(j0 % n), ring_bot((j0 + ph) % n)
            for i in range(1, ph):
                jj = (j0 + i) % n
                bot[jj].z = min(g2 * 0.4, _plane3_z(Lp[m], a, b, (G[jj].x, G[jj].y)))
    for j in range(n):
        if top[j].z < bot[j].z + 0.01:
            top[j].z = bot[j].z + 0.01

    verts, faces = [], []

    def face(*pts):
        base = len(verts)
        verts.extend(pts)
        faces.append(tuple(range(base, base + len(pts))))

    face(*T)
    for k in range(sectors):
        j = cs * k
        face(T[(k - 1) % sectors], S[k], T[k])                                     # star
        face(T[k], S[k], top[(j + ch_half) % n], S[(k + 1) % sectors])             # bezel (kite)
        face(S[k], *[top[(j - ch_half + i) % n] for i in range(ch_half + 1)])       # upper girdle, left
        face(S[k], *[top[(j + i) % n] for i in range(ch_half + 1)])                 # upper girdle, right
    for m in range(pav_sectors):
        j = ps * m
        face(bot[(j + ph) % n], Lp[m], C, Lp[(m + 1) % pav_sectors])              # pavilion main (kite)
        face(Lp[m], *[bot[(j - ph + i) % n] for i in range(ph + 1)])                # lower girdle, left
        face(Lp[m], *[bot[(j + i) % n] for i in range(ph + 1)])                     # lower girdle, right
    for j in range(n):
        face(top[j], bot[j], bot[(j + 1) % n], top[(j + 1) % n])                   # girdle
    ob = mesh_object(name, verts, faces, mat, smooth=False)
    fix_normals(ob)
    shade(ob, False)
    return ob


# ---------------------------------------------------------------- metal parts

def tube(name, points, radius, radii=None, closed=False, mat=None, resolution=4, handles="AUTO", caps=True):
    """Smooth round wire through points (Bezier with automatic handles). radii: per-point radius factors."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = resolution
    cu.use_fill_caps = caps
    cu.resolution_u = 10
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for i, p in enumerate(points):
        bp = sp.bezier_points[i]
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = handles
        bp.radius = radii[i] if radii else 1.0
    sp.use_cyclic_u = closed
    ob = link(bpy.data.objects.new(name, cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.curves.remove(cu)
    out = link(bpy.data.objects.new(name, me))
    if mat:
        me.materials.append(mat)
    shade(out, True)
    return out


def ellipsoid(name, center, radii, axis=(0, 0, 1), mat=None, subdivisions=4):
    """Ellipsoid with radii (rx, ry, rz); its local Z is turned to `axis`.
    Icosphere, not UV sphere: a UV pole facing the camera shows radial shading streaks on polished claw tips."""
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1.0)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    rot = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
    me.transform(Matrix.Translation(center) @ rot @ Matrix.Diagonal((*radii, 1)))
    ob = link(bpy.data.objects.new(name, me))
    if mat:
        me.materials.append(mat)
    shade(ob, True)
    return ob


def prong(name, base, girdle_point, stone_center_xy, crown_h, mat, radius=0.45, tip=(0.62, 0.62, 0.85),
          lean=0.35, tip_height=0.55):
    """Claw from `base` up to the girdle and over the crown edge, finished with a rounded (tear-drop) tip.
    girdle_point: Vector on the stone outline at girdle height. tip: ellipsoid radii (across, around, along)."""
    g = Vector(girdle_point)
    out = Vector((g.x - stone_center_xy[0], g.y - stone_center_xy[1], 0))
    out = out.normalized() if out.length > 1e-6 else Vector((1, 0, 0))
    b = Vector(base)
    p_mid = g + out * radius * 0.9 + Vector((0, 0, -(g.z - b.z) * 0.35))
    p_g = g + out * radius * 0.85
    p_tip = g - out * lean + Vector((0, 0, crown_h * tip_height))
    # The wire must end deep inside the tip: its flat end cap pokes through the ellipsoid as a dent or a second disc
    # unless it stops within ~0.25 mm of the tip centre (cap radius = wire radius).
    axis = (p_tip - p_g).normalized()
    parts = [tube(name + "_wire", [b, p_mid, p_g, p_tip - axis * 0.25], radius, mat=mat)]
    parts.append(ellipsoid(name + "_tip", p_tip, (tip[0], tip[1], tip[2]), axis, mat))
    return parts


def rail(name, outline, z, radius, scale=1.0, mat=None, center=(0, 0)):
    pts = [Vector((center[0] + x * scale, center[1] + y * scale, z)) for x, y in outline]
    return tube(name, pts, radius, closed=True, mat=mat)


# ---------------------------------------------------------------- materials

def _principled(mat):
    return mat.node_tree.nodes.get("Principled BSDF")


def mat_silicone(color_name_or_hex, name="Silicone_A", roughness=0.5, frosted=False):
    hexv = SILICONE.get(color_name_or_hex, color_name_or_hex)
    m = bpy.data.materials.new(name)
    p = _principled(m)
    p.inputs["Base Color"].default_value = hex_lin(hexv)
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Specular IOR Level"].default_value = 0.35
    p.inputs["Coat Weight"].default_value = 0.0
    p.inputs["Subsurface Weight"].default_value = 0.12
    p.inputs["Subsurface Radius"].default_value = hex_lin(hexv, False)
    p.inputs["Subsurface Scale"].default_value = 0.4
    if frosted:
        p.inputs["Transmission Weight"].default_value = 0.85
        p.inputs["Roughness"].default_value = 0.42
        p.inputs["Subsurface Weight"].default_value = 0.0
        p.inputs["IOR"].default_value = 1.41
    m.diffuse_color = hex_lin(hexv)
    return m


def mat_metal(metal="Silver", name="Metal", roughness=0.3):
    # 0.3: polished but soft, as on Rinfit renders; sharper metal mirrors the tent cards as radial spokes on claw tips
    m = bpy.data.materials.new(name)
    p = _principled(m)
    p.inputs["Base Color"].default_value = hex_lin(METAL.get(metal, metal))
    p.inputs["Metallic"].default_value = 1.0
    p.inputs["Roughness"].default_value = roughness
    return m


def mat_cz(name="CZ", ior=2.16, film=0.0):
    """Cubic zirconia: one clear glass lobe (keeps energy through many internal reflections)
    with a faint thin-film layer for the rainbow flashes seen in Rinfit renders.
    Splitting into R/G/B glass lobes looks like dispersion but kills light on every bounce -> grey stones."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    g = nt.nodes.new("ShaderNodeBsdfGlass")
    g.inputs["Color"].default_value = (1, 1, 1, 1)
    g.inputs["Roughness"].default_value = 0.0
    g.inputs["IOR"].default_value = ior
    if film:
        g.inputs["Thin Film Thickness"].default_value = film
        g.inputs["Thin Film IOR"].default_value = 1.45
    nt.links.new(g.outputs[0], out.inputs["Surface"])
    m.diffuse_color = (0.95, 0.95, 1.0, 1)
    return m


def mat_cz_black(name="CZ_Black"):
    m = bpy.data.materials.new(name)
    p = _principled(m)
    p.inputs["Base Color"].default_value = (0.004, 0.004, 0.005, 1)
    p.inputs["Roughness"].default_value = 0.015
    p.inputs["IOR"].default_value = 2.16
    p.inputs["Specular IOR Level"].default_value = 0.5
    return m


# ---------------------------------------------------------------- studio, camera, render

def studio(env_strength=1.0, env="tent", env_rotation=0.0, softboxes=True, key=2.0, diffuse_level=0.9, tent=None,
           bounce=0.0, bounce_depth=12.0):
    """White product studio: world for reflections (light tent, gradient or HDRI) + large emissive softboxes.
    diffuse_level dims the world for diffuse bounces only, so matte silicone keeps soft shading
    while stones and metal still see the bright tent."""
    sc = bpy.context.scene
    w = bpy.data.worlds.new("Studio")
    sc.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    lp = nt.nodes.new("ShaderNodeLightPath")
    dim = nt.nodes.new("ShaderNodeMath")
    dim.operation = "MULTIPLY"
    dim.inputs[1].default_value = 1.0 - diffuse_level
    nt.links.new(lp.outputs["Is Diffuse Ray"], dim.inputs[0])
    strength = nt.nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    one_minus = nt.nodes.new("ShaderNodeMath")
    one_minus.operation = "SUBTRACT"
    one_minus.inputs[0].default_value = 1.0
    nt.links.new(dim.outputs[0], one_minus.inputs[1])
    nt.links.new(one_minus.outputs[0], strength.inputs[0])
    strength.inputs[1].default_value = env_strength
    nt.links.new(strength.outputs[0], bg.inputs["Strength"])
    if env == "tent":
        _tent_world(nt, bg, env_rotation, **(tent or {}))
    elif env == "gradient":
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = -1
        mr.inputs["From Max"].default_value = 1
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
        el = ramp.color_ramp.elements
        el[0].position, el[0].color = 0.0, (0.02, 0.02, 0.022, 1)
        el[1].position, el[1].color = 1.0, (1, 1, 1, 1)
        e = el.new(0.48)
        e.color = (0.25, 0.25, 0.26, 1)
        e = el.new(0.56)
        e.color = (0.85, 0.85, 0.86, 1)
        nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    else:
        path = env if os.path.isabs(env) else os.path.join(bpy.utils.system_resource("DATAFILES"), "studiolights", "world", env)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Rotation"].default_value[2] = env_rotation
        tex = nt.nodes.new("ShaderNodeTexEnvironment")
        tex.image = bpy.data.images.load(path, check_existing=True)
        hs = nt.nodes.new("ShaderNodeHueSaturation")   # neutral studio: no colour cast on white silicone
        hs.inputs["Saturation"].default_value = 0.0
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], hs.inputs["Color"])
        nt.links.new(hs.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    lights = []
    if bounce:
        # white sweep under the product (like the table of a light tent): stones and metal need a bright lower
        # hemisphere, the dark bottom of studio.exr turns CZ grey. Invisible to the camera, casts no shadows.
        card = softbox("bounce", (0, 0, -bounce_depth), (900, 900), bounce, target=(0, 0, 0))
        lights.append(card)
    if softboxes:
        for nm, loc, size, strength in (
            ("key", (60, -80, 140), (120, 90), key),
            ("fill", (-150, -40, 60), (80, 140), key * 0.45),
            ("rim", (90, 140, 80), (60, 140), key * 0.6),
            ("top", (0, 0, 220), (160, 160), key * 0.35),
        ):
            lights.append(softbox(nm, loc, size, strength))
    return lights


def _tent_world(nt, bg, rotation=0.0, cards=18, card_width=0.45, horizon=0.6, floor_gray=0.9, top=1.4, zenith=0.25):
    # defaults picked by lighting sweeps against Rinfit's oval render ("L4", then contrast "C3"): white CZ with a dark
    # bow-tie and crisp dark facets, silicone keeps soft grey shading
    """Jewellery light tent: bright surroundings, thin dark vertical cards round the horizon, grey floor.
    Gives CZ the white body with crisp dark facet accents seen in Rinfit renders."""
    N = nt.nodes
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])

    def math_node(op, a, b=None, value=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, src in enumerate((a, b)):
            if src is None:
                continue
            if isinstance(src, (int, float)):
                n.inputs[i].default_value = src
            else:
                nt.links.new(src, n.inputs[i])
        return n.outputs[0]

    az = math_node("ARCTAN2", sep.outputs["Y"], sep.outputs["X"])
    az = math_node("ADD", az, rotation)
    wave = math_node("SINE", math_node("MULTIPLY", az, cards / 2.0))
    card = math_node("GREATER_THAN", wave, 1.0 - card_width)               # dark vertical cards
    band = math_node("LESS_THAN", math_node("ABSOLUTE", sep.outputs["Z"]), horizon)
    # Cards only for light leaving a stone (transmission rays) - that is what draws the dark facets in CZ.
    # Polished metal (glossy rays) sees a smooth studio instead: on a round claw tip the cards turn into radial spokes.
    lp = N.new("ShaderNodeLightPath")
    trans = lp.outputs["Is Transmission Ray"]
    dark_cards = math_node("MULTIPLY", math_node("MULTIPLY", card, band), trans)
    soft_band = math_node("MULTIPLY", math_node("MULTIPLY", band, math_node("SUBTRACT", 1.0, trans)), 0.35)
    dark = math_node("ADD", math_node("MULTIPLY", dark_cards, 0.97), soft_band)
    floor = math_node("LESS_THAN", sep.outputs["Z"], -horizon)
    bright = math_node("SUBTRACT", top, math_node("MULTIPLY", floor, top - floor_gray))
    val = math_node("MULTIPLY", bright, math_node("SUBTRACT", 1.0, dark))
    if zenith:   # dark disc straight above (camera and its stand reflected in the table)
        cap = math_node("GREATER_THAN", sep.outputs["Z"], 1.0 - zenith)
        val = math_node("MULTIPLY", val, math_node("SUBTRACT", 1.0, math_node("MULTIPLY", cap, 0.96)))
    nt.links.new(val, bg.inputs["Color"])


def softbox(name, location, size, strength, target=(0, 0, 0), visible_camera=False):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new(name, me))
    ob.scale = (size[0], size[1], 1)
    loc = Vector(location)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - loc).to_track_quat("Z", "Y").to_euler()
    ob.rotation_euler.rotate_axis("X", math.pi)   # face the target
    m = bpy.data.materials.new(name + "_emit")
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], o.inputs["Surface"])
    me.materials.append(m)
    ob.visible_camera = visible_camera
    ob.visible_shadow = False
    return ob


def camera(direction=(0, -1, 0.35), up=(0, 0, 1), target=(0, 0, 0), dist=160.0, lens=100.0, ortho_scale=None):
    """Camera placed at target + direction * dist, looking at target."""
    d = Vector(direction).normalized()
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = lens
    cam_data.sensor_width = 36
    cam_data.clip_start = 1
    cam_data.clip_end = 5000
    if ortho_scale:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho_scale
    ob = link(bpy.data.objects.new("cam", cam_data))
    fwd = -d
    right = fwd.cross(Vector(up)).normalized()
    upv = right.cross(fwd).normalized()
    m = Matrix((right, upv, d)).transposed().to_4x4()
    m.translation = Vector(target) + d * dist
    ob.matrix_world = m
    bpy.context.scene.camera = ob
    return ob


def frame_camera(cam, objs, margin=1.08):
    """Move the camera along its axis so the objects fill the frame."""
    import bpy_extras
    sc = bpy.context.scene
    pts = [ob.matrix_world @ Vector(c) for ob in objs for c in ob.bound_box]
    center = sum(pts, Vector()) / len(pts)
    d = cam.matrix_world.to_3x3() @ Vector((0, 0, 1))
    for _ in range(4):
        cam.matrix_world.translation = center + d * (cam.matrix_world.translation - center).length
        bpy.context.view_layer.update()
        cs = [bpy_extras.object_utils.world_to_camera_view(sc, cam, p) for p in pts]
        ext = max(max(abs(c.x - 0.5), abs(c.y - 0.5)) for c in cs) * 2
        dist = (cam.matrix_world.translation - center).length
        cam.matrix_world.translation = center + d * dist * ext * margin
        bpy.context.view_layer.update()
    return cam


def shadow_floor(z, size=400):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    me = bpy.data.meshes.new("floor")
    bm.to_mesh(me)
    bm.free()
    ob = link(bpy.data.objects.new("floor", me))
    ob.location.z = z
    ob.is_shadow_catcher = True
    return ob


def render(path, res=1000, samples=192, transparent=True, gpu=True, res_y=None):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    if gpu:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == "METAL"
        sc.cycles.device = "GPU"
    cy = sc.cycles
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.use_denoising = True
    cy.max_bounces = 32
    cy.transmission_bounces = 32
    cy.glossy_bounces = 16
    cy.diffuse_bounces = 3
    cy.transparent_max_bounces = 16
    cy.caustics_reflective = True
    cy.caustics_refractive = True
    cy.blur_glossy = 0.2
    cy.sample_clamp_indirect = 30
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.render.film_transparent = transparent
    sc.render.resolution_x = res
    sc.render.resolution_y = res_y or res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.render.filepath = path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.render.render(write_still=True)
    return path


EXPORT_ROT = Matrix.Rotation(math.radians(90), 4, "X")   # modelling frame -> glTF app frame


def export_glb(objs, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for ob in objs:
        bake(ob)
        ob.data.transform(EXPORT_ROT)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_texcoords=False, export_normals=True,
                              export_cameras=False, export_lights=False, export_extras=True)
    for ob in objs:
        ob.data.transform(EXPORT_ROT.inverted())
    return path
