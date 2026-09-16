"""Grid of several renders warped into the photo frame (emerald / halo / princess helper).

  python3 blender/rings/_rect_grid.py <ring> <photo> <cam.json> <lens> <x0,y0,x1,y1> <view1,view2,...> <out_name>
"""
import json, os, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ring, photo_name, cam_path, lens, box, views, out_name = sys.argv[1:8]
lens = float(lens)
box = tuple(int(v) for v in box.split(","))
views = views.split(",")
cam = json.load(open(cam_path))
photo = Image.open(os.path.join(HERE, "ref", ring, photo_name)).convert("RGB")
tiles = [("photo", photo.crop(box))]
for v in views:
    r = Image.open(os.path.join(HERE, "out", "renders", f"{ring}_{v}.png")).convert("RGBA")
    res = r.width
    r = Image.alpha_composite(Image.new("RGBA", r.size, (255, 255, 255, 255)), r).convert("RGB")
    a = (lens / 36 * res) / cam["sc"]
    w = r.transform(photo.size, Image.AFFINE, (a, 0, res / 2 - cam["tx"] * a, 0, a, res / 2 - cam["ty"] * a),
                    resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    tiles.append((v, w.crop(box)))
cols = min(4, len(tiles))
T = 520
th = int(T * (box[3] - box[1]) / (box[2] - box[0]))
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (T * cols + 10 * (cols + 1), (th + 25) * rows + 10), (236, 232, 228))
d = ImageDraw.Draw(sheet)
for i, (label, t) in enumerate(tiles):
    x = 10 + (i % cols) * (T + 10)
    y = 22 + (i // cols) * (th + 25)
    sheet.paste(t.resize((T, th), Image.LANCZOS), (x, y))
    d.text((x + 4, y - 16), label, fill=(0, 0, 0))
out = os.path.join(HERE, "out", "compare", out_name)
sheet.save(out, quality=88)
print(out)
