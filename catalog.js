// Real Rinfit products (rinfit.com, 15.09.2026).
// Sizes come from product descriptions; colors are sampled from the variant photos.
// Values marked "est." are measured from photos because the description does not state them.
const IMG = (path) => `https://cdn.shopify.com/s/files/1/1471/8740/files/${path}?width=240`;
const PDP = (handle) => `https://www.rinfit.com/products/${handle}`;

export const SILICONE = {
  "White": "#ebebec", "Black": "#1e1e20", "Nude": "#dcc9b4", "Pink": "#f2d2d1",
  "Orchid Ice": "#e8dce3", "Soft Blue": "#d2dce7", "Teal Ocean": "#21646d", "Ocean": "#2a6a74",
  "Red": "#c21f30", "Olive": "#4f5530", "Blue": "#2f3ea8", "Light Gray": "#a6a7a9",
  "Steel Blue": "#4d6a86", // est.
  "Burgundy": "#9d5784", "Grayish Green": "#a3c1b7", "Pastel Pink": "#e3abbb",
  "Pastel Peach": "#deb6a6", "Pastel Purple": "#d3b7eb", "Grayish Purple": "#827b89",
  "Turquoise": "#5ccdbb", "Frosted Clear": "#eef2f3"
};
export const METAL = { "Silver": "#e4e5e8", "Rose Gold": "#d6a08c" };

export const bandHex = (ring, name) => ring.palette?.[name] || SILICONE[name] || "#cccccc";

// "White and Silver"                 -> bands [White],        metals [Silver]
// "Black and White Silver"           -> bands [Black, White], metals [Silver, Silver]  (set of 2)
// "Black Rose Gold and Black Silver" -> bands [Black, Black], metals [Rose Gold, Silver]
// "Teal Ocean Rose Gold"             -> bands [Teal Ocean],   metals [Rose Gold]
export function parseColor(name) {
  const parts = name.split(/\s+and\s+/i).map((p) => {
    const m = p.trim().match(/^(.*?)\s*(Rose Gold|Silver)?$/i);
    return { band: (m[1] || "").trim(), metal: m[2] ? (/rose/i.test(m[2]) ? "Rose Gold" : "Silver") : null };
  });
  let metal = "Silver";
  for (let i = parts.length - 1; i >= 0; i--) {
    if (parts[i].metal) metal = parts[i].metal;
    else parts[i].metal = metal;
  }
  const items = parts.filter((p) => p.band);
  return { bands: items.map((p) => p.band), metals: items.map((p) => p.metal) };
}

