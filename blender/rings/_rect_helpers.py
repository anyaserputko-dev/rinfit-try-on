"""Helpers used only by emerald.py, halo.py, princess.py.

faceted(): brilliant-style stone for straight-sided outlines (radiant / princess). rinfit.brilliant builds facets from
sectors round the centre; on a long straight side neighbouring facets become coplanar and merge into a few huge planes
(step-cut look). Here the stone is a girdle prism cut by true facet planes (bmesh bisect + fill): every plane is tangent
to the girdle outline at its own azimuth, with varying crown slope / pavilion "virtual culet" depth, mirror-symmetric
over X and Y — many distinct small facets = the crushed-ice look of Rinfit's CAD stones.
"""
import math
import bmesh, bpy
from mathutils import Vector, Matrix


def support(outline, th):
    c, s = math.cos(th), math.sin(th)
    return max(x * c + y * s for x, y in outline)


def mirrored(azq):
    """(theta, index) pairs in [0, pi/2] -> all four quadrants (mirror over X and Y), duplicates removed."""
    out = []
    for th, k in azq:
        for t in (th, math.pi - th, math.pi + th, 2 * math.pi - th):
            t %= 2 * math.pi
            if all(abs((t - u + math.pi) % (2 * math.pi) - math.pi) > 1e-6 for u, _ in out):
                out.append((t, k))
    return out


def faceted(L, name, outline, mat, crown_h, pav_d, girdle_h=0.16, n_quad=8, crown_t=(0.58,), pav_f=(1.0,),
            pav2=None, crown2=None, crown_slope=None, pav_slope=None, tiers=None):
    """outline: convex girdle polygon (x, y) round the origin. Table plane at girdle_h/2 + crown_h.
    crown_t: cycle of 'where the facet meets the table' (fraction of the support distance) per azimuth.
    pav_f: cycle of virtual-culet depth fractions per azimuth (actual culet = pav_d * min(pav_f)).
    pav2 / crown2: optional second tier (n_quad, fractions, azimuth offset in steps) for smaller facets near the girdle."""
    g2 = girdle_h / 2
    zt = g2 + crown_h
    bm = bmesh.new()
    n = len(outline)
    top = [bm.verts.new((x, y, zt + 0.5)) for x, y in outline]
    bot = [bm.verts.new((x, y, -g2 - pav_d - 0.5)) for x, y in outline]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    planes = [(Vector((0, 0, 1)), zt)]

    def crown_planes(nq, fracs, offset=0.0, lift=0.0):
        az = [((k + offset) / nq * math.pi / 2, k) for k in range(nq + 1)]
        for th, k in mirrored([a for a in az if a[0] <= math.pi / 2 + 1e-9]):
            h = support(outline, th)
            if crown_slope and not lift:        # facet slope in degrees (same angle on long and short sides)
                g = math.radians(crown_slope[k % len(crown_slope)])
            else:
                t = fracs[k % len(fracs)]
                g = math.atan2(crown_h - lift, h * (1 - t))
            nv = Vector((math.sin(g) * math.cos(th), math.sin(g) * math.sin(th), math.cos(g)))
            planes.append((nv, math.sin(g) * h + math.cos(g) * (g2 + lift)))

    def pav_planes(nq, fracs, offset=0.0):
        az = [((k + offset) / nq * math.pi / 2, k) for k in range(nq + 1)]
        for th, k in mirrored([a for a in az if a[0] <= math.pi / 2 + 1e-9]):
            h = support(outline, th)
            if pav_slope and offset == 0.0:     # constant slope per facet -> keel line on elongated stones
                g = math.radians(pav_slope[k % len(pav_slope)])
            else:
                g = math.atan2(pav_d * fracs[k % len(fracs)], h)
            nv = Vector((math.sin(g) * math.cos(th), math.sin(g) * math.sin(th), -math.cos(g)))
            planes.append((nv, math.sin(g) * h + math.cos(g) * g2))

    def tier_planes(t):
        """t: side 'crown' / 'pav', nq, offset (azimuth steps), slopes (deg cycle), a (anchor at a * support distance),
        anchor z: crown -> 'table' or girdle + (1 - a) * h * tan(ref) + lift; pav -> -girdle - (1 - a) * h * tan(ref) + lift."""
        nq, off = t["nq"], t.get("offset", 0.0)
        az = [((k + off) / nq * math.pi / 2, k) for k in range(nq + 1)]
        for th, k in mirrored([x for x in az if x[0] <= math.pi / 2 + 1e-9]):
            h = support(outline, th)
            g = math.radians(t["slopes"][k % len(t["slopes"])])
            a = t.get("a", 1.0)
            if t["side"] == "crown":
                z0 = zt if t.get("anchor") == "table" else \
                    g2 + (1 - a) * h * math.tan(math.radians(t.get("ref", 34))) + t.get("lift", 0.0)
                nv = Vector((math.sin(g) * math.cos(th), math.sin(g) * math.sin(th), math.cos(g)))
                planes.append((nv, math.sin(g) * a * h + math.cos(g) * z0))
            else:
                z0 = -g2 - (1 - a) * h * math.tan(math.radians(t.get("ref", 42))) + t.get("lift", 0.0)
                nv = Vector((math.sin(g) * math.cos(th), math.sin(g) * math.sin(th), -math.cos(g)))
                planes.append((nv, math.sin(g) * a * h - math.cos(g) * z0))

    if tiers:
        for t in tiers:
            tier_planes(t)
    else:
        crown_planes(n_quad, crown_t)
        if crown2:
            crown_planes(crown2[0], crown2[1], crown2[2], crown2[3] if len(crown2) > 3 else 0.0)
        pav_planes(n_quad, pav_f)
        if pav2:
            pav_planes(pav2[0], pav2[1], pav2[2])

    for nv, d in planes:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=nv * d, plane_no=nv, clear_outer=True)
        edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        if edges:
            bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = L.link(bpy.data.objects.new(name, me))
    me.materials.append(mat)
    L.shade(ob, False)
    return ob


