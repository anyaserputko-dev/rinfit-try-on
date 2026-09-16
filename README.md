# Rinfit Ring Try-On — concept prototype

A working prototype of a virtual ring try-on for a Shopify product page. Not an official Rinfit page.

**Live:** https://anyaserputko-dev.github.io/rinfit-try-on/

## What it does

- **3D view** — rotate and zoom the selected ring.
- **Live try-on** — the phone or laptop camera finds the hand and places the ring on the chosen finger in real time.
- **Photo** — the same try-on on an uploaded photo, for shoppers who do not want to turn the camera on.
- Switch rings, colors and fingers; save a snapshot.

Product names, prices, color options and photos come from rinfit.com (15 September 2026).

## How it works

- Hand tracking: [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) running in the browser. The camera image is processed on the device and never uploaded.
- Placement: the ring sits between the knuckle and the middle joint of the finger. Finger width is estimated from knuckle spacing, palm length and finger segment length. The stone faces the back of the hand.
- Realism: an invisible "finger" cylinder hides the back half of the ring, so the band wraps around the finger instead of floating on top.
- Rendering: three.js. Each ring is rebuilt from its product page: band width and thickness, stone cut and size, setting type, set composition, and colors sampled from the variant photos. Sets of two separate rings put the second ring on the neighbouring finger, as in Rinfit's lifestyle photos.
- Palm or back of the hand is decided by anatomy (the thumb sits on the palm side), not by the handedness label, which is unreliable on photos.
- A real GLB model can replace any procedural ring: add `model: { url, scale, bandLength }` to the product in `catalog.js`.

## Exact ring models (Blender)

Each ring is modelled in Blender 5.2 from its product page and images, then exported as GLB for the web app.

- `blender/rinfit.py` — modelling library: band cross-sections from the product sizes, faceted stones with true planar facets (brilliant family on any outline: round, oval, marquise, pear, rectangle), claws, rails, engraved or embossed lettering, materials, jewellery light tent, camera, Cycles render, GLB export.
- `blender/rings/<ring>.py` — one module per product: sizes and sources, setting details, camera views that match Rinfit's product renders.
- `blender/build.py` — builds a ring headless, renders the views, saves an editable `.blend`, exports `models/<ring>.glb`:
  `Blender -b --factory-startup -P blender/build.py -- ring=oval views=hero,nude export=1`
- `blender/compare.py` — side-by-side sheet: Rinfit product render next to ours, both cropped to the object.
- `blender/test_site.mjs` — headless check of the site (3D view and photo try-on) without a camera.

Model contract with the app: millimetres, ring axis along +Y, stone towards +Z, inner diameter 17.32 mm (US 7). Material names say what to recolour per variant: `Silicone_A` / `Silicone_B` (band colours), `Metal` (Silver or Rose Gold), `CZ` / `CZ_Black` (stones).

## Realtime stones

`gem.js` ray-traces each main stone in the browser. A cut stone is a convex solid, so the shader takes the facet planes straight from the GLB, refracts the view ray in, bounces it off the facets (total internal reflection and Fresnel) and lets it out with a little dispersion. The environment is the same light tent as the Blender renders, so the site and the renders read alike, and it works over live video because nothing depends on what is behind the stone.

## Files

| File | Purpose |
| --- | --- |
| `index.html` | Page layout and styles |
| `app.js` | Camera, hand tracking, ring placement, UI |
| `rings.js` | Procedural 3D ring models |
| `catalog.js` | Rinfit products used in the demo |

## Going from prototype to production

1. **Exact 3D models.** For a one-to-one match, export each product from Rinfit's manufacturing CAD files (or a 3D scan) as GLB and plug it in through `model` in `catalog.js`. The app already loads GLB files.
2. **Shopify integration.** Package as a theme app block on the product template: the block reads the product handle and selected variant, loads the matching model, and keeps color in sync with the variant picker and "Add to cart".
3. **Size helper (optional).** The same hand tracking can suggest a ring size, but it needs a reference object or calibration to be reliable.
4. **Analytics.** Track try-on opens, color switches and add-to-cart after try-on to measure the effect on conversion.

## Limitations of the prototype

- Procedural rings match the product sizes, cuts, settings and colors, but not factory-exact details such as the exact prong shape or the depth of engraved logos. Three sizes are estimated from photos because the product pages do not state them: the Solitaire band width and the V heights of Couture and the Black Oval set.
- Tracking works best with an open hand, back of the hand towards the camera, 30–50 cm away. Tightly curled fingers are less stable.
- Requires a modern browser with WebGL and camera access over HTTPS.
