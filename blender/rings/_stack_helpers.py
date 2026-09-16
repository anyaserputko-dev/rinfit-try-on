"""Helpers used only by the GlowStone stack modules (marquise.py, pear.py, black_oval.py)."""
import math
import bisect
import bpy
import bmesh
from mathutils import Vector, Matrix


class Shifted:
    """BandProfile proxy for a band built with y_offset (engrave/wrap_on_band evaluate the profile at absolute y)."""

    def __init__(self, prof, dy):
        self.prof, self.dy, self.width = prof, dy, prof.width

    def inner_r(self, y):
        return self.prof.inner_r(y - self.dy)

    def outer_r(self, y):
        return self.prof.outer_r(y - self.dy)


def band_z(r_top, x):
    """Height of a cylindrical band surface of radius r_top at lateral offset x (stone side up)."""
    return math.sqrt(max(0.0, r_top * r_top - x * x))


def sheet(L, name, top_pts, bot_pts, thickness, offset_dir, mat):
    """Metal sheet between two polylines of equal length, thickened by `thickness` along offset_dir (centred)."""
    n = len(top_pts)
    d = Vector(offset_dir).normalized() * (thickness / 2)
    verts = [Vector(p) + d for p in top_pts] + [Vector(p) + d for p in bot_pts] + \
            [Vector(p) - d for p in top_pts] + [Vector(p) - d for p in bot_pts]
    T0, B0, T1, B1 = 0, n, 2 * n, 3 * n
    faces = []
    for i in range(n - 1):
        faces.append((T0 + i, T0 + i + 1, B0 + i + 1, B0 + i))
        faces.append((T1 + i, B1 + i, B1 + i + 1, T1 + i + 1))
        faces.append((T0 + i, T1 + i, T1 + i + 1, T0 + i + 1))
        faces.append((B0 + i, B0 + i + 1, B1 + i + 1, B1 + i))
    faces.append((T0, B0, B1, T1))
    faces.append((T0 + n - 1, T1 + n - 1, B1 + n - 1, B0 + n - 1))
    ob = L.mesh_object(name, verts, faces, mat)
    L.fix_normals(ob)
    return ob


def pillow(L, name, outline_uv, thick, origin, u_axis, v_axis, mat, levels=2, scale=1.0):
    """Rounded metal blob: a flat outline (u, v) extruded by `thick` and smoothed with subdivision.
    The outline lies in the plane spanned by u_axis / v_axis at `origin`."""
    bm = bmesh.new()
    top = [bm.verts.new((u * scale, v * scale, thick / 2)) for u, v in outline_uv]
    bot = [bm.verts.new((u * scale, v * scale, -thick / 2)) for u, v in outline_uv]
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    n = len(top)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = L.link(bpy.data.objects.new(name, me))
    u, v = Vector(u_axis).normalized(), Vector(v_axis).normalized()
    w = u.cross(v).normalized()
    v = w.cross(u).normalized()
    M = Matrix((u, v, w)).transposed().to_4x4()
    M.translation = Vector(origin)
    ob.matrix_world = M
    mod = ob.modifiers.new("sub", "SUBSURF")
    mod.levels = mod.render_levels = levels
    L.bake(ob)
    ob.data.materials.append(mat)
    L.shade(ob, True)
    return ob


def _arc_table(R, y_fn, n=4096):
    phis = [2 * math.pi * i / n for i in range(n + 1)]
    s = [0.0]
    for i in range(n):
        dy = y_fn(phis[i + 1]) - y_fn(phis[i])
        s.append(s[-1] + math.hypot(R * (phis[i + 1] - phis[i]), dy))
    return phis, s


def _phi_at(phis, s, target):
    i = min(max(bisect.bisect_left(s, target), 1), len(s) - 1)
    f = (target - s[i - 1]) / max(1e-12, s[i] - s[i - 1])
    return phis[i - 1] + f * (phis[i] - phis[i - 1])


