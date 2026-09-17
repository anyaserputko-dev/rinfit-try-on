"""Rinfit MetalBar Collection - men's silicone wedding ring with a stainless steel strip.

Product page (rinfit.com/products/metalbarcollection-silicone-rings-for-men, $24.99):
  Width 8 mm | Thickness 2 mm | rubber silicone + stainless steel strip | matte-brushed finish
  Colours: "Black and Gunmetal Gray", "Black and Gold" | sizes 7-13 (men's)

Read off the CAD heroes 00_mr2 (gunmetal) and 09_mr3 (gold), which are the same ring from the same camera:
  - one plain domed band, matte black, rounded edges, no step or ledge
  - a steel strip that follows the band's own outer surface flush, running the FULL width of the band and only
    a short arc round the ring; its two edges are straight lines across the band, its finish polished (the
    silicone around it is matte, which is what makes it read as a separate part)
  - the inside carries Rinfit's chevron relief (grip / breathing channels) and the RINFIT wordmark, both
    debossed - through the ring's hole they are the only thing you see, so they are modelled, not faked

Sizes here are US 10 (men's middle of the range, inner Ø 19.76 mm), not the US 7 the women's rings use.
Band shape, strip arc and the camera are fitted to the hero silhouette by blender/fit/fit_metal_bar.py.
"""
import math
import _band_helpers as H

COLORS = ["Black and Gunmetal Gray", "Black and Gold"]
PALETTE = {                       # (силікон, метал)
    "Black and Gunmetal Gray": ("#1c1c1e", "#8c9095"),
    "Black and Gold": ("#1c1c1e", "#cfa53c"),
}

W, T = 8.0, 2.0
R_IN = 8.655                     # підігнано по фото (≈ US 7 за таблицею Rinfit)
BAND = dict(width=W, thickness=1.65, dome=0.55, inner_dome=0.25, edge_out=0.91, edge_in=0.70)
ROUGH = 0.62                      # matte-brushed силікон
STRIP = dict(arc=4.61, lift=0.02, depth=0.30, rough=0.16)   # довжина дуги, виступ, товщина, шорсткість металу
CHEVRON = dict(count=13, stroke=0.95, rise=3.0, depth=0.32, span=0.74)
WORD = dict(height=2.35, phi=146.0, rot=180.0, depth=0.22, clear=64.0)
# phi — туди, де в hero видно нутро; clear — чистий сектор під напис: RINFIT на цьому радіусі
# займає ~120° дуги, і якщо шеврони в нього залазять, спільний інструмент стає самоперетинним
STRIP_PHI = 318.5                 # де сидить смуга (градуси від верху)

HERO = dict(direction=(-0.6460, -0.4067, 0.6460), up=(0.4540, 0.0, 0.8910), target=(0, 0, 0), dist=102.4, lens=95)
VIEWS = {
    "hero": dict(camera=HERO, frame=False, color="Black and Gunmetal Gray"),
    "gold": dict(camera=HERO, frame=False, color="Black and Gold"),
    "side": dict(camera=dict(direction=(1, 0.1, 0.25), up=(0, 0, 1), dist=150, lens=100), frame=False),
    "top": dict(camera=dict(direction=(0.05, -0.1, 1), up=(0, 1, 0), dist=150, lens=100), frame=False),
}


def chevron_loops(stroke, rise, half_w):
    """Одна «стрілка» — V-подібний штрих упоперек внутрішньої поверхні (x — навколо кільця, y — вздовж пальця)."""
    return [[(-rise / 2, -half_w), (rise / 2, 0.0), (-rise / 2, half_w),
             (-rise / 2 + stroke, half_w), (rise / 2 + stroke, 0.0), (-rise / 2 + stroke, -half_w)]]


