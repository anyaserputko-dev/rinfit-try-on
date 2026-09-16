"""Exact-framing check for emerald / halo / princess (compare.py crops both images to their bbox, which fails
when the Rinfit photo cuts the ring at the image border).

  python3 blender/rings/_rect_overlay.py <ring> <view> <photo> <cam.json> <lens> [out_suffix]

The render (camera from _rect_fitcam.py, given lens) is warped into the photo's pixel frame with the fitted
scale/shift, then: photo | render | 50 % blend. -> blender/out/compare/<ring>_<view>_overlay.jpg
"""
import json, os, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ring, view, photo_name, cam_path, lens = sys.argv[1:6]
suffix = sys.argv[6] if len(sys.argv) > 6 else ""
lens = float(lens)
cam = json.load(open(cam_path))
photo = Image.open(os.path.join(HERE, "ref", ring, photo_name)).convert("RGB")
rend = Image.open(os.path.join(HERE, "out", "renders", f"{ring}_{view}.png")).convert("RGBA")
res = rend.width
white = Image.new("RGBA", rend.size, (255, 255, 255, 255))
rend = Image.alpha_composite(white, rend).convert("RGB")
k = cam["sc"] / (lens / 36.0 * res)          # photo px per render px
a = 1.0 / k
warped = rend.transform(photo.size, Image.AFFINE, (a, 0, res / 2 - cam["tx"] * a, 0, a, res / 2 - cam["ty"] * a),
                        resample=Image.BICUBIC, fillcolor=(255, 255, 255))
blend = Image.blend(photo, warped, 0.5)
# red rings = the photo points used for the camera fit (the render's features should sit on them)
fit_pts = []
for cand in (cam_path.replace("_sil_cam.json", ".json"), cam_path.replace("_cam.json", ".json")):
    if os.path.exists(cand):
        fit_pts = json.load(open(cand)).get("pts", [])
        break
for im in (photo, warped, blend):
    dd = ImageDraw.Draw(im)
    for p in fit_pts:
        dd.ellipse((p[3] - 14, p[4] - 14, p[3] + 14, p[4] + 14), outline=(230, 0, 0), width=4)
T = 760
tiles = [im.resize((T, T * photo.height // photo.width), Image.LANCZOS) for im in (photo, warped, blend)]
sheet = Image.new("RGB", (T * 3 + 40, tiles[0].height + 50), (236, 232, 228))
d = ImageDraw.Draw(sheet)
for i, (t, label) in enumerate(zip(tiles, ("Rinfit photo", "Blender render (same framing)", "50 % overlay"))):
    sheet.paste(t, (10 + i * (T + 10), 40))
    d.text((14 + i * (T + 10), 12), f"{ring} {view} · {label}", fill=(40, 40, 40))
out = os.path.join(HERE, "out", "compare", f"{ring}_{view}_overlay{suffix}.jpg")
sheet.save(out, quality=88)
print(out)
