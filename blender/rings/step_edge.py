"""Rinfit Inner Step Edge Collection — Silicone Ring for Men (Floating Collection).
Product page: width 9 mm, thickness 2 mm. Colours Light Gray, Steel Blue.
Renders: img_00 Light Gray (hero), img_16 Steel Blue (same angle); img_05 infographic (inside unrolled).

Geometry (renders; estimates marked ~):
  - domed outside with large rounded edges
  - inside: raised rims at both edges touch the finger, recessed centre channel between them
  - in the channel, raised "infinity design" pattern: the Rinfit infinity mark (two square outlines at 45 deg
    sharing a long stem, same as on infinity-men) repeated round the ring, plus one RINFIT wordmark
"""
import math
import _band_helpers as H

COLORS = ["Light Gray", "Steel Blue"]
# Blender base colours, calibrated so the median body colour of our hero render matches each variant render
# (photo samples, sRGB: Light Gray #b4b4b4, Steel Blue #647b8d)
HEX = {"Light Gray": "#c1c1c1", "Steel Blue": "#648095"}

W, T = 9.0, 2.0
DOME = 0.55        # ~ outer crown drop to the edges (img_00: lit crown is ~60% of the width)
EDGE_OUT = 1.3     # ~ outer edge rounding
EDGE_IN = 0.22
RIM_W = 1.15       # ~ inner rim width (flat lip visible inside on img_00/img_16)
RECESS = 0.35      # ~ channel depth
RELIEF_TOP = 0.10  # relief stops this far below the rim surface
MARK_GAP = 0.4     # ~ gap between marks / text along the channel (mm)
MARK_W = 4.0       # ~ mark extent across the channel (mm)
MARK_ANGLE = -45   # stem at 45 deg to the band (as on infinity-men)
MARK_MIRROR = True # wrap_on_band mirrors x on the inner surface (phi = phi_c - x/r): mirror the mark so its
                   # handedness reads like the outside one while the pair keeps the stagger seen on img_00
WORD_H = 1.85       # ~ RINFIT letter height across the channel
WORD_CONDENSE = 0.72  # ring lettering is narrower than the website logo
WORD_PHI = math.radians(350)  # solved from the fitted hero camera (text position on img_16)

# fitted to the silhouette of img_16 (IoU + hole IoU, Workbench masks)
HERO_CAM = dict(direction=(-0.2288, 0.6120, -0.7570), up=(0.9248, -0.1062, -0.3654), target=(-0.383, -0.413, -0.218),
                dist=99.5, lens=145.0)
VIEWS = {
    "hero": dict(camera=HERO_CAM, frame=False, color="Light Gray"),
    "steel": dict(camera=HERO_CAM, frame=False, color="Steel Blue", photo="img_16.jpg"),
    "side": dict(camera=dict(direction=(1, 0, 0), up=(0, 0, 1), dist=90, lens=100), frame=False, color="Light Gray"),
    "inside": dict(camera=dict(direction=(0, -1, 0.0), up=(0, 0, 1), dist=60, lens=100), frame=False,
                   color="Light Gray"),
}


def r_out(L, y):
    return L.R_IN + T - DOME * min(1.0, abs(y) / (W / 2)) ** 2.2


def section(L):
    R = L.R_IN
    b = W / 2
    c = b - RIM_W
    rf = R + RECESS
    pts, radii = [], []
    # start inner left edge, go round: inner rim -> channel -> inner rim -> side -> outer dome -> side
    pts += [(R, -b), (R, -c), (rf, -c), (rf, c), (R, c), (R, b)]
    radii += [EDGE_IN, 0.08, 0.07, 0.07, 0.08, EDGE_IN]
    pts.append((r_out(L, b), b))
    radii.append(EDGE_OUT)
    n = 16
    ylim = b - EDGE_OUT * 1.25
    for k in range(n + 1):
        y = ylim - 2 * ylim * k / n
        pts.append((r_out(L, y), y))
        radii.append(0.0)
    pts.append((r_out(L, -b), -b))
    radii.append(EDGE_OUT)
    loop = H.rounded_poly(pts, radii, n=6)
    return H.Section(loop, W, lambda y: r_out(L, y), lambda y: rf if abs(y) < c else R)


def build(L, color, scene="hero"):
    hexv = HEX.get(color) or L.SILICONE.get(color, color)
    sil = L.mat_silicone(hexv, "Silicone_A")
    prof = section(L)
    band = L.revolve("band", prof.points, segments=180, mat=sil)
    band["band_width"] = W
    R = L.R_IN
    rf = R + RECESS                    # channel floor radius: arc lengths of the relief are laid out there
    height = RECESS - RELIEF_TOP
    word = H.svg_mesh(height=WORD_H, condense=WORD_CONDENSE)
    mark_loops = H.transform2d(H.infinity_mark_loops(), angle=math.radians(MARK_ANGLE))
    if MARK_MIRROR:
        mark_loops = [[(-x, y) for x, y in lp] for lp in mark_loops]
    mark_loops = H.fit_loops(mark_loops, height=MARK_W)
    lt = max(v.co.x for v in word.vertices) - min(v.co.x for v in word.vertices)
    lm = max(x for lp in mark_loops for x, _ in lp) - min(x for lp in mark_loops for x, _ in lp)
    circ = 2 * math.pi * rf
    n = int((circ - lt) // (lm + MARK_GAP))
    gap = (circ - lt - n * lm) / (n + 1)           # even gaps: text | mark | mark | ... | mark | text
    # wordmark reads bottom-to-top on img_00 / img_16 (rotate 180 deg on the inner surface)
    H.engrave_mesh(L, band, prof, word, phi_center=WORD_PHI, depth=height, emboss=True, on_inner=True,
                   rotate=math.pi, below=0.25)
    for k in range(n):
        arc = lt / 2 + gap + lm / 2 + k * (lm + gap)
        me = H.loops_mesh(mark_loops, max_seg=0.3)
        H.engrave_mesh(L, band, prof, me, phi_center=WORD_PHI + arc / rf, depth=height, emboss=True, on_inner=True,
                       below=0.25)
    band["relief_marks"] = n
    L.shade(band, True, sharp_angle=35)
    return [band]