def rect_poly(w, l, c):
    """Rectangle with cut corners as 8 points, counter-clockwise from the +X side."""
    hw, hl = w / 2, l / 2
    return [(hw, -hl + c), (hw, hl - c), (hw - c, hl), (-hw + c, hl), (-hw, hl - c), (-hw, -hl + c),
            (-hw + c, -hl), (hw - c, -hl)]


def faceted_sides(L, name, poly, mat, crown_h, pav_d, girdle_h=0.24, seg_pts=(4, 1), psi=6.0,
                  crown_t=(0.58, 0.50, 0.64), pav_f=(1.0, 0.93, 1.06, 0.97), star=(20, 24), table=0.62, star_nq=8):
    """Radiant / princess style stone on a convex polygon girdle (straight sides).
    Along every side, facet pairs tilted +-psi from the side normal start at seg_pts[0] + 1 points (seg_pts[1] + 1
    on short edges such as chamfers): they meet the side at different points (slightly scalloped girdle, as on real
    stones) and run to a virtual culet at depth pav_d * f on the axis -> radiating crushed-ice pavilion.
    Crown facets rise from the same points to the table (meeting it at crown_t fractions); star facets hang from
    the table edge."""
    g2 = girdle_h / 2
    zt = g2 + crown_h
    n = len(poly)
    bm = bmesh.new()
    top = [bm.verts.new((x, y, zt + 0.5)) for x, y in poly]
    bot = [bm.verts.new((x, y, -g2 - pav_d * max(pav_f) - 0.5)) for x, y in poly]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    planes = [(Vector((0, 0, 1)), zt)]
    lens = [math.dist(poly[i], poly[(i + 1) % n]) for i in range(n)]
    long_len = max(lens)
    k = 0
    for i in range(n):
        a, b = Vector(poly[i]), Vector(poly[(i + 1) % n])
        e = (b - a).normalized()
        nrm = Vector((e.y, -e.x))           # outward normal for a counter-clockwise polygon
        m = seg_pts[0] if lens[i] > 0.45 * long_len else seg_pts[1]
        for s in range(m + 1):
            P = a.lerp(b, s / m)
            for sgn in ((-1, 1) if 0 < s < m else ((1,) if s == 0 else (-1,))):
                ang = math.atan2(nrm.y, nrm.x) + math.radians(psi) * sgn
                u = Vector((math.cos(ang), math.sin(ang)))
                h = P.dot(u)
                # pavilion
                g = math.atan2(pav_d * pav_f[k % len(pav_f)], h)
                planes.append((Vector((math.sin(g) * u.x, math.sin(g) * u.y, -math.cos(g))),
                               math.sin(g) * h + math.cos(g) * g2))
                # crown
                t = crown_t[k % len(crown_t)]
                g = math.atan2(crown_h, h * (1 - t))
                planes.append((Vector((math.sin(g) * u.x, math.sin(g) * u.y, math.cos(g))),
                               math.sin(g) * h + math.cos(g) * g2))
                k += 1
    if star:
        for th, kk in mirrored([((q + 0.5) / star_nq * math.pi / 2, q) for q in range(star_nq)]):
            h = support(poly, th)
            g = math.radians(star[kk % len(star)])
            nv = Vector((math.sin(g) * math.cos(th), math.sin(g) * math.sin(th), math.cos(g)))
            planes.append((nv, math.sin(g) * table * h + math.cos(g) * zt))
    for nv, d in planes:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=nv * d, plane_no=nv, clear_outer=True)
        edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        if edges:
            bmesh.ops.holes_fill(bm, edges=edges, sides=0)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = L.link(bpy.data.objects.new(name, me))
    me.materials.append(mat)
    L.shade(ob, False)
    return ob


