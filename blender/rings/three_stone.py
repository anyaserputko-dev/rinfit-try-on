"""Rinfit Silicone Ring with Three Round CZ Stones - Patented.

Product page (rinfit.com/products/three-stones-round-cut-silicone-ring):
  Band Width 6 mm | Band Thickness 2 mm | three Round-Cut CZ | polished brass setting
  Colours: "Nude and Rose Gold", "White and Silver", "Black and Silver"

Stone sizes are NOT stated. Measured off the CAD hero (7_9ac6a3ab..., the picture Anna gave as the reference)
and the white variant (6_5d50accd...), which show the same geometry from the same camera:
  centre : side stone = 1.47 (the DVS_* hand photos give the same ratio)
  the three stones together span the ring's own outer diameter -> centre 8.9 mm, sides 6.05 mm on a US 7 band
Known conflict (as in solitaire.py): Rinfit's CAD heroes draw the stones larger relative to the band than the
hand photos do. The CAD is the product page image, so the CAD is what is matched here.

Construction, read off a rose-gold mask of the hero (segmenting the metal by hue tells it better than the eye):
  - the stones sit on the ARC of the band, not on a straight bar: the setting is a curved rail of roughly even
    thickness lying on the band's outer surface, and every stone's girdle plane is tangent to the ring, so the
    side stones lean outwards by the arc angle
  - the rail tapers into the silicone at both ends; its flat y = +-half_w walls are the big flat quads that read
    as "a flat plate" on the photo
  - 4 claws per stone on the diagonals, round wire with bulbous tear-drop tips leaning in over the crown
  - RINFIT debossed on the OUTER surface of the band, just past the end of the rail (solitaire has it inside)
"""
import math
from mathutils import Matrix, Vector

COLORS = ["Nude and Rose Gold", "White and Silver", "Black and Silver"]

BAND = dict(width=6.0, thickness=2.0, dome=0.85, inner_dome=0.12, edge_out=1.0, edge_in=0.4)

CENTER = 6.95                   # centre stone diameter (mm)
SIDE = 4.70                     # side stone diameter
GAP = 0.15                      # between neighbouring girdles
GIRDLE_H = 2.30                 # girdle plane over the crown of the band
RAIL = dict(h=0.85, half_w=2.05, over=0.70, taper=9.0)   # height over the band, half width, run past the
#                                                          outer stone edge, degrees of end taper
STONE = dict(table=0.56, star=0.78, crown=0.15, pavilion=0.435, lower=0.23, sectors=8, pav_sectors=8)
CLAW = dict(radius=0.30, tip=(0.46, 0.46, 0.62), lean=0.26, tip_height=0.62, back=0.50)
TEXT = dict(size=2.9, depth=0.16, spacing=1.05, rotate=0.0)
TEXT_PHI = math.radians(52.0)  # where RINFIT sits round the band, measured from the stones

HERO = dict(direction=(0.0, -0.3420, 0.9397), up=(0.0872, 0.0, 0.9962), target=(0, 0, 2.5), dist=60, lens=85)
VIEWS = {
    "hero": dict(camera=HERO, frame=False, color="Nude and Rose Gold"),
    "white": dict(camera=HERO, frame=False, color="White and Silver"),
    "black": dict(camera=HERO, frame=False, color="Black and Silver"),
    "side": dict(camera=dict(direction=(1, 0.12, 0.3), up=(0, 0, 1), dist=200, lens=100), scene="glb"),
    "top": dict(camera=dict(direction=(0.02, -0.08, 1), up=(0, 1, 0), dist=200, lens=100), scene="glb"),
}


def stone_angles(girdle_r):
    """Arc positions of the three stones: the girdles just clear each other on the chord between them."""
    chord = (CENTER + SIDE) / 2 + GAP
    d = 2 * math.asin(min(0.99, chord / (2 * girdle_r)))
    return [(-d, SIDE, "_l"), (0.0, CENTER, "_c"), (d, SIDE, "_r")]


