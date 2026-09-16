"""Build one Rinfit ring in Blender (headless).

  Blender -b --factory-startup -P blender/build.py -- ring=oval [views=hero,side] [render=1] [export=1]
          [blend=1] [samples=160] [res=900]

A view in the ring module (VIEWS) holds: camera, color, optional studio settings, frame (auto-fit, default True),
margin and floor. Views with the same colour share one scene.

Outputs:
  blender/out/renders/<ring>_<view>.png   Cycles render (transparent background)
  models/<ring>.glb                       model for the web app (export=1)
  blender/out/blend/<ring>.blend          editable Blender file of the first view (blend=1)
"""
import sys, os, importlib, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "rings"))
import bpy
import rinfit as L

args = dict(a.split("=", 1) for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []))
ring_id = args["ring"]
mod = importlib.import_module(ring_id.replace("-", "_"))
view_names = args.get("views", args.get("view", "hero")).split(",")
t0 = time.time()
saved = False

for vn in view_names:
    view = mod.VIEWS[vn]
    color = view.get("color", mod.COLORS[0])
    scene_key = (color, view.get("scene", "hero"))
    if getattr(L, "_scene_key", None) != scene_key:
        L.clear_scene()
        objs = mod.build(L, color, scene=view.get("scene", "hero"))
        L._scene_key = scene_key
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
    if "floor" in view:
        L.shadow_floor(view["floor"])
    if args.get("blend", "1") == "1" and not saved:
        path = os.path.join(L.OUT_DIR, "blend", f"{ring_id}.blend")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
        saved = True
    if args.get("render", "1") == "1":
        out = os.path.join(L.OUT_DIR, "renders", f"{ring_id}_{vn}.png")
        t1 = time.time()
        L.render(out, res=int(args.get("res", 900)), samples=int(args.get("samples", 160)))
        print("RENDER %s %.1fs" % (out, time.time() - t1))

if args.get("export", "0") == "1":
    L.clear_scene()
    L._scene_key = None
    objs = mod.build(L, mod.COLORS[0], scene="glb")
    meshes = [o for o in objs if o.type == "MESH"]
    bands = [o for o in meshes if o.name.startswith("band") or o.name.startswith("chevron")] or meshes
    ys = [(o.matrix_world @ v.co).y for o in bands for v in o.data.vertices]
    path = os.path.join(L.PROJECT_DIR, "models", f"{ring_id}.glb")
    L.export_glb(meshes, path)
    # triangles, not faces: quads and ngons are triangulated on export (a quad counts twice)
    tris = sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons)
    print("GLB", path, "band_length=%.2f" % (max(ys) - min(ys)), "tris=%d" % tris,
          "size=%.1fMB" % (os.path.getsize(path) / 1e6))

print("DONE %.1fs" % (time.time() - t0))
