"""One sheet with every ring: Rinfit product render on the left, ours on the right.

  python3 blender/sheet_all.py            -> blender/out/compare/all_rings.jpg
Uses the per-ring sheets already made by compare.py (blender/out/compare/<ring>_hero.jpg).
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
COMPARE = os.path.join(HERE, "out", "compare")
RINGS = [("oval", "Thin Oval Cut CZ 11x8"), ("emerald", "Thin Emerald Cut CZ 10x8"),
         ("halo", "Halo Emerald CZ 10x8"), ("solitaire", "Round Solitaire CZ 7 mm, set of 2"),
         ("princess", "Princess Cut CZ 8x8"), ("marquise", "Marquise Cut CZ 14x7"),
         ("pear", "Pear Cut CZ 8x12"), ("frosted", "Frosted Clear, round CZ"),
         ("black-oval", "Black Oval Cut CZ 12x8"), ("couture", "Couture stackable 2.5 mm"),
         ("infinity-men", "Men's Infinity 9 mm"), ("step-edge", "Inner Step Edge 9 mm")]
W = 1100          # width of one ring row
font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 26)
small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)

rows = []
for rid, title in RINGS:
    path = os.path.join(COMPARE, f"{rid}_hero.jpg")
    if not os.path.exists(path):
        print("missing", path)
        continue
    im = Image.open(path).convert("RGB")
    im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
    rows.append((title, im))

if rows:
    pad, head = 14, 40
    cols = 2
    col_h = [0, 0]
    placed = []
    for title, im in rows:
        c = 0 if col_h[0] <= col_h[1] else 1
        placed.append((c, col_h[c], title, im))
        col_h[c] += im.height + head + pad
    sheet = Image.new("RGB", (cols * (W + pad) + pad, max(col_h) + pad), (238, 235, 232))
    d = ImageDraw.Draw(sheet)
    for c, y, title, im in placed:
        x = pad + c * (W + pad)
        d.text((x + 4, y + pad + 6), title, fill=(60, 58, 54), font=font)
        d.text((x + W - 300, y + pad + 10), "left: rinfit.com   right: Blender", fill=(150, 60, 60), font=small)
        sheet.paste(im, (x, y + pad + head))
    out = os.path.join(COMPARE, "all_rings.jpg")
    sheet.save(out, quality=88)
    print(out, sheet.size)