def rail_mesh(L, name, prof, r_out, half_w, phi_end, taper, mat, n_phi=140, n_y=12):
    """Curved setting rail: inner surface = the band's own domed outer surface (so it sits flush), outer surface
    at radius r_out, flat walls at y = +-half_w, tapering back down onto the band over `taper` radians."""
    phis = [-phi_end + 2 * phi_end * i / n_phi for i in range(n_phi + 1)]
    ys = [-half_w + 2 * half_w * j / n_y for j in range(n_y + 1)]
    r_in = [prof.outer_r(y) - 0.04 for y in ys]

    def ro(phi):
        a = abs(phi)
        if a <= phi_end - taper:
            return r_out
        t = (a - (phi_end - taper)) / taper
        return r_out - (r_out - r_in[n_y // 2]) * t * t

    def P(r, phi, y):
        return (r * math.sin(phi), y, r * math.cos(phi))

    nyv = n_y + 1
    verts, faces = [], []
    for phi in phis:                                                # inner shell
        for j, y in enumerate(ys):
            verts.append(P(r_in[j], phi, y))
    top0 = len(verts)
    for phi in phis:                                                # outer shell
        for j, y in enumerate(ys):
            verts.append(P(max(ro(phi), r_in[j] + 0.02), phi, y))
    for i in range(n_phi):
        for j in range(n_y):
            a, b = i * nyv + j, (i + 1) * nyv + j
            faces.append((a, a + 1, b + 1, b))
            a, b = top0 + i * nyv + j, top0 + (i + 1) * nyv + j
            faces.append((a, b, b + 1, a + 1))
    for j in range(n_y):                                            # caps at both ends
        faces.append((j, top0 + j, top0 + j + 1, j + 1))
        a, t = n_phi * nyv + j, top0 + n_phi * nyv + j
        faces.append((a, a + 1, t + 1, t))
    for i in range(n_phi):                                          # flat side walls
        faces.append((i * nyv, (i + 1) * nyv, top0 + (i + 1) * nyv, top0 + i * nyv))
        faces.append((i * nyv + n_y, top0 + i * nyv + n_y, top0 + (i + 1) * nyv + n_y, (i + 1) * nyv + n_y))
    ob = L.mesh_object(name, verts, faces, mat, smooth=False)
    L.fix_normals(ob)
    L.shade(ob, True, sharp_angle=28)
    return ob


def cone_tool(L, name, r_girdle, pav_depth, z_hi, clear=0.14, n=40):
    """Clearance cone for one pavilion, in the stone's own frame (girdle plane at z = 0, table up)."""
    culet = -pav_depth
    r_hi = r_girdle * (z_hi - culet) / pav_depth + clear
    verts, faces = [], []
    for z, rr in ((culet - 0.3, 0.05), (z_hi, r_hi)):
        for k in range(n):
            a = 2 * math.pi * k / n
            verts.append((rr * math.cos(a), rr * math.sin(a), z))
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((k, k2, n + k2, n + k))
    c0 = len(verts)
    verts.append((0, 0, culet - 0.3))
    c1 = len(verts)
    verts.append((0, 0, z_hi))
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((k2, k, c0))
        faces.append((n + k, n + k2, c1))
    ob = L.mesh_object(name, verts, faces, None, smooth=False)
    L.fix_normals(ob)
    return ob


def place(ob, M):
    ob.data.transform(M)
    ob.data.update()
    return ob


def build(L, color, scene="hero"):
    bands, metals = L.parse_color(color)
    sil = L.mat_silicone(bands[0], "Silicone_A")
    metal = L.mat_metal(metals[0], "Metal")
    cz = L.mat_cz()

    prof = L.BandProfile(**BAND)
    band = L.band("band", prof, sil)
    r_top = prof.outer_r(0)
    girdle_r = r_top + GIRDLE_H
    r_rail = r_top + RAIL["h"]
    row = stone_angles(girdle_r)

    taper = math.radians(RAIL["taper"])
    phi_end = abs(row[0][0]) + (SIDE / 2 + RAIL["over"]) / girdle_r + taper
    rail = rail_mesh(L, "rail", prof, r_rail, RAIL["half_w"], phi_end, taper, metal)

    stones, parts = [], [rail]
    for phi, d, tag in row:
        M = Matrix.Rotation(phi, 4, "Y") @ Matrix.Translation((0.0, 0.0, girdle_r))
        R, pav = d / 2, STONE["pavilion"] * d
        stones.append(place(L.brilliant("stone" + tag, L.outline_ellipse(d, d), cz, size_ref=d, **STONE), M))
        z_rail = r_rail - girdle_r          # rail top in the stone's own frame (negative: below the girdle)
        for k in range(4):
            a = math.radians(45 + 90 * k)
            c, s = math.cos(a), math.sin(a)
            g = Vector((R * c, R * s, 0.0))
            base = Vector(((R - CLAW["back"]) * c, (R - CLAW["back"]) * s, z_rail - 0.30))
            for p in L.prong(f"claw{tag}_{k}", base, g, (0.0, 0.0), STONE["crown"] * d, metal,
                             radius=CLAW["radius"], tip=CLAW["tip"], lean=CLAW["lean"],
                             tip_height=CLAW["tip_height"]):
                parts.append(place(L.bake(p), M))
        L.boolean(rail, place(cone_tool(L, "bore" + tag, R, pav, z_rail + 0.35), M), "DIFFERENCE")
        if pav > GIRDLE_H:                  # pavilion reaches into the silicone
            L.boolean(band, place(cone_tool(L, "pocket" + tag, R, pav, -GIRDLE_H + 0.6, clear=0.25), M),
                      "DIFFERENCE")

    L.engrave(band, prof, "RINFIT", phi_center=TEXT_PHI, on_inner=False, **TEXT)
    L.shade(band, True, sharp_angle=50)
    return [band, L.join(parts, "metal", metal)] + stones



