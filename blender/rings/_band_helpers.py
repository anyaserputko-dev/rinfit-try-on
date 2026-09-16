"""Helpers shared by couture.py, infinity_men.py and step_edge.py (plain silicone bands).

- svg_mesh(): the real Rinfit wordmark (blender/fonts/rinfit_logo.svg, downloaded from rinfit.com) as a flat mesh
- rect_union_mesh(): outline of a union of axis-aligned rectangles (logo marks drawn on a square grid)
- profile_band(): revolve any closed (r, y) polyline with an r(y) function for wrap_on_band
- loops_mesh(max_seg): resampled outlines so wrapped tool caps follow the band curvature
"""
import bpy, bmesh, math, os
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(os.path.dirname(HERE), "fonts")
LOGO_SVG = os.path.join(FONT_DIR, "rinfit_wordmark_ring.svg")   # ring lettering (R with stem); rinfit_logo.svg = website original


def _curve_to_mesh(cu, name="flat"):
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob, do_unlink=True)
    return me


def signed_volume(me):
    v = 0.0
    for p in me.polygons:
        vs = [me.vertices[i].co for i in p.vertices]
        for k in range(1, len(vs) - 1):
            v += vs[0].dot(vs[k].cross(vs[k + 1])) / 6
    return v


def orient_outward(me):
    """Make a closed tool solid point outwards (by signed volume). Curve fill gives some glyphs inside-out
    (the R of the wordmark), which the EXACT boolean silently ignores. Do NOT weld/recalc normals:
    welding the unwelded curve output makes EXACT drop the whole band."""
    if signed_volume(me) < 0:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    return me


def center_scale(me, height=None, width=None):
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    me.transform(Matrix.Translation((-(min(xs) + max(xs)) / 2, -(min(ys) + max(ys)) / 2, 0)))
    if height or width:
        s = height / (max(ys) - min(ys)) if height else width / (max(xs) - min(xs))
        me.transform(Matrix.Diagonal((s, s, 1, 1)))
    return me


def _signed_area(lp):
    return 0.5 * sum(lp[i - 1][0] * lp[i][1] - lp[i][0] * lp[i - 1][1] for i in range(len(lp)))


def _inside(pt, lp):
    x, y = pt
    c = False
    n = len(lp)
    for i in range(n):
        x1, y1 = lp[i - 1]
        x2, y2 = lp[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            c = not c
    return c


def clean_loop(lp, tol=0.004):
    """Drop near-duplicate points and zero-width spikes (A-B-A backtracks) that make scanfill skip triangles."""
    pts = []
    for p in lp:
        if not pts or math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) > tol:
            pts.append((float(p[0]), float(p[1])))
    while len(pts) > 3 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= tol:
        pts.pop()
    changed = True
    while changed and len(pts) > 3:
        changed = False
        n = len(pts)
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            ab = (b[0] - a[0], b[1] - a[1])
            bc = (c[0] - b[0], c[1] - b[1])
            cross = ab[0] * bc[1] - ab[1] * bc[0]
            dot = ab[0] * bc[0] + ab[1] * bc[1]
            if abs(cross) < 1e-9 and dot < 0:      # backtrack
                del pts[i]
                changed = True
                break
    return pts


