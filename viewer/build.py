"""Вшити GLB у сторінку-переглядач (GLB як окремий файл артефакт не віддає).

  python3 viewer/build.py [ring]        ring = three_stone (типово) або metal_bar
"""
import base64, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RING = sys.argv[1] if len(sys.argv) > 1 else "three_stone"
glb = base64.b64encode(open(os.path.join(HERE, "..", "models", RING + ".glb"), "rb").read()).decode()
# gem.js лежить поруч зі сторінкою (артефакт віддає лише файли з власної теки), але джерело правди
# — один файл у корені проєкту: копіюємо щоразу, щоб копія не розходилась
shutil.copyfile(os.path.join(HERE, "..", "gem.js"), os.path.join(HERE, "gem.js"))
html = open(os.path.join(HERE, RING + ".src.html")).read().replace("__GLB_BASE64__", glb)
out = os.path.join(HERE, RING + ".html")
open(out, "w").write(html)
print("%s  %.1f МБ" % (out, len(html) / 1e6))