// spec.kind:  band    — plain silicone band
//             chevron — V-shaped stackable band with pyramid texture
//             stone   — band with a CZ stone in a metal setting
// spec.mount: basket (tall 4-prong basket) · high (raised prongs) · low (stone close to band) · halo
// model:      optional { url, scale, bandLength } — a real GLB file replaces the procedural ring
export const RINGS = [
  {
    id: "infinity-men", name: "Men's Infinity", family: "Infinity Collection · 9 mm", price: 16.99,
    colors: ["Blue", "Olive", "Red", "White"],
    view: "band",
    spec: { kind: "band", style: "step", width: 9, thickness: 2, finish: "matte", logo: true },
    img: IMG("infman1050-1-9_18d13299-ebbd-4335-af4f-eb156df55e3e.jpg"),
    url: PDP("copy-of-mens-infinity-silicone-ring-soft-comfortable-durable-wedding-band-us-design-patent")
  },
  {
    id: "step-edge", name: "Inner Step Edge", family: "Floating Collection · 9 mm", price: 16.99,
    colors: ["Light Gray", "Steel Blue"],
    view: "band",
    spec: { kind: "band", style: "dome", width: 9, thickness: 2, finish: "matte", innerStep: true, engrave: true },
    img: IMG("3_7c0bcd0d-3249-49bc-bb87-0ceab86d060c.jpg"),
    url: PDP("copy-of-inner-step-edge-collection-silicone-ring-for-men-patent-pending")
  },
  {
    id: "couture", name: "Couture Stackable", family: "Couture Collection · 2.5 mm", price: 9.99,
    colors: ["White", "Pastel Purple", "Turquoise", "Burgundy", "Pastel Pink", "Ocean"],
    palette: { "White": "#e9ecf1", "Ocean": "#2b6670" },
    view: "couture",
    spec: { kind: "chevron", width: 2.5, thickness: 2, amplitude: 4.8 /* est. */ },
    img: IMG("012_4da77e9a-5746-4fa3-9c15-6d8f81f5af33.jpg"),
    url: PDP("gift-ring-womens-couture-silicone-stackable-rings-stylish-design-comfortable-durable-wedding-band")
  },
  {
    id: "oval", name: "Thin Oval Cut CZ · 11×8 mm", family: "GlowStone Thin · 3 mm band", price: 49.99,
    colors: ["White and Silver", "Nude and Rose Gold", "Black and Silver"],
    view: "front",
    spec: { kind: "stone", cut: "oval", w: 8, l: 11, band: { width: 3, thickness: 2 }, mount: "high" },
    img: IMG("07_6365c2a0-4ca3-4672-9bfa-44dd1e56b4ae.jpg"),
    url: PDP("rinfit-thin-oval-cut")
  },
  {
    id: "emerald", name: "Emerald Cut CZ · 10×8 mm", family: "GlowStone Thin · 3 mm band", price: 49.99,
    colors: ["Nude and Rose Gold", "White and Silver", "Black and Silver"],
    view: "threeq",
    spec: { kind: "stone", cut: "emerald", w: 8, l: 10, band: { width: 3, thickness: 2 }, mount: "high", engrave: true },
    img: IMG("02_54337d16-8dd6-484d-8fdf-ac20182f73aa.jpg"),
    url: PDP("rinfit-thin-emerald-cut")
  },
  {
    id: "halo", name: "Halo Emerald CZ · 10×8 mm", family: "GlowStone Halo · 6 mm band", price: 59.99,
    colors: ["White and Silver", "Nude and Rose Gold", "Black and Silver"],
    view: "threeq",
    spec: { kind: "stone", cut: "emerald", w: 8, l: 10, band: { width: 6, thickness: 2, style: "dome" }, mount: "halo", engrave: true },
    img: IMG("020.jpg"),
    url: PDP("rinfit-halo-emerald-glowstone")
  },
  {
    id: "solitaire", name: "Round Solitaire CZ · 7 mm", family: "GlowStone · set of 2 rings", price: 79.99,
    colors: ["Black and White Silver", "Black and Nude Rose Gold", "Nude and Pink Rose Gold",
             "Black and Ocean Rose Gold", "Pink and Ocean Rose Gold", "Black Rose Gold and Black Silver"],
    palette: { "Pink": "#d9aca8", "Nude": "#ccb39f", "Ocean": "#2f6a73" },
    view: "threeq",
    spec: { kind: "stone", cut: "round", w: 7, l: 7, band: { width: 6 /* est. */, thickness: 2, style: "dome" }, mount: "basket", engrave: true, pair: "separate" },
    img: IMG("sst6.jpg"),
    url: PDP("2-ring-set-7mm-round-solitaire-cz-silicone-ring-glowstone")
  },
  {
    id: "princess", name: "Princess Cut CZ · 8×8 mm", family: "GlowStone · 2-ring stack", price: 59.99,
    colors: ["Nude and Rose Gold", "White and Silver", "Pink and Rose Gold", "Orchid Ice and Rose Gold", "Black and Rose Gold"],
    view: "top",
    spec: { kind: "stone", cut: "princess", w: 8, l: 8, band: { width: 6, thickness: 2 }, mount: "low", thin: { width: 3 } },
    img: IMG("Ring130_0950014.jpg"),
    url: PDP("silicone-ring-stackable-princess-cut-cz-2rings-set-thin")
  },
  {
    id: "marquise", name: "Marquise Cut CZ · 14×7 mm", family: "GlowStone · 2-ring stack", price: 59.99,
    colors: ["Pink and Rose Gold", "Nude and Rose Gold", "White and Silver", "Orchid Ice and Rose Gold", "Soft Blue and Silver", "Black and Rose Gold"],
    view: "top",
    spec: { kind: "stone", cut: "marquise", w: 7, l: 14, band: { width: 6, thickness: 2 }, mount: "low", thin: { width: 3 } },
    img: IMG("Ring_130_093_004.jpg"),
    url: PDP("silicone-ring-stackable-marquise-cut-cz-2rings-set-thin")
  },
  {
    id: "pear", name: "Pear Cut CZ · 8×12 mm", family: "GlowStone · 2-ring stack", price: 59.99,
    colors: ["Nude and Rose Gold", "White and Silver", "Orchid Ice and Rose Gold", "Pink and Rose Gold", "Soft Blue and Silver", "Black and Rose Gold", "Teal Ocean Rose Gold"],
    view: "top",
    spec: { kind: "stone", cut: "pear", w: 8, l: 12, band: { width: 6, thickness: 2 }, mount: "low", thin: { width: 3 } },
    img: IMG("02_0c7944f9-f6f3-480e-bfdd-c082475b7715.jpg"),
    url: PDP("silicone-ring-stackable-pear-cut-cz-2rings-set-thin")
  },
  {
    id: "frosted", name: "Frosted Clear · Round CZ", family: "GlowStone Thin · 3 mm band", price: 54.99,
    colors: ["Frosted Clear"],
    view: "front",
    spec: { kind: "stone", cut: "round", w: 7, l: 7, band: { width: 3, thickness: 2 }, mount: "high", frosted: true },
    img: IMG("main_round2..jpg"),
    url: PDP("frosted-clear-round")
  },
  {
    id: "black-oval", name: "Black Oval CZ · 12×8 mm", family: "GlowStone · 3-piece stack", price: 59.99,
    colors: ["Black and Rose Gold"],
    view: "top",
    spec: { kind: "stone", cut: "oval", w: 8, l: 12, band: { width: 6, thickness: 2 }, mount: "low", blackStone: true,
            chevrons: { width: 2, amplitude: 2.6 /* est. */ } },
    img: IMG("01_2_86588659-a271-489c-829e-dfdde773c45e.jpg"),
    url: PDP("silicone-ring-stackable-set-14x7-mm-marquise-cut-cz-patent-pending-design-glowstone-collection-copy")
  }
];