def pyramid_row(L, name, R, y_fn, count, across, height, mat, sink=0.12, along=1.0, apex_shift=0.0):
    """Row of 4-sided pyramids with a diamond base, following a (possibly V shaped) band path on its outer
    surface of radius R. y_fn(phi) = centre line of the band along the finger. Studs are spaced evenly along
    the true path length; one stud is centred on phi = 0 (the V apex). `along` scales the base diagonal along
    the path relative to the pitch (1.0 = neighbouring diamonds touch)."""
    phis, s = _arc_table(R, y_fn)
    total = s[-1]
    pitch = total / count
    verts, faces = [], []

    def surf(phi, r):
        return Vector((r * math.sin(phi), y_fn(phi), r * math.cos(phi)))

    rb = R - sink
    for k in range(count):
        sc = k * pitch
        pc = _phi_at(phis, s, sc % total)
        pa = _phi_at(phis, s, (sc - pitch / 2 * along) % total)
        pb = _phi_at(phis, s, (sc + pitch / 2 * along) % total)
        eps = 1e-3
        dyd = (y_fn(pc + eps) - y_fn(pc - eps)) / (2 * eps)
        nrm = math.hypot(R, dyd)
        ta = -dyd / nrm * across / 2
        ty = R / nrm * across / 2
        c0, c2 = surf(pa, rb), surf(pb, rb)
        c1 = Vector((rb * math.sin(pc + ta / R), y_fn(pc) + ty, rb * math.cos(pc + ta / R)))
        c3 = Vector((rb * math.sin(pc - ta / R), y_fn(pc) - ty, rb * math.cos(pc - ta / R)))
        apex = surf(pc, R + height)
        apex.y += apex_shift
        b = len(verts)
        verts += [c0, c1, c2, c3, apex]
        faces += [(b, b + 1, b + 4), (b + 1, b + 2, b + 4), (b + 2, b + 3, b + 4), (b + 3, b, b + 4),
                  (b + 3, b + 2, b + 1, b)]
    ob = L.mesh_object(name, verts, faces, mat)
    L.fix_normals(ob)
    L.shade(ob, False)
    return ob


def textured_copy(base_mat, name, scale=9.0, strength=0.35, distance=0.03, roughness=None):
    """Hero-render-only copy of a silicone material with the fine grain of Rinfit's studded bands."""
    m = base_mat.copy()
    m.name = name
    nt = m.node_tree
    p = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = 8.0
    tex.inputs["Roughness"].default_value = 0.65
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    nt.links.new(tc.outputs["Object"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
    if roughness is not None:
        p.inputs["Roughness"].default_value = roughness
    return m


def polyline_offset(outline, inset, idx):
    """Points of a closed 2D outline (counter-clockwise) moved inwards by `inset` along the local normal."""
    n = len(outline)
    out = []
    for j in idx:
        a, b = Vector(outline[(j - 1) % n]), Vector(outline[(j + 1) % n])
        t = (b - a).normalized()
        nin = Vector((-t.y, t.x))          # left of the direction of travel = inside for CCW outlines
        p = Vector(outline[j % n]) + nin * inset
        out.append((p.x, p.y))
    return out


def outline_pear_full(w, l, round_len, power=2.5, n=64):
    """Pear outline fitted to Rinfit's pear render (img_00): round end = semi-ellipse (half width w/2, depth
    round_len), flanks x = w/2 * (1 - u**power) with u = 0 at the widest point and 1 at the tip.
    Tip at +Y (j = n/4), j = 0 at +X, counter-clockwise, centred on the length."""
    q = n // 4
    r = w / 2
    yw = -l / 2 + round_len
    h = l / 2 - yw
    dense = []
    for i in range(801):
        u = i / 800
        dense.append((r * (1 - u ** power), yw + h * u))
    flank = resample_open(dense, q)                    # q + 1 points from (r, yw) to the tip
    pts = flank[:-1] + [(-x, y) for x, y in reversed(flank)][:-1]
    ell = [(r * math.cos(math.pi + math.pi * i / 400), yw + round_len * math.sin(math.pi + math.pi * i / 400))
           for i in range(401)]
    pts += resample_open(ell, n // 2)[:-1]
    return pts


def resample_open(points, segs):
    """segs + 1 points evenly spaced along an open polyline."""
    pts = [Vector((p[0], p[1])) for p in points]
    d = [0.0]
    for a, b in zip(pts, pts[1:]):
        d.append(d[-1] + (b - a).length)
    out, k = [], 0
    for i in range(segs + 1):
        t = d[-1] * i / segs
        while k < len(d) - 2 and d[k + 1] < t:
            k += 1
        f = (t - d[k]) / max(1e-12, d[k + 1] - d[k])
        q = pts[k].lerp(pts[k + 1], min(1.0, max(0.0, f)))
        out.append((q.x, q.y))
    return out