def ear_clip(lp):
    """Triangulate one simple counter-clockwise polygon (list of (x, y)) -> index triples. Always n-2 triangles."""
    idx = list(range(len(lp)))
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    def in_tri(p, a, b, c):
        return cross(a, b, p) >= -1e-12 and cross(b, c, p) >= -1e-12 and cross(c, a, p) >= -1e-12

    guard = 0
    while len(idx) > 3 and guard < 20000:
        guard += 1
        n = len(idx)
        best = None
        for k in range(n):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % n]
            a, b, c = lp[i0], lp[i1], lp[i2]
            cr = cross(a, b, c)
            if cr <= 1e-14:
                continue
            if any(in_tri(lp[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            # prefer fat ears (keeps cap triangles compact)
            e = cr / max(1e-12, (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (c[0] - b[0]) ** 2 + (c[1] - b[1]) ** 2)
            if best is None or e > best[0]:
                best = (e, k)
        if best is None:          # degenerate remainder: cut the flattest vertex
            k = min(range(n), key=lambda k: abs(cross(lp[idx[k - 1]], lp[idx[k]], lp[idx[(k + 1) % n]])))
        else:
            k = best[1]
        tris.append((idx[k - 1], idx[k], idx[(k + 1) % n]))
        del idx[k]
    if len(idx) == 3:
        tris.append(tuple(idx))
    return tris


def prism_mesh(loops, depth=1.0, name="flat", tol=0.004):
    """Watertight extruded solid from closed 2D loops (even-odd: loops inside loops are holes), welded by
    construction: caps from mathutils tessellate_polygon, walls per loop. Replaces Blender curve fill,
    whose unwelded/degenerate output made the EXACT boolean drop glyphs (R) or cut logo holes through the band."""
    from mathutils.geometry import tessellate_polygon
    clean = []
    for lp in loops:
        pts = clean_loop(lp, tol)
        if len(pts) >= 3 and abs(_signed_area(pts)) > 1e-9:
            clean.append(pts)
    depths = []
    for k, lp in enumerate(clean):
        probe = ((lp[0][0] + lp[1][0]) / 2, (lp[0][1] + lp[1][1]) / 2)
        depth_k = sum(1 for m, other in enumerate(clean) if m != k and _inside(probe, other))
        depths.append(depth_k)
        want_ccw = depth_k % 2 == 0
        if (_signed_area(lp) > 0) != want_ccw:
            lp.reverse()
    offsets, base = [], 0
    for lp in clean:
        offsets.append(base)
        base += len(lp)
    N = base
    h = depth / 2
    verts = [(x, y, h) for lp in clean for x, y in lp] + [(x, y, -h) for lp in clean for x, y in lp]
    flat = [p for lp in clean for p in lp]
    faces = []
    cap = []
    # each outer outline with its own direct holes: ear clipping when simple, scanfill only for outlines with holes
    for k, lp in enumerate(clean):
        if depths[k] % 2:
            continue
        holes = [m for m, other in enumerate(clean) if depths[m] == depths[k] + 1 and
                 _inside(((other[0][0] + other[1][0]) / 2, (other[0][1] + other[1][1]) / 2), lp)]
        if not holes:
            cap += [(offsets[k] + i, offsets[k] + j, offsets[k] + q) for i, j, q in ear_clip(lp)]
        else:
            group = [k] + holes
            gidx = [offsets[g] + i for g in group for i in range(len(clean[g]))]
            for t in tessellate_polygon([[Vector((x, y, 0)) for x, y in clean[g]] for g in group]):
                cap.append(tuple(gidx[i] for i in t))
    for a_, b_, c_ in cap:
        (ax, ay), (bx, by), (cx, cy) = flat[a_], flat[b_], flat[c_]
        if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 0:
            faces += [(a_, b_, c_), (a_ + N, c_ + N, b_ + N)]
        else:
            faces += [(a_, c_, b_), (a_ + N, b_ + N, c_ + N)]
    base = 0
    for lp in clean:
        n = len(lp)
        for i in range(n):
            j = (i + 1) % n
            faces.append((base + i + N, base + j + N, base + j, base + i))
        base += n
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bad = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    if bad:
        print("WARNING prism_mesh %s: %d non-manifold edges" % (name, bad))
    return orient_outward(me)


def svg_glyph_loops(path=LOGO_SVG, resolution=10):
    """Outline loops per glyph (curve object) of an SVG, sampled from the Bezier control points, sorted left->right."""
    import addon_utils
    from mathutils.geometry import interpolate_bezier
    addon_utils.enable("io_curve_svg")
    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=path)
    new = [o for o in bpy.data.objects if o not in before and o.type == "CURVE"]
    glyphs = []
    for ob in new:
        mw = ob.matrix_world
        loops = []
        for sp in ob.data.splines:
            bp = sp.bezier_points
            n = len(bp)
            pts = []
            for i in range(n if sp.use_cyclic_u else n - 1):
                p0, p1 = bp[i], bp[(i + 1) % n]
                d = p1.co - p0.co
                straight = d.length < 1e-12 or all(
                    (h - p0.co).cross(d).length <= 1e-6 * d.length ** 2 for h in (p0.handle_right, p1.handle_left))
                if straight:
                    pts.append(mw @ p0.co)
                else:
                    seg = interpolate_bezier(p0.co, p0.handle_right, p1.handle_left, p1.co, resolution + 1)
                    pts += [mw @ v for v in seg[:-1]]
            loops.append([(v.x, v.y) for v in pts])
        glyphs.append(loops)
    for ob in new:
        cu = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if cu.users == 0:
            bpy.data.curves.remove(cu)
    for c in [c for c in bpy.data.collections if not c.objects and not c.children]:
        bpy.data.collections.remove(c)
    glyphs.sort(key=lambda g: min(p[0] for lp in g for p in lp))
    return glyphs


def svg_mesh(path=LOGO_SVG, height=1.6, width=None, depth=1.0, resolution=10, italic=0.0, tracking=0.0,
             condense=1.0):
    """The SVG (Rinfit wordmark) as a watertight extruded flat mesh in XY (x = reading direction), centred,
    cap height `height` mm (or total `width`). tracking: extra gap between glyphs in mm; condense: x scale of glyphs."""
    glyphs = svg_glyph_loops(path, resolution)
    ys = [p[1] for g in glyphs for lp in g for p in lp]
    xs = [p[0] for g in glyphs for lp in g for p in lp]
    sc = height / (max(ys) - min(ys)) if height else width / (max(xs) - min(xs))
    loops = []
    for k, g in enumerate(glyphs):
        for lp in g:
            loops.append([(x * sc * condense + k * tracking, y * sc) for x, y in lp])
    if italic:
        t = math.tan(italic)
        loops = [[(x + y * t, y) for x, y in lp] for lp in loops]
    loops = fit_loops(loops)
    return prism_mesh(loops, depth, "svg")


def rect_union_loops(rects, cuts=(), snap=1e-6):
    """Boundary loops (lists of (x, y)) of a union of axis-aligned rectangles (x0, y0, x1, y1) minus `cuts`.
    Outer loops counter-clockwise, holes clockwise."""
    allr = list(rects) + list(cuts)
    xs = sorted({round(v, 6) for r in allr for v in (r[0], r[2])})
    ys = sorted({round(v, 6) for r in allr for v in (r[1], r[3])})
    nx, ny = len(xs) - 1, len(ys) - 1

    def inside(r, cx, cy):
        return r[0] - snap <= cx <= r[2] + snap and r[1] - snap <= cy <= r[3] + snap

    def filled(i, j):
        if i < 0 or j < 0 or i >= nx or j >= ny:
            return False
        cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
        return any(inside(r, cx, cy) for r in rects) and not any(inside(r, cx, cy) for r in cuts)

    F = [[filled(i, j) for j in range(ny)] for i in range(nx)]

    def f(i, j):
        return 0 <= i < nx and 0 <= j < ny and F[i][j]

    # directed boundary edges with the filled cell on the left, as a multimap start -> [ends]
    mm = {}
    for i in range(nx):
        for j in range(ny):
            if not F[i][j]:
                continue
            if not f(i, j - 1):
                mm.setdefault((i, j), []).append((i + 1, j))
            if not f(i + 1, j):
                mm.setdefault((i + 1, j), []).append((i + 1, j + 1))
            if not f(i, j + 1):
                mm.setdefault((i + 1, j + 1), []).append((i, j + 1))
            if not f(i - 1, j):
                mm.setdefault((i, j + 1), []).append((i, j))
    loops = []
    while mm:
        start = next(iter(mm))
        loop = [start]
        cur = start
        prev_dir = None
        while True:
            outs = mm.get(cur)
            if not outs:
                break
            if len(outs) > 1 and prev_dir is not None:   # pinch vertex: turn left first
                def turn(e):
                    d = (e[0] - cur[0], e[1] - cur[1])
                    return -(prev_dir[0] * d[1] - prev_dir[1] * d[0])
                outs.sort(key=turn)
            nxt = outs.pop(0)
            if not outs:
                del mm[cur]
            prev_dir = (nxt[0] - cur[0], nxt[1] - cur[1])
            cur = nxt
            if cur == start:
                break
            loop.append(cur)
        # drop collinear points
        pts = [(xs[i], ys[j]) for i, j in loop]
        clean = []
        n = len(pts)
        for k in range(n):
            a, b, c = pts[k - 1], pts[k], pts[(k + 1) % n]
            if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9:
                clean.append(b)
        if len(clean) >= 3:
            loops.append(clean)
    return loops


def infinity_mark_loops(side=4.0, stroke=1.1):
    """Rinfit infinity mark in grid units: square outline A = [0,s]^2 and B = A + (s-t, s).
    A's right side and B's left side form one long stem; B's bottom bar sits right on top of A's top bar
    (outer edges collinear on the infinity-men renders). Used debossed on infinity-men and raised inside step-edge."""
    s, t = side, stroke
    a = [(0, 0, s, t), (0, s - t, s, s), (0, 0, t, s), (s - t, 0, s, s)]
    dx, dy = (s - t), s
    b = [(x0 + dx, y0 + dy, x1 + dx, y1 + dy) for x0, y0, x1, y1 in a]
    return rect_union_loops(a + b)


def resample_loop(lp, max_seg):
    out = []
    n = len(lp)
    for k in range(n):
        (x0, y0), (x1, y1) = lp[k], lp[(k + 1) % n]
        m = max(1, int(math.ceil(math.hypot(x1 - x0, y1 - y0) / max_seg)))
        out += [(x0 + (x1 - x0) * i / m, y0 + (y1 - y0) * i / m) for i in range(m)]
    return out


def fit_loops(loops, height=None, width=None):
    """Centre 2D loops on the origin and scale them to a height (y extent) or width (x extent) in mm."""
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    sc = height / (max(ys) - min(ys)) if height else (width / (max(xs) - min(xs)) if width else 1.0)
    return [[((x - cx) * sc, (y - cy) * sc) for x, y in lp] for lp in loops]


def loops_mesh(loops, depth=1.0, name="flat", max_seg=None):
    """Watertight extruded mesh from closed 2D loops (holes = loops inside loops). max_seg (mm) inserts points
    along long edges so the wrapped caps follow the band curvature."""
    if max_seg:
        loops = [resample_loop(lp, max_seg) for lp in loops]
    return prism_mesh(loops, depth, name)


def transform2d(loops, angle=0.0, scale=1.0, offset=(0, 0)):
    c, s = math.cos(angle), math.sin(angle)
    return [[(offset[0] + scale * (x * c - y * s), offset[1] + scale * (x * s + y * c)) for x, y in lp] for lp in loops]


def join_meshes(meshes, name="flat"):
    bm = bmesh.new()
    for me in meshes:
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    return out


def copy_mesh(me, dx=0.0, dy=0.0):
    m = me.copy()
    m.transform(Matrix.Translation((dx, dy, 0)))
    return m


def engrave_mesh(L, band_ob, profile, me, phi_center, depth=0.15, emboss=False, y_center=0.0, on_inner=False,
                 rotate=0.0, y_of_phi=None, below=0.3, above=0.6):
    """L.engrave() for any flat tool mesh (SVG wordmark, logo outlines)."""
    if emboss:
        tool = L.wrap_on_band(me, profile, phi_center, y_center, below=below, above=depth, on_inner=on_inner,
                              rotate=rotate, y_of_phi=y_of_phi)
        return L.boolean(band_ob, tool, "UNION")
    tool = L.wrap_on_band(me, profile, phi_center, y_center, below=depth, above=above, on_inner=on_inner,
                          rotate=rotate, y_of_phi=y_of_phi)
    return L.boolean(band_ob, tool, "DIFFERENCE")


class Section:
    """Arbitrary closed (r, y) cross-section with outer_r / inner_r lookups (for wrap_on_band)."""

    def __init__(self, points, width, outer_fn, inner_fn):
        self.points = points
        self.width = width
        self._o, self._i = outer_fn, inner_fn

    def outer_r(self, y):
        return self._o(y)

    def inner_r(self, y):
        return self._i(y)


def rounded_poly(corners, radii, n=6):
    """Closed polyline through `corners` with each corner rounded by a quadratic Bezier of size radii[k] (mm)."""
    pts = []
    m = len(corners)
    for k in range(m):
        p0, p1, p2 = Vector(corners[k - 1]), Vector(corners[k]), Vector(corners[(k + 1) % m])
        r = radii[k]
        if r <= 1e-6:
            pts.append((p1.x, p1.y))
            continue
        a = p1 + (p0 - p1).normalized() * min(r, (p0 - p1).length * 0.49)
        b = p1 + (p2 - p1).normalized() * min(r, (p2 - p1).length * 0.49)
        for i in range(n + 1):
            t = i / n
            q = a * (1 - t) ** 2 + p1 * 2 * (1 - t) * t + b * t * t
            pts.append((q.x, q.y))
    return pts