def _ring_points(outline, s, step, off):
    """Points of a ring: outline scaled by s, taking every `step`-th girdle point, shifted by `off` * step."""
    n = len(outline)
    pts = []
    for i in range(n // step):
        t = (i + off) * step
        j = int(math.floor(t)) % n
        f = t - math.floor(t)
        a, b = outline[j], outline[(j + 1) % n]
        pts.append((t % n, (a[0] + (b[0] - a[0]) * f) * s, (a[1] + (b[1] - a[1]) * f) * s))
    return pts


def _zip(ra, rb, n):
    """Triangles between two closed rings given as (param, index) lists, param = girdle index in [0, n)."""
    tris = []
    ia = ib = 0
    la, lb = len(ra), len(rb)
    start_a = min(range(la), key=lambda i: ra[i][0])
    start_b = min(range(lb), key=lambda i: rb[i][0])
    A = ra[start_a:] + ra[:start_a]
    B = rb[start_b:] + rb[:start_b]
    A = A + [(A[0][0] + n, A[0][1])]
    B = B + [(B[0][0] + n, B[0][1])]
    while ia < la or ib < lb:
        if ib >= lb or (ia < la and A[ia + 1][0] <= B[ib + 1][0]):
            tris.append((A[ia][1], A[ia + 1][1], B[ib][1]))
            ia += 1
        else:
            tris.append((A[ia][1], B[ib + 1][1], B[ib][1]))
            ib += 1
    return tris


def crushed(L, name, outline, mat, crown_h, pav_d, girdle_h=0.18, table=0.62,
            crown_rings=((0.86, 2, 0.5),), pav_rings=((0.78, 2, 0.5), (0.50, 4, 0.0), (0.22, 8, 0.5)),
            jitter=0.03, jitter_z=0.04, pav_power=1.0, seed=1):
    """Explicit crushed-ice brilliant for any convex girdle (straight sides stay exact).
    Rings (scale, girdle-point step, half-step offset) are zipped into triangles; inner rings get a small
    deterministic radial / height jitter so every flat triangle is its own facet. Point counts halve towards the
    culet -> radiating 'bow-tie' pavilion; the table is one flat face at scale `table`."""
    n = len(outline)
    g2 = girdle_h / 2
    zt = g2 + crown_h
    verts, faces = [], []

    def rnd(i, k):
        v = math.sin(i * 12.9898 + k * 78.233 + seed * 37.719) * 43758.5453
        return (v - math.floor(v)) * 2 - 1

    def add_ring(pts, zfun, jit):
        idx = []
        for i, (t, x, y) in enumerate(pts):
            if jit:
                f = 1 + jitter * rnd(len(verts), 1)
                x, y = x * f, y * f
            z = zfun(x, y) + (jitter_z * rnd(len(verts), 2) if jit else 0.0)
            verts.append((x, y, z))
            idx.append((t, len(verts) - 1))
        return idx

    gt = add_ring(_ring_points(outline, 1.0, 1, 0.0), lambda x, y: g2, False)
    gb = add_ring(_ring_points(outline, 1.0, 1, 0.0), lambda x, y: -g2, False)
    for i in range(n):
        j = (i + 1) % n
        faces.append((gb[i][1], gb[j][1], gt[j][1], gt[i][1]))
    # crown
    prev = gt
    for s, step, off in list(crown_rings):
        ring = add_ring(_ring_points(outline, s, step, off), lambda x, y, s=s: g2 + crown_h * (1 - s) / (1 - table), True)
        faces += _zip(prev, ring, n)
        prev = ring
    tab = add_ring(_ring_points(outline, table, 4, 0.0), lambda x, y: zt, False)
    faces += _zip(prev, tab, n)
    faces.append(tuple(i for _, i in tab))
    # pavilion
    prev = gb
    for s, step, off in pav_rings:
        ring = add_ring(_ring_points(outline, s, step, off),
                        lambda x, y, s=s: -g2 - pav_d * (1 - s) ** pav_power, True)
        faces += [(a, c, b) for a, b, c in _zip(prev, ring, n)]
        prev = ring
    verts.append((0.0, 0.0, -g2 - pav_d))
    c = len(verts) - 1
    lst = sorted(prev)
    for k in range(len(lst)):
        a, b = lst[k][1], lst[(k + 1) % len(lst)][1]
        faces.append((b, a, c))
    ob = L.mesh_object(name, verts, faces, mat, smooth=False)
    L.fix_normals(ob)
    L.shade(ob, False)
    return ob


def drop_empty_slots(ob):
    """rinfit.engrave's boolean leaves an extra empty material slot on the band (no faces use it); remove it so the
    GLB carries only the named materials."""
    me = ob.data
    for i in reversed(range(len(me.materials))):
        if me.materials[i] is None and not any(p.material_index == i for p in me.polygons):
            me.materials.pop(index=i)


def ball(L, name, center, radii, axis, mat, subdiv=3):
    """Ellipsoid from an icosphere (no pole streaks on polished tips)."""
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


def corner_index(outline, w, l, c):
    """Chamfer middles per quadrant (+X+Y, -X+Y, -X-Y, +X-Y).
    Library note: rinfit.outline_rect's docstring says corners at j = 8, 24, 40, 56 (n = 64) but its rotation puts
    them at 4, 20, 36, 52."""
    tgt = [(sx * (w / 2 - c / 2), sy * (l / 2 - c / 2)) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
    return [min(range(len(outline)), key=lambda j: (outline[j][0] - x) ** 2 + (outline[j][1] - y) ** 2) for x, y in tgt]
