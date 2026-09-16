"""Side-by-side check: Rinfit product photo (left) vs our Blender render (right), both cropped to the object.

  python3 blender/compare.py <ring> [view=hero] [photo=img_00.jpg]   ->  blender/out/compare/<ring>_<view>.jpg
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
ring = sys.argv[1]
opts = dict(a.split("=", 1) for a in sys.argv[2:])
view = opts.get("view", "hero")
photo_path = os.path.join(HERE, "ref", ring, opts.get("photo", "img_00.jpg"))
render_path = os.path.join(HERE, "out", "renders", f"{ring}_{view}{opts.get('suffix', '')}.png")
T = int(opts.get("size", 900))


def crop_photo(im):
    g = im.convert("L").point(lambda v: 255 if v < 244 else 0)
    box = g.getbbox() or (0, 0, *im.size)
    return im.crop(box)


def crop_render(im):
    white = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return crop_photo(Image.alpha_composite(white, im).convert("RGB"))


def fit(im):
    im = im.copy()
    im.thumbnail((T - 40, T - 40), Image.LANCZOS)
    bg = Image.new("RGB", (T, T), (255, 255, 255))
    bg.paste(im, ((T - im.width) // 2, (T - im.height) // 2))
    return bg


photo = fit(crop_photo(Image.open(photo_path).convert("RGB")))
render = fit(crop_render(Image.open(render_path).convert("RGBA")))
sheet = Image.new("RGB", (T * 2 + 30, T + 50), (236, 232, 228))
d = ImageDraw.Draw(sheet)
font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24)
d.text((12, 12), f"{ring} · Rinfit photo", fill=(120, 20, 20), font=font)
d.text((T + 42, 12), f"Blender render · {view}", fill=(20, 60, 120), font=font)
sheet.paste(photo, (10, 45))
sheet.paste(render, (T + 20, 45))
out = os.path.join(HERE, "out", "compare", f"{ring}_{view}{opts.get('suffix', '')}.jpg")
os.makedirs(os.path.dirname(out), exist_ok=True)
sheet.save(out, quality=90)
print(out)
