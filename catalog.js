// Real Rinfit products (rinfit.com/products.json, 15.09.2026).
// Stone sizes come from product titles. Render colors are approximations of the named colors.
const IMG = (path) => `https://cdn.shopify.com/s/files/1/1471/8740/files/${path}?width=240`;
const PDP = (handle) => `https://www.rinfit.com/products/${handle}`;

export const SILICONE = {
  "White": "#f1efea", "Red": "#b3302c", "Olive": "#6a6f45", "Blue": "#2f4d7d",
  "Light Gray": "#b8bbbc", "Atlantic Blue": "#2a5b78", "Steel Blue": "#4f6f8f",
  "Burgundy": "#6b2233", "Grayish Green": "#8d9e8c", "Pink": "#e597ad",
  "Pastel Pink": "#f2c4cd", "Pastel Peach": "#f4c7a9", "Pastel Purple": "#cbb5de",
  "Grayish Purple": "#9b8ca4", "Turquoise": "#3db5ad", "Ocean": "#2d7c97",
  "Nude": "#d6b49e", "Black": "#1d1d20", "Soft Blue": "#9fc0dc", "Orchid Ice": "#d9c3e3",
  "Teal Ocean": "#2f7d86", "Frosted Clear": "#e8eef0"
};
export const METAL = { "Silver": "#d7dade", "Rose Gold": "#d9a08b" };

// "Nude and Rose Gold" -> { band: Nude, metal: Rose Gold }
export function parseColor(name) {
  const m = name.match(/^(.*?)\s+and\s+(.*)$/i) || name.match(/^(.*?)\s+((?:\w+\s+)?(?:Rose Gold|Silver))$/i);
  if (!m) return { band: name, metal: null };
  const band = m[1].trim();
  const metal = /rose gold/i.test(m[2]) ? "Rose Gold" : "Silver";
  return { band, metal };
}

