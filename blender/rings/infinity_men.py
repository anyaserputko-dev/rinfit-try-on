"""Rinfit Men's Infinity Silicone Ring (Infinity Collection).
Product page: width 9 mm, thickness 2 mm, matte-brushed finish. Colours Red, White, Olive, Blue.
Renders: img_00 Blue (hero), img_01 Olive, img_02 Red, img_03 White — all the same angle.

Geometry (renders; estimates marked ~):
  - raised flat main band with a lower step ledge along BOTH edges (the far ledge is foreshortened on img_00,
    visible on the far edge of img_00/img_01), rounded outer edges, flat inside with rounded inner edges
  - Rinfit infinity mark (two square outlines at 45 deg sharing a long stem, H.infinity_mark_loops) debossed on the main band
  - RINFIT wordmark (fonts/rinfit_wordmark_ring.svg: rinfit.com logo letters, R rebuilt with the stem and counter
    seen on the ring) debossed on the inner surface, roughly opposite the mark
"""
import math
import _band_helpers as H

COLORS = ["Blue", "Olive", "Red", "White"]
# Blender base colours, calibrated so the median body colour of our hero render matches each variant render
# (photo samples, sRGB: Blue #3240ab, Olive #4c522d, Red #c2202f, White #e0e1e3). Red stays ~12 levels
# less saturated than the photo even at full base saturation (silicone subsurface + specular).
HEX = {"Blue": "#2237b8", "Olive": "#474f19", "Red": "#d1061d", "White": "#f3f4f7"}

W, T = 9.0, 2.0
LEDGE_W = 2.0     # ~ each step ledge width (main band ~55% of the width on img_00/img_01)
STEP = 0.45        # ~ step height (main band above the ledges)
EDGE_OUT = 0.45    # ~ outer ledge corner radius
EDGE_IN = 0.5      # ~ inner corner radius
MAIN_DOME = 0.06   # ~ main band crown
ROUGH = 0.62

# fitted to the silhouette of img_00 (IoU + hole IoU, Workbench masks)
HERO_CAM = dict(direction=(-0.2936, 0.5253, -0.7986), up=(0.9168, -0.0818, -0.3908), target=(-0.345, -0.487, -0.193),
                dist=104.6, lens=153.6)
VIEWS = {
    "hero": dict(camera=HERO_CAM, frame=False, color="Blue"),
    "olive": dict(camera=HERO_CAM, frame=False, color="Olive", photo="img_01.jpg"),
    "red": dict(camera=HERO_CAM, frame=False, color="Red", photo="img_02.jpg"),
    "white": dict(camera=HERO_CAM, frame=False, color="White", photo="img_03.jpg"),
    "side": dict(camera=dict(direction=(1, 0, 0), up=(0, 0, 1), dist=90, lens=100), frame=False, color="Blue"),
    "top": dict(camera=dict(direction=(0, 0, 1), up=(0, 1, 0), dist=90, lens=100), frame=False, color="Blue"),
}


def section(L):
    R = L.R_IN
    b = W / 2
    bm = b - LEDGE_W
    rT, rL = R + T, R + T - STEP
    pts = [(R, -b), (rL, -b), (rL, -bm), (rT - MAIN_DOME, -bm)]
    radii = [EDGE_IN, EDGE_OUT, 0.06, 0.12]
    n = 10
    for k in range(1, n):
        y = -bm + 2 * bm * k / n
        pts.append((rT - MAIN_DOME * (y / bm) ** 2, y))
        radii.append(0.0)
    pts += [(rT - MAIN_DOME, bm), (rL, bm), (rL, b), (R, b)]
    radii += [0.12, 0.06, EDGE_OUT, EDGE_IN]
    loop = H.rounded_poly(pts, radii, n=5)

    def outer(y):
        return rT - MAIN_DOME * min(1.0, (y / bm) ** 2) if abs(y) <= bm else rL

    return H.Section(loop, W, outer, lambda y: R)


def mat(L, color):
    hexv = HEX.get(color) or L.SILICONE.get(color, color)
    m = L.mat_silicone(hexv, "Silicone_A", roughness=ROUGH)
    return m


def build(L, color, scene="hero"):
    sil = mat(L, color)
    prof = section(L)
    band = L.revolve("band", prof.points, segments=180, mat=sil)
    band["band_width"] = W

    # infinity mark on the main band (phi = 0)
    # stem runs at +45 deg in (round-the-ring, along-the-finger) space, loops sit along the ring (img_00/img_03)
    loops = H.transform2d(H.infinity_mark_loops(), angle=math.radians(-45))
    me = H.loops_mesh(H.fit_loops(loops, height=LOGO_H), max_seg=0.3)
    H.engrave_mesh(L, band, prof, me, phi_center=LOGO_PHI, depth=0.2, rotate=math.radians(LOGO_ROT))

    word = H.svg_mesh(height=WORD_H)
    H.engrave_mesh(L, band, prof, word, phi_center=WORD_PHI, depth=0.2, on_inner=True, rotate=math.radians(WORD_ROT))
    L.shade(band, True, sharp_angle=35)
    return [band]


LOGO_H = 3.5       # ~ mark extent along the finger (mm)
LOGO_PHI = math.radians(188)   # solved from the fitted hero camera (logo position on img_00)
LOGO_ROT = 0.0
WORD_H = 2.6       # ~ cap height of RINFIT on the inside
WORD_PHI = math.radians(12)    # solved from the fitted hero camera (text position on img_00)
WORD_ROT = 180.0               # reads bottom-to-top on img_00