def strip_mesh(L, name, prof, phi_c, arc, lift, depth, mat, n_phi=40, n_y=24):
    """Сталева смуга: та сама поверхня, що й у ободка, підняті на `lift`, на дузі `arc` мм, на всю ширину."""
    half = arc / (2 * (prof.inner + prof.thickness))          #半 кут дуги
    b = prof.width / 2
    phis = [phi_c - half + 2 * half * i / n_phi for i in range(n_phi + 1)]
    ys = [-b + 2 * b * j / n_y for j in range(n_y + 1)]
    ro = [prof.outer_r(y) + lift for y in ys]
    ri = [prof.outer_r(y) - depth for y in ys]

    def P(r, phi, y):
        return (r * math.sin(phi), y, r * math.cos(phi))

    nyv = n_y + 1
    verts, faces = [], []
    for phi in phis:
        for j, y in enumerate(ys):
            verts.append(P(ro[j], phi, y))
    k0 = len(verts)
    for phi in phis:
        for j, y in enumerate(ys):
            verts.append(P(ri[j], phi, y))
    for i in range(n_phi):
        for j in range(n_y):
            a, c = i * nyv + j, (i + 1) * nyv + j
            faces.append((a, a + 1, c + 1, c))
            a, c = k0 + i * nyv + j, k0 + (i + 1) * nyv + j
            faces.append((a, c, c + 1, a + 1))
    for j in range(n_y):                                       # торці дуги
        faces.append((j, k0 + j, k0 + j + 1, j + 1))
        a, c = n_phi * nyv + j, k0 + n_phi * nyv + j
        faces.append((a, a + 1, c + 1, c))
    for i in range(n_phi):                                     # краї по ширині ободка
        faces.append((i * nyv, (i + 1) * nyv, k0 + (i + 1) * nyv, k0 + i * nyv))
        faces.append((i * nyv + n_y, k0 + i * nyv + n_y, k0 + (i + 1) * nyv + n_y, (i + 1) * nyv + n_y))
    ob = L.mesh_object(name, verts, faces, mat, smooth=True)
    L.fix_normals(ob)
    L.shade(ob, True, sharp_angle=32)
    return ob


def build(L, color, scene="hero"):
    sil_hex, met_hex = PALETTE.get(color, PALETTE[COLORS[0]])
    sil = L.mat_silicone(sil_hex, "Silicone_A", roughness=ROUGH)
    met = L.mat_metal(met_hex, "Metal", roughness=STRIP["rough"])

    prof = L.BandProfile(inner=R_IN, **BAND)
    band = L.band("band", prof, sil, segments=200)

    # Шеврони й напис ріжуться ОДНИМ інструментом і ОДНИМ булевим.
    # ⚠️ Два EXACT-булеві поспіль по цьому ободку ламають меш (після першого лишаються T-стики — другий
    # тихо віддає 178 вершин замість 20 тисяч). А щоб один інструмент не був самоперетинним, під напис
    # лишається чистий сектор WORD["clear"], у якому шевронів не ставимо.
    half_w = prof.width / 2 * CHEVRON["span"]
    word_phi = math.radians(WORD["phi"])
    clear = math.radians(WORD["clear"])          # сектор, залишений під напис
    tools = []
    for k in range(CHEVRON["count"]):
        phi = 2 * math.pi * k / CHEVRON["count"] + word_phi + math.pi
        if abs((phi - word_phi + math.pi) % (2 * math.pi) - math.pi) < clear:
            continue
        me = H.loops_mesh(chevron_loops(CHEVRON["stroke"], CHEVRON["rise"], half_w), depth=1.0, max_seg=0.35)
        tools.append(L.wrap_on_band(me, prof, phi, 0.0, below=CHEVRON["depth"], above=0.6, on_inner=True))
    word = H.svg_mesh(height=WORD["height"], depth=1.0)
    tools.append(L.wrap_on_band(word, prof, word_phi, 0.0, below=WORD["depth"], above=0.6,
                                on_inner=True, rotate=math.radians(WORD["rot"])))
    L.boolean(band, L.join(tools, "inner_tool"), "DIFFERENCE")
    if not len(band.data.vertices):
        raise RuntimeError("boolean з'їв ободок — інструмент самоперетинний")
    L.shade(band, True, sharp_angle=35)

    strip = strip_mesh(L, "strip", prof, math.radians(STRIP_PHI), STRIP["arc"], STRIP["lift"],
                       STRIP["depth"], met)
    return [band, strip]
