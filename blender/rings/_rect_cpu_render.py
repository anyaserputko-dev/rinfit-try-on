"""CPU twin of build.py for emerald / halo / princess (the shared Metal GPU stalls when several agents render at once).

  Blender -b --factory-startup -P blender/rings/_rect_cpu_render.py -- ring=halo views=hero,info samples=96 res=700
          [threads=6] [export=1] [blend=1]

Same scenes, studio, cameras and output paths as build.py; only the device differs (rinfit.render(..., gpu=False)).
"""
import sys, os, importlib, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "rings"))
import bpy
import rinfit as L

args = dict(a.split("=", 1) for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
ring_id = args["ring"]
mod = importlib.import_module(ring_id.replace("-", "_"))
view_names = args.get("views", "hero").split(",")
t0 = time.time()
saved = False
scene_key = None
objs = []

for vn in view_names:
    view = mod.VIEWS[vn]
    color = view.get("color", mod.COLORS[0])
    key = (color, view.get("scene", "hero"))
    if key != scene_key:
        L.clear_scene()
        objs = mod.build(L, color, scene=view.get("scene", "hero"))
        scene_key = key
    for name in ("cam", "floor"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    for ob in [o for o in bpy.data.objects if o.get("studio")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    for ob in L.studio(**view.get("studio", {})):
        ob["studio"] = True
    cam = L.camera(**view["camera"])
    if view.get("frame", True):
        L.frame_camera(cam, [o for o in objs if o.type == "MESH" and not o.get("studio")], margin=view.get("margin", 1.08))
    if args.get("blend", "0") == "1" and not saved:
        path = os.path.join(L.OUT_DIR, "blend", f"{ring_id}.blend")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        saved = True
    if args.get("render", "1") == "1":
        sc = bpy.context.scene
        if "threads" in args:
            sc.render.threads_mode = "FIXED"
            sc.render.threads = int(args["threads"])
        out = os.path.join(L.OUT_DIR, "renders", f"{ring_id}_{vn}.png")
        t1 = time.time()
        L.render(out, res=int(args.get("res", 900)), samples=int(args.get("samples", 160)), gpu=False)
        print("RENDER %s %.1fs" % (out, time.time() - t1))

if args.get("export", "0") == "1":
    L.clear_scene()
    objs = mod.build(L, mod.COLORS[0], scene="glb")
    meshes = [o for o in objs if o.type == "MESH"]
    bands = [o for o in meshes if o.name.startswith("band") or o.name.startswith("chevron")] or meshes
    ys = [(o.matrix_world @ v.co).y for o in bands for v in o.data.vertices]
    path = os.path.join(L.PROJECT_DIR, "models", f"{ring_id}.glb")
    L.export_glb(meshes, path)
    print("GLB", path, "band_length=%.2f" % (max(ys) - min(ys)), "tris=%d" % sum(len(o.data.polygons) for o in meshes))

print("DONE %.1fs" % (time.time() - t0))
