"""Rinfit Women's Couture Silicone Stackable Ring (Couture Collection).
Product page: width 2.5 mm, thickness 2 mm.
Renders: img_00 White (hero), img_05..img_13 the same angle in the other colours; img_02 lifestyle (studs, V, lettering).

Geometry (measured on the renders, estimates marked ~):
  - flat-sided band, flat inside, one row of square pyramid studs over the full outer width, all round the ring
  - V (chevron) peak at phi = 0: the band shifts along the finger, arms are straight in the unrolled band
  - RINFIT wordmark (fonts/rinfit_wordmark_ring.svg, R with stem as on the rings) debossed inside opposite the V
"""
import math
import _band_helpers as H

COLORS = ["White", "Burgundy", "Grayish Green", "Pink", "Pastel Pink", "Pastel Peach", "Pastel Purple",
          "Grayish Purple", "Turquoise", "Ocean"]
# Blender base colours, calibrated so the median body colour of our hero render matches each variant render
# (photo samples, sRGB: White #e4e7ec, Pastel Purple #cfb2e9, Grayish Purple #898290, Grayish Green #a5c1b8,
#  Burgundy #a55e8b, Ocean #2e6e77, Pastel Pink #e4acbc, Pastel Peach #e3bcac, Turquoise #61d2c0, Pink #fadade)
HEX = {
    "White": "#f5f8fe", "Pastel Purple": "#ddbdfa", "Grayish Purple": "#908798", "Grayish Green": "#b0cec4",
    "Burgundy": "#af5b92", "Ocean": "#186e7a", "Pastel Pink": "#f5b7c9", "Pastel Peach": "#f4c8b7",
    "Turquoise": "#60e0cd", "Pink": "#ffe9ee",
}

W, T = 2.5, 2.0          # page
STUD_H = 0.47            # ~ pyramid height (silhouette sawtooth amplitude measured on img_09, incl. in the 2 mm)
N_STUDS = 36             # studs round the ring (counted on img_09: ~7 studs per arc where 26 gave ~5)
V_H = 3.6                # ~ V peak offset along the finger (mm)
V_PHI = math.radians(75) # ~ half-angle of the V region
V_SOFT = 0.18            # rounding where the V arms join the plain circle (fraction of V_PHI)
EDGE_IN = 0.18           # inner corner fillet
WORD_H = 1.75            # ~ letter height of RINFIT inside (img_00 / img_09)
WORD_TRACK = 0.35        # ~ extra letter spacing (mm), couture lettering is spaced wider than the logo

# fitted to the silhouette of the variant renders (IoU + hole IoU, Workbench masks)
HERO_CAM = dict(direction=(-0.2657, -0.4092, 0.8729), up=(0.9327, 0.1199, 0.3401), target=(-0.413, 1.612, 0.630),
                dist=99.5, lens=149.2)
VIEWS = {
    "hero": dict(camera=HERO_CAM, frame=False, color="White"),
    "side": dict(camera=dict(direction=(1, 0, 0), up=(0, 0, 1), dist=90, lens=100), frame=False, color="White"),
    "top": dict(camera=dict(direction=(0, 0, 1), up=(0, 1, 0), dist=90, lens=100), frame=False, color="White"),
    "front": dict(camera=dict(direction=(0, -1, 0), up=(0, 0, 1), dist=90, lens=100), frame=False, color="White"),
}
for _c, _img in (("Pastel Purple", "img_05"), ("Grayish Purple", "img_06"), ("Grayish Green", "img_07"),
                 ("Burgundy", "img_08"), ("Ocean", "img_09"), ("Pastel Pink", "img_10"), ("Pastel Peach", "img_11"),
                 ("Turquoise", "img_12"), ("Pink", "img_13")):
    VIEWS[_c.lower().replace(" ", "_")] = dict(camera=HERO_CAM, frame=False, color=_c, photo=_img + ".jpg")


def y_of_phi(phi):
    a = abs(math.atan2(math.sin(phi), math.cos(phi)))
    x = 1.0 - a / V_PHI
    e = V_SOFT
    if x >= e:
        s = x
    elif x <= -e:
        s = 0.0
    else:
        s = (x + e) ** 2 / (4 * e)
    return V_H * s


def build_band(L, mat, name="band"):
    R = L.R_IN
    ro = R + T - STUD_H
    b = W / 2
    f = EDGE_IN
    # cross-section loop: (kind, r, y); kind "o" = outer stud row
    sec = [("o", ro, -b), ("o", ro, 0.0), ("o", ro, b)]
    sec += [("s", R + f, b)]
    for k in range(1, 4):
        t = k / 4
        # quadratic fillet corner at (R, b)
        p0, p1, p2 = (R + f, b), (R, b), (R, b - f)
        sec.append(("s", (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    n_in = 8
    for k in range(n_in + 1):
        sec.append(("i", R, (b - f) - (2 * b - 2 * f) * k / n_in))
    for k in range(1, 4):
        t = k / 4
        p0, p1, p2 = (R, -b + f), (R, -b), (R + f, -b)
        sec.append(("s", (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    sec.append(("s", R + f, -b))
    ns = len(sec)
    cols = 2 * N_STUDS
    verts, faces = [], []
    for i in range(cols):
        phi = math.pi * i / N_STUDS
        dy = y_of_phi(phi)
        s, c = math.sin(phi), math.cos(phi)
        apex_col = i % 2 == 0
        for j, (kind, r, y) in enumerate(sec):
            if kind == "o" and apex_col and j == 1:
                r = ro + STUD_H
            verts.append((r * s, y + dy, r * c))
    for i in range(cols):
        i2 = (i + 1) % cols
        for j in range(ns):
            j2 = (j + 1) % ns
            A, B, C, D = i * ns + j, i * ns + j2, i2 * ns + j2, i2 * ns + j
            if j in (0, 1):
                # stud cell: split along the diagonal through the apex (even column, row 1)
                apex = i * ns + 1 if i % 2 == 0 else i2 * ns + 1
                if apex in (A, B, C, D):
                    k = (A, B, C, D).index(apex)
                    q = (A, B, C, D)[k:] + (A, B, C, D)[:k]
                    faces.append((q[0], q[1], q[2]))
                    faces.append((q[0], q[2], q[3]))
                    continue
            faces.append((A, B, C, D))
    ob = L.mesh_object(name, verts, faces, mat, smooth=True)
    L.fix_normals(ob)
    prof = H.Section(None, W, lambda y: ro, lambda y: R)
    ob["band_width"] = W
    return ob, prof


def build(L, color, scene="hero"):
    hexv = HEX.get(color) or L.SILICONE.get(color, color)
    sil = L.mat_silicone(hexv, "Silicone_A")
    band, prof = build_band(L, sil)
    word = H.svg_mesh(height=WORD_H, tracking=WORD_TRACK)
    H.engrave_mesh(L, band, prof, word, phi_center=math.pi, depth=0.15, on_inner=True, rotate=0.0)
    L.shade(band, True, sharp_angle=22)
    return [band]