export const RINGS = [
  {
    id: "infinity-men", name: "Men's Infinity", family: "Silicone band", price: 16.99,
    colors: ["Olive", "Blue", "Red", "White"],
    shape: { type: "band", width: 8.2, thickness: 2.1, grooves: 0 },
    img: IMG("infman1050-1-9_18d13299-ebbd-4335-af4f-eb156df55e3e.jpg"),
    url: PDP("copy-of-mens-infinity-silicone-ring-soft-comfortable-durable-wedding-band-us-design-patent")
  },
  {
    id: "step-edge", name: "Inner Step Edge", family: "Silicone band", price: 16.99,
    colors: ["Steel Blue", "Light Gray"],
    shape: { type: "band", width: 8.0, thickness: 2.2, grooves: 2 },
    img: IMG("3_7c0bcd0d-3249-49bc-bb87-0ceab86d060c.jpg"),
    url: PDP("copy-of-inner-step-edge-collection-silicone-ring-for-men-patent-pending")
  },
  {
    id: "couture", name: "Couture Stackable", family: "Thin stackable", price: 9.99,
    colors: ["Pastel Pink", "Turquoise", "Burgundy", "Grayish Green", "Pastel Purple", "White"],
    shape: { type: "stack", width: 2.4, thickness: 1.7, count: 3 },
    img: IMG("012_4da77e9a-5746-4fa3-9c15-6d8f81f5af33.jpg"),
    url: PDP("gift-ring-womens-couture-silicone-stackable-rings-stylish-design-comfortable-durable-wedding-band")
  },
  {
    id: "oval", name: "Thin Oval Cut CZ", family: "GlowStone", price: 49.99,
    colors: ["White and Silver", "Nude and Rose Gold", "Black and Silver"],
    shape: { type: "stone", cut: "oval", w: 8, l: 12, width: 2.8, thickness: 1.8 },
    img: IMG("07_6365c2a0-4ca3-4672-9bfa-44dd1e56b4ae.jpg"),
    url: PDP("rinfit-thin-oval-cut")
  },
  {
    id: "emerald", name: "Emerald Cut CZ · 10×8 mm", family: "GlowStone", price: 49.99,
    colors: ["Nude and Rose Gold", "White and Silver", "Black and Silver"],
    shape: { type: "stone", cut: "emerald", w: 8, l: 10, width: 2.8, thickness: 1.8 },
    img: IMG("02_54337d16-8dd6-484d-8fdf-ac20182f73aa.jpg"),
    url: PDP("rinfit-thin-emerald-cut")
  },
  {
    id: "halo", name: "Halo Emerald CZ · 10×8 mm", family: "GlowStone", price: 59.99,
    colors: ["White and Silver", "Nude and Rose Gold", "Black and Silver"],
    shape: { type: "stone", cut: "emerald", w: 8, l: 10, width: 2.8, thickness: 1.8, halo: true },
    img: IMG("020.jpg"),
    url: PDP("rinfit-halo-emerald-glowstone")
  },
  {
    id: "solitaire", name: "Round Solitaire CZ · 7 mm", family: "GlowStone set of 2", price: 79.99,
    colors: ["Black and White Silver", "Nude and Pink Rose Gold", "Black and Nude Rose Gold"],
    shape: { type: "stone", cut: "round", w: 7, l: 7, width: 2.6, thickness: 1.8, stackBand: true },
    img: IMG("sst6.jpg"),
    url: PDP("2-ring-set-7mm-round-solitaire-cz-silicone-ring-glowstone")
  },
  {
    id: "princess", name: "Princess Cut CZ · 8×8 mm", family: "GlowStone set of 2", price: 59.99,
    colors: ["Pink and Rose Gold", "Nude and Rose Gold", "White and Silver", "Orchid Ice and Rose Gold"],
    shape: { type: "stone", cut: "princess", w: 8, l: 8, width: 2.8, thickness: 1.8, stackBand: true },
    img: IMG("Ring130_0950014.jpg"),
    url: PDP("silicone-ring-stackable-princess-cut-cz-2rings-set-thin")
  },
  {
    id: "marquise", name: "Marquise Cut CZ · 14×7 mm", family: "GlowStone set of 2", price: 59.99,
    colors: ["Soft Blue and Silver", "Pink and Rose Gold", "White and Silver", "Black and Rose Gold"],
    shape: { type: "stone", cut: "marquise", w: 7, l: 14, width: 2.8, thickness: 1.8, stackBand: true },
    img: IMG("Ring_130_093_004.jpg"),
    url: PDP("silicone-ring-stackable-marquise-cut-cz-2rings-set-thin")
  },
  {
    id: "pear", name: "Pear Cut CZ · 8×12 mm", family: "GlowStone set of 2", price: 59.99,
    colors: ["Teal Ocean Rose Gold", "Nude and Rose Gold", "White and Silver", "Black and Rose Gold"],
    shape: { type: "stone", cut: "pear", w: 8, l: 12, width: 2.8, thickness: 1.8, stackBand: true },
    img: IMG("02_0c7944f9-f6f3-480e-bfdd-c082475b7715.jpg"),
    url: PDP("silicone-ring-stackable-pear-cut-cz-2rings-set-thin")
  },
  {
    id: "frosted", name: "Frosted Clear · Round CZ", family: "Frosted Clear", price: 54.99,
    colors: ["Frosted Clear"],
    shape: { type: "stone", cut: "round", w: 7, l: 7, width: 2.6, thickness: 1.8, frosted: true },
    img: IMG("main_round2..jpg"),
    url: PDP("frosted-clear-round")
  },
  {
    id: "black-oval", name: "Black Oval CZ · 12×8 mm", family: "GlowStone stackable set", price: 59.99,
    colors: ["Black and Rose Gold"],
    shape: { type: "stone", cut: "oval", w: 8, l: 12, width: 2.8, thickness: 1.8, blackStone: true, stackBand: true },
    img: IMG("01_2_86588659-a271-489c-829e-dfdde773c45e.jpg"),
    url: PDP("silicone-ring-stackable-set-14x7-mm-marquise-cut-cz-patent-pending-design-glowstone-collection-copy")
  }
];
