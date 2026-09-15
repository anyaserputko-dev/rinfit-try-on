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
- Rendering: three.js. Rings are generated in code from each product's shape (band, stackable set, stone cut and size from the product title).

## Files

| File | Purpose |
| --- | --- |
| `index.html` | Page layout and styles |
| `app.js` | Camera, hand tracking, ring placement, UI |
| `rings.js` | Procedural 3D ring models |
| `catalog.js` | Rinfit products used in the demo |

## Going from prototype to production

1. **Exact 3D models.** Replace procedural rings with GLB models of each product (from CAD files or a 3D scan), including patterns such as Infinity or Eagle.
2. **Shopify integration.** Package as a theme app block on the product template: the block reads the product handle and selected variant, loads the matching model, and keeps color in sync with the variant picker and "Add to cart".
3. **Size helper (optional).** The same hand tracking can suggest a ring size, but it needs a reference object or calibration to be reliable.
4. **Analytics.** Track try-on opens, color switches and add-to-cart after try-on to measure the effect on conversion.

## Limitations of the prototype

- 3D rings are simplified renders, not exact product geometry.
- Tracking works best with an open hand, back of the hand towards the camera, 30–50 cm away. Tightly curled fingers are less stable.
- Requires a modern browser with WebGL and camera access over HTTPS.
