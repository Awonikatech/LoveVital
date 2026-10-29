"""Static seed data for the demo catalog (also drives image generation)."""

CATEGORIES = [
    # (slug, name, parent_slug, description, order)
    ("jewellery", "Jewellery", None, "Handcrafted artificial jewellery — kundan, temple, oxidised and contemporary.", 1),
    ("earrings", "Earrings", "jewellery", "Jhumkas, chandbalis, studs and hoops.", 1),
    ("necklaces", "Necklaces & Sets", "jewellery", "Chokers, kundan sets, temple necklaces and layered haars.", 2),
    ("bangles", "Bangles & Kadas", "jewellery", "Stackable bangles and statement kadas.", 3),
    ("bracelets", "Bracelets", "jewellery", "Charm, chain and cuff bracelets.", 4),
    ("rings", "Rings", "jewellery", "Cocktail, traditional and adjustable rings.", 5),
    ("pendants", "Pendants", "jewellery", "Pendant necklaces for everyday elegance.", 6),
    ("anklets-tikkas", "Anklets & Maang Tikkas", "jewellery", "Payals, anklets and maang tikkas.", 7),
    ("silver-oxidised", "Silver & Oxidised", None, "Silver-look and oxidised pieces with a boho soul.", 2),
    ("oxidised-earrings", "Oxidised Earrings", "silver-oxidised", "Tribal, boho and German-silver earrings.", 1),
    ("silver-sets", "Silver-look Sets", "silver-oxidised", "Necklace sets in rhodium and oxidised finishes.", 2),
    ("ethnic-wear", "Ethnic Wear", None, "Kurtis, sarees, anarkalis and festive ensembles.", 3),
    ("kurtis", "Kurtis & Kurtas", "ethnic-wear", "Everyday and festive kurtis.", 1),
    ("sarees", "Sarees", "ethnic-wear", "Silk, georgette and chiffon sarees.", 2),
    ("ethnic-dresses", "Ethnic Dresses", "ethnic-wear", "Anarkalis and flared ethnic dresses.", 3),
    ("western-wear", "Western Wear", None, "Tops, trousers and co-ords for work and weekends.", 4),
    ("tops", "Tops", "western-wear", "Blouses, peplums and everyday tops.", 1),
    ("trousers", "Trousers & Palazzos", "western-wear", "Tailored trousers and flowy palazzos.", 2),
    ("coord-sets", "Co-ord Sets", "western-wear", "Matching sets, effortlessly put together.", 3),
    ("festive-bridal", "Festive & Bridal", None, "Showstoppers for weddings and festivals.", 5),
    ("bridal-jewellery", "Bridal Jewellery", "festive-bridal", "Statement bridal sets and heirloom-look pieces.", 1),
    ("festive-apparel", "Festive Apparel", "festive-bridal", "Lehengas and festive ensembles.", 2),
]

CATEGORY_ART = {
    # slug: (art, metal, gem, bg, fabric)
    "jewellery": ("kundan-set", "gold", "emerald", "champagne", None),
    "earrings": ("jhumka", "gold", "ruby", "blush", None),
    "necklaces": ("choker", "gold", "ruby", "ivory", None),
    "bangles": ("bangles", "gold", "emerald", "sand", None),
    "bracelets": ("bracelet", "rose-gold", "amethyst", "blush", None),
    "rings": ("ring", "gold", "sapphire", "powder", None),
    "pendants": ("pendant", "rose-gold", "ruby", "blush", None),
    "anklets-tikkas": ("tikka", "gold", "pearl", "ivory", None),
    "silver-oxidised": ("chandbali", "oxidised", "onyx", "sage", None),
    "oxidised-earrings": ("chandbali", "oxidised", "emerald", "sage", None),
    "silver-sets": ("temple", "silver", "sapphire", "powder", None),
    "ethnic-wear": ("anarkali", "gold", "ruby", "blush", "#7B1E2B"),
    "kurtis": ("kurti", "gold", "ruby", "ivory", "#1F6F50"),
    "sarees": ("saree", "gold", "ruby", "sand", "#8E1B3A"),
    "ethnic-dresses": ("anarkali", "gold", "ruby", "champagne", "#2F4CA0"),
    "western-wear": ("peplum", "gold", "ruby", "powder", "#E8B4B8"),
    "tops": ("top", "silver", "pearl", "powder", "#F4EDE0"),
    "trousers": ("palazzo", "gold", "pearl", "sand", "#1F2A44"),
    "coord-sets": ("coord", "gold", "pearl", "blush", "#D9A520"),
    "festive-bridal": ("lehenga", "gold", "ruby", "champagne", "#B3202A"),
    "bridal-jewellery": ("kundan-set", "antique-gold", "ruby", "champagne", None),
    "festive-apparel": ("lehenga", "gold", "emerald", "blush", "#6E1D3B"),
}

COLLECTIONS = [
    # slug, name, description, featured, order
    ("festive-edit", "The Festive Edit", "Kundan, zari and jewel tones for Diwali, Karva Chauth and every celebration in between.", True, 1),
    ("heritage-gold", "Heritage Gold", "Temple motifs and antique finishes inspired by South Indian heirlooms.", True, 2),
    ("everyday-minimal", "Everyday Minimal", "Light, wearable pieces that go from desk to dinner.", True, 3),
    ("wedding-season", "Wedding Season", "Bridal sets and showstopper lehengas for the big day.", True, 4),
    ("boho-oxidised", "Boho Oxidised", "Tribal silhouettes in oxidised German silver.", False, 5),
]
COLLECTION_ART = {
    "festive-edit": ("kundan-set", "gold", "emerald", "blush", None),
    "heritage-gold": ("temple", "antique-gold", "ruby", "sand", None),
    "everyday-minimal": ("pendant", "rose-gold", "pearl", "powder", None),
    "wedding-season": ("lehenga", "gold", "ruby", "champagne", "#9E1B32"),
    "boho-oxidised": ("chandbali", "oxidised", "onyx", "sage", None),
}

BANNER_ART = [
    # name, art, metal, gem, bg, fabric, flip
    ("hero-festive", "kundan-set", "gold", "emerald", "champagne", None, False),
    ("hero-jhumka", "jhumka", "gold", "ruby", "blush", None, False),
    ("hero-saree", "saree", "gold", "ruby", "sand", "#8E1B3A", False),
    ("promo-bridal", "lehenga", "gold", "ruby", "champagne", "#9E1B32", True),
    ("promo-minimal", "pendant", "rose-gold", "pearl", "powder", None, True),
]

SWATCH = {
    "Gold": "#D4AF37", "Rose Gold": "#E0A899", "Silver": "#C0C0C0", "Oxidised": "#5D5A55", "Antique Gold": "#B08D57",
    "Maroon": "#7B1E2B", "Emerald Green": "#1F6F50", "Royal Blue": "#2F4CA0", "Mustard": "#D9A520", "Ivory": "#F4EDE0",
    "Black": "#1C1C1C", "Blush Pink": "#E8B4B8", "Teal": "#1F7A7A", "Lavender": "#B9A3D8", "White": "#FAFAFA",
    "Navy": "#1F2A44", "Peach": "#F5B895", "Beige": "#D8C3A5", "Olive": "#6B7A3A", "Red": "#B3202A", "Wine": "#6E1D3B",
    "Magenta": "#A3195B", "Sage": "#9CAF88",
}
METAL_OF = {"Gold": "gold", "Rose Gold": "rose-gold", "Silver": "silver", "Oxidised": "oxidised", "Antique Gold": "antique-gold"}

ATTRIBUTES = [
    # code, name, display, axis, order, values
    ("color", "Colour", "swatch", True, 1, list(SWATCH)),
    ("size", "Size", "button", True, 2, ["XS", "S", "M", "L", "XL", "XXL", "Free Size", "Adjustable", "6", "7", "8", "2.4", "2.6", "2.8"]),
    ("material", "Base Material", "text", False, 3, ["Brass", "Alloy", "Copper", "German Silver"]),
    ("plating", "Plating", "text", False, 4, ["Gold-plated", "Rose gold-plated", "Rhodium-plated", "Oxidised", "Antique gold-plated", "Matte gold-plated"]),
    ("stone", "Stone", "text", False, 5, ["Kundan", "Pearl", "American Diamond (CZ)", "Ruby-tone", "Emerald-tone", "Polki-look", "Meenakari", "No stone"]),
    ("style", "Style", "text", False, 6, ["Traditional", "Contemporary", "Fusion", "Minimal", "Statement", "Boho", "Casual", "Formal"]),
    ("fabric", "Fabric", "text", False, 7, ["Cotton", "Rayon", "Georgette", "Silk Blend", "Chiffon", "Crepe", "Linen Blend", "Chanderi", "Organza", "Viscose"]),
    ("fit", "Fit", "text", False, 8, ["Straight", "A-line", "Flared", "Regular", "Relaxed", "Slim", "Wide-leg"]),
    ("sleeve", "Sleeve", "text", False, 9, ["Sleeveless", "Short", "Three-quarter", "Full", "Puff"]),
    ("occasion", "Occasion", "text", False, 10, ["Festive", "Wedding", "Daily Wear", "Office", "Party"]),
]

APPAREL_SIZES = ["S", "M", "L", "XL", "XXL"]
SIZE_CHART_TOP = {
    "unit": "inches",
    "columns": ["Size", "Bust", "Waist", "Hip", "Length"],
    "rows": [["S", "36", "32", "38", "44"], ["M", "38", "34", "40", "44"], ["L", "40", "36", "42", "45"],
             ["XL", "42", "38", "44", "45"], ["XXL", "44", "40", "46", "46"]],
    "note": "Garment measurements. If you are between sizes, choose the larger size for a relaxed fit.",
}
SIZE_CHART_BOTTOM = {
    "unit": "inches",
    "columns": ["Size", "Waist", "Hip", "Length", "Inseam"],
    "rows": [["S", "28", "38", "39", "28"], ["M", "30", "40", "39", "28"], ["L", "32", "42", "40", "29"],
             ["XL", "34", "44", "40", "29"], ["XXL", "36", "46", "41", "29"]],
    "note": "Elasticated waist fits ±2 inches.",
}
SIZE_CHART_RING = {"unit": "mm", "columns": ["Indian Size", "Inner Diameter", "Circumference"],
                   "rows": [["6", "15.3", "48.0"], ["7", "15.6", "49.0"], ["8", "16.0", "50.3"]],
                   "note": "Adjustable rings fit Indian sizes 6–14."}
SIZE_CHART_BANGLE = {"unit": "inches", "columns": ["Size", "Inner Diameter"], "rows": [["2.4", "2.25"], ["2.6", "2.38"], ["2.8", "2.5"]],
                     "note": "Measure the widest part of your hand with fingers together."}

JW_CARE = ("Keep away from water, perfume and moisture. Wipe gently with a soft dry cloth after use and store in the "
           "LoveVital pouch provided, separately from other pieces, to preserve the plating.")
AP_CARE = {
    "Cotton": "Machine wash cold with like colours. Do not bleach. Tumble dry low. Warm iron on reverse.",
    "Rayon": "Gentle hand wash in cold water. Dry in shade. Iron on low heat.",
    "Georgette": "Dry clean recommended for the first wash. Hand wash gently thereafter. Do not wring.",
    "Silk Blend": "Dry clean only. Store wrapped in a muslin cloth. Iron on silk setting.",
    "Chiffon": "Dry clean only. Steam to remove creases.",
    "Crepe": "Gentle machine wash cold. Line dry. Low iron.",
    "Linen Blend": "Machine wash cold, gentle cycle. Iron while slightly damp.",
    "Chanderi": "Dry clean only.",
    "Organza": "Dry clean only. Steam lightly.",
    "Viscose": "Hand wash cold. Dry flat in shade.",
}


def jw(sku, name, cat, art, mrp, sale, *, colors=("Gold",), gem="ruby", bg="ivory", sizes=None, stone="Kundan", style="Traditional",
       material="Brass", occasion="Festive", weight=None, flags="", collections=(), desc="", tags=(), stock=40, cost_pct=0.32,
       processing=1, returnable=True, plating=None, chart=None):
    return dict(kind="jewellery", sku=sku, name=name, cat=cat, art=art, mrp=mrp, sale=sale, colors=list(colors), gem=gem, bg=bg,
                sizes=sizes, attrs={"stone": stone, "style": style, "material": material, "occasion": occasion}, plating=plating,
                weight=weight, flags=flags, collections=list(collections), desc=desc, tags=list(tags), stock=stock, cost_pct=cost_pct,
                processing=processing, returnable=returnable, chart=chart)


def ap(sku, name, cat, art, mrp, sale, *, colors=("Maroon",), fabric="Rayon", fit="Straight", sleeve="Three-quarter", style="Traditional",
       occasion="Daily Wear", sizes=APPAREL_SIZES, flags="", collections=(), desc="", tags=(), stock=14, cost_pct=0.38, processing=2,
       bg="ivory", chart="top"):
    return dict(kind="apparel", sku=sku, name=name, cat=cat, art=art, mrp=mrp, sale=sale, colors=list(colors), gem="ruby", bg=bg,
                sizes=list(sizes) if sizes else None, attrs={"fabric": fabric, "fit": fit, "sleeve": sleeve, "style": style, "occasion": occasion},
                weight=None, flags=flags, collections=list(collections), desc=desc, tags=list(tags), stock=stock, cost_pct=cost_pct,
                processing=processing, returnable=True, plating=None, chart=chart)


RAW = [
    # ---------------- earrings
    jw("JW-EAR-001", "Gold-Plated Traditional Earrings", "earrings", "jhumka", 999, 499, colors=("Gold",), gem="ruby", bg="blush",
       stone="Ruby-tone", flags="featured,bestseller", collections=("festive-edit",), stock=50, weight=28,
       desc="Our signature temple jhumkas, hand-finished in 22k gold-tone plating with ruby-tone stones and a cascade of seed pearls. "
            "Lightweight enough for an all-night celebration.", tags=("jhumka", "temple", "festive")),
    jw("JW-EAR-002", "Meenakari Peacock Jhumkas", "earrings", "jhumka", 1499, 849, colors=("Gold", "Antique Gold"), gem="emerald", bg="sage",
       stone="Meenakari", flags="featured", collections=("festive-edit", "heritage-gold"), weight=34,
       desc="Hand-painted meenakari peacocks crown these bell jhumkas, finished with emerald-tone drops and pearl fringes.",
       tags=("jhumka", "peacock", "meenakari")),
    jw("JW-EAR-003", "Kundan Chandbali Earrings", "earrings", "chandbali", 1899, 1099, colors=("Gold", "Rose Gold"), gem="kundan", bg="champagne",
       stone="Kundan", style="Statement", flags="bestseller", collections=("festive-edit", "wedding-season"), weight=32,
       desc="Crescent chandbalis set with uncut-look kundan and edged with luminous faux pearls — a wedding-season essential."),
    jw("JW-EAR-004", "American Diamond Floral Studs", "earrings", "studs", 899, 449, colors=("Silver", "Gold", "Rose Gold"), gem="kundan", bg="powder",
       stone="American Diamond (CZ)", style="Minimal", occasion="Office", flags="new", collections=("everyday-minimal",), weight=6, plating="Rhodium-plated",
       desc="Eight-petal studs pavé-set with brilliant-cut CZ that catch the light from every angle.", tags=("studs", "cz", "office")),
    jw("JW-EAR-005", "Pearl Drop Studs", "earrings", "studs", 699, 399, colors=("Gold", "Silver"), gem="pearl", bg="ivory", stone="Pearl",
       style="Minimal", occasion="Daily Wear", collections=("everyday-minimal",), weight=5,
       desc="A luminous faux pearl framed by a delicate gold-tone floral setting."),
    jw("JW-EAR-006", "Textured Gold Hoops", "earrings", "hoops", 799, 479, colors=("Gold", "Rose Gold", "Silver"), gem="topaz", bg="sand",
       stone="No stone", style="Contemporary", occasion="Party", flags="new", collections=("everyday-minimal",), weight=12,
       desc="Hammered-texture hoops with a click-top closure. Wear them from brunch to after-hours.", tags=("hoops",)),
    # ---------------- oxidised
    jw("JW-OXE-001", "Oxidised Silver Chandbalis", "oxidised-earrings", "chandbali", 899, 449, colors=("Oxidised",), gem="onyx", bg="sage",
       stone="No stone", style="Boho", material="German Silver", occasion="Daily Wear", plating="Oxidised", flags="bestseller",
       collections=("boho-oxidised",), weight=24, desc="Tribal-inspired chandbalis in oxidised German silver with ghungroo fringes."),
    jw("JW-OXE-002", "Oxidised Mirror Jhumkas", "oxidised-earrings", "jhumka", 749, 399, colors=("Oxidised",), gem="sapphire", bg="powder",
       stone="No stone", style="Boho", material="German Silver", occasion="Daily Wear", plating="Oxidised", collections=("boho-oxidised",),
       weight=26, desc="Mirror-work domes and beaded drops — the ultimate kurta companion."),
    jw("JW-OXE-003", "Afghani Tribal Hoops", "oxidised-earrings", "hoops", 699, 349, colors=("Oxidised",), gem="emerald", bg="sage",
       stone="Emerald-tone", style="Boho", material="German Silver", occasion="Daily Wear", plating="Oxidised", flags="new",
       collections=("boho-oxidised",), weight=18, desc="Oversized engraved hoops with emerald-tone accents."),
    # ---------------- necklaces
    jw("JW-NCK-001", "Ruby Kundan Choker Set", "necklaces", "choker", 3999, 1999, colors=("Gold",), gem="ruby", bg="blush", stone="Kundan",
       style="Statement", occasion="Wedding", flags="featured,bestseller", collections=("festive-edit", "wedding-season"), weight=86, stock=25,
       desc="A regal choker of kundan diamonds and ruby-tone stones with pearl drops, paired with matching earrings.", tags=("choker", "set", "bridal")),
    jw("JW-NCK-002", "Emerald Kundan Necklace Set", "necklaces", "kundan-set", 4499, 2699, colors=("Gold", "Antique Gold"), gem="emerald", bg="champagne",
       stone="Kundan", style="Statement", occasion="Wedding", flags="featured", collections=("festive-edit", "wedding-season"), weight=110, stock=20,
       desc="Emerald-tone drops and kundan florets on a graduated collar, complete with matching studs."),
    jw("JW-NCK-003", "Lakshmi Temple Necklace", "necklaces", "temple", 3499, 2299, colors=("Antique Gold",), gem="ruby", bg="sand",
       stone="Ruby-tone", style="Traditional", occasion="Festive", plating="Antique gold-plated", flags="bestseller",
       collections=("heritage-gold",), weight=95, stock=18, desc="Hand-chased Lakshmi coin motifs and a ruby-tone pendant, inspired by Chettinad heirlooms."),
    jw("JW-NCK-004", "Layered Pearl Rani Haar", "necklaces", "layered", 2999, 1799, colors=("Gold",), gem="pearl", bg="ivory", stone="Pearl",
       style="Traditional", occasion="Wedding", collections=("wedding-season", "heritage-gold"), weight=120, stock=15,
       desc="Two cascading strands of faux pearls and gold beads finished with a statement pendant."),
    jw("JW-NCK-005", "Sapphire Statement Collar", "necklaces", "choker", 2799, 1599, colors=("Gold", "Silver"), gem="sapphire", bg="powder",
       stone="American Diamond (CZ)", style="Contemporary", occasion="Party", flags="new", weight=72, stock=16,
       desc="Midnight-blue stones and CZ pavé for cocktail evenings."),
    # ---------------- silver sets
    jw("JW-SLV-001", "Silver-look Temple Necklace Set", "silver-sets", "temple", 2499, 1299, colors=("Silver", "Oxidised"), gem="sapphire", bg="powder",
       stone="No stone", style="Fusion", material="German Silver", plating="Rhodium-plated", flags="featured", collections=("boho-oxidised",),
       weight=80, desc="A silver-look temple necklace with matching earrings — fusion styling for sarees and Indo-western looks.",
       tags=("silver", "necklace set")),
    jw("JW-SLV-002", "Oxidised Coin Choker Set", "silver-sets", "choker", 1999, 999, colors=("Oxidised",), gem="onyx", bg="sage", stone="No stone",
       style="Boho", material="German Silver", plating="Oxidised", collections=("boho-oxidised",), weight=76,
       desc="Antique coin choker with drop earrings — the boho staple."),
    # ---------------- bangles
    jw("JW-BNG-001", "Kundan Bangle Set of 4", "bangles", "bangles", 1999, 1099, colors=("Gold",), gem="emerald", bg="sand", stone="Kundan",
       sizes=["2.4", "2.6", "2.8"], flags="bestseller", collections=("festive-edit",), weight=90, chart="bangle",
       desc="Four slim bangles set with kundan and emerald-tone stones. Sold as a set of four.", tags=("bangles", "set")),
    jw("JW-BNG-002", "Artificial Glass Bangles — Bridal Stack", "bangles", "bangles", 1299, 749, colors=("Red", "Maroon", "Emerald Green"), gem="ruby",
       bg="blush", stone="No stone", material="Alloy", occasion="Wedding", sizes=["2.4", "2.6", "2.8"], collections=("wedding-season",),
       weight=110, chart="bangle", desc="A 24-piece bridal stack of glass-finish bangles with gold-tone accent kadas."),
    jw("JW-BNG-003", "Antique Peacock Kada", "bangles", "kada", 1599, 999, colors=("Antique Gold", "Gold"), gem="ruby", bg="champagne",
       stone="Polki-look", style="Statement", sizes=["2.4", "2.6", "2.8"], collections=("heritage-gold",), weight=60, chart="bangle",
       desc="A single screw-open kada with peacock engravings and polki-look stones."),
    jw("JW-BNG-004", "CZ Slim Kada Pair", "bangles", "kada", 1499, 899, colors=("Rose Gold", "Gold", "Silver"), gem="kundan", bg="powder",
       stone="American Diamond (CZ)", style="Minimal", occasion="Office", sizes=["2.4", "2.6", "2.8"], flags="new", collections=("everyday-minimal",),
       weight=40, chart="bangle", desc="Two sleek kadas with a single line of channel-set CZ."),
    # ---------------- bracelets
    jw("JW-BRC-001", "Charm Bracelet with Evil Eye", "bracelets", "bracelet", 999, 549, colors=("Rose Gold", "Gold"), gem="sapphire", bg="blush",
       stone="No stone", style="Contemporary", occasion="Daily Wear", flags="bestseller", collections=("everyday-minimal",), weight=14,
       desc="Dainty chain with evil-eye and heart charms; adjustable length 6.5–8 inches."),
    jw("JW-BRC-002", "Pearl & Gold Chain Bracelet", "bracelets", "chain-bracelet", 849, 499, colors=("Gold", "Silver"), gem="pearl", bg="ivory",
       stone="Pearl", style="Minimal", occasion="Office", collections=("everyday-minimal",), weight=10, desc="Paperclip links with a single pearl station."),
    jw("JW-BRC-003", "Amethyst Tennis Bracelet", "bracelets", "bracelet", 1799, 1099, colors=("Silver", "Rose Gold"), gem="amethyst", bg="powder",
       stone="American Diamond (CZ)", style="Contemporary", occasion="Party", flags="new", weight=16, plating="Rhodium-plated",
       desc="Violet and clear CZ alternate in a classic tennis line with box clasp."),
    # ---------------- rings
    jw("JW-RNG-001", "Traditional Ruby Cocktail Ring", "rings", "ring", 899, 449, colors=("Gold", "Antique Gold"), gem="ruby", bg="blush",
       stone="Ruby-tone", style="Traditional", sizes=["Adjustable"], flags="bestseller", collections=("heritage-gold",), weight=8, chart="ring",
       desc="A ruby-tone centre stone held in a temple-style setting on an adjustable band.", tags=("ring", "adjustable")),
    jw("JW-RNG-002", "Solitaire CZ Ring", "rings", "ring", 799, 399, colors=("Silver", "Rose Gold", "Gold"), gem="kundan", bg="powder",
       stone="American Diamond (CZ)", style="Minimal", occasion="Daily Wear", sizes=["6", "7", "8"], collections=("everyday-minimal",), weight=4,
       chart="ring", plating="Rhodium-plated", desc="A brilliant-cut CZ solitaire on a slim band."),
    jw("JW-RNG-003", "Emerald Kundan Finger Ring Pair", "rings", "ring-pair", 1199, 649, colors=("Gold",), gem="emerald", bg="sage",
       stone="Kundan", style="Traditional", occasion="Wedding", sizes=["Adjustable"], collections=("wedding-season",), weight=12, chart="ring",
       desc="Two stackable rings with emerald-tone and kundan clusters."),
    # ---------------- pendants
    jw("JW-PND-001", "Ruby Teardrop Pendant Necklace", "pendants", "pendant", 1199, 699, colors=("Rose Gold", "Gold"), gem="ruby", bg="blush",
       stone="Ruby-tone", style="Contemporary", occasion="Party", flags="featured", collections=("everyday-minimal",), weight=9,
       desc="A faceted ruby-tone teardrop framed in a halo of CZ, on an 18-inch chain."),
    jw("JW-PND-002", "Sapphire Halo Pendant", "pendants", "pendant", 1299, 799, colors=("Silver", "Gold"), gem="sapphire", bg="powder",
       stone="American Diamond (CZ)", style="Minimal", occasion="Office", flags="new", weight=8, plating="Rhodium-plated",
       desc="Deep blue stone ringed with CZ — subtle sparkle for every day."),
    jw("JW-PND-003", "Emerald Drop Pendant", "pendants", "pendant", 1099, 649, colors=("Gold",), gem="emerald", bg="sage", stone="Emerald-tone",
       style="Fusion", occasion="Festive", collections=("festive-edit",), weight=9, desc="An emerald-tone drop on a fine box chain."),
    # ---------------- anklets & tikka
    jw("JW-ANK-001", "Ghungroo Anklets (Pair)", "anklets-tikkas", "anklet", 999, 549, colors=("Silver", "Gold", "Oxidised"), gem="pearl", bg="ivory",
       stone="No stone", style="Traditional", occasion="Festive", collections=("boho-oxidised",), weight=40,
       desc="Musical ghungroo payals with an adjustable hook. Sold as a pair."),
    jw("JW-TKA-001", "Kundan Maang Tikka", "anklets-tikkas", "tikka", 1299, 699, colors=("Gold", "Rose Gold"), gem="kundan", bg="champagne",
       stone="Kundan", style="Traditional", occasion="Wedding", flags="featured", collections=("wedding-season",), weight=18,
       desc="A chandbali-shaped tikka with kundan and pearl drops."),
    # ---------------- bridal
    jw("JW-BRD-001", "Polki-look Bridal Necklace Set", "bridal-jewellery", "kundan-set", 9999, 5999, colors=("Antique Gold",), gem="ruby", bg="champagne",
       stone="Polki-look", style="Statement", occasion="Wedding", plating="Antique gold-plated", flags="featured", collections=("wedding-season",),
       weight=180, stock=8, processing=2, returnable=False,
       desc="Our most opulent set: polki-look stones, ruby-tone accents and cascading pearls, with earrings and maang tikka. "
            "Made to order in limited quantities; not eligible for return for hygiene reasons."),
    jw("JW-BRD-002", "Heritage Rani Haar Bridal Set", "bridal-jewellery", "layered", 7999, 4799, colors=("Gold",), gem="ruby", bg="sand",
       stone="Kundan", style="Statement", occasion="Wedding", collections=("wedding-season", "heritage-gold"), weight=200, stock=10, processing=2,
       desc="A long rani haar with choker and jhumkas — three pieces, one heirloom look."),
    # ---------------- kurtis
    ap("AP-KRT-001", "Emerald Block-Print Cotton Kurti", "kurtis", "kurti", 1499, 749, colors=("Emerald Green", "Maroon", "Navy"), fabric="Cotton",
       fit="Straight", flags="featured,bestseller", collections=("everyday-minimal",),
       desc="Hand block-printed cotton kurti with gold-foil yoke embroidery and a straight, breathable fit.", tags=("kurti", "cotton", "block print")),
    ap("AP-KRT-002", "Chanderi Embroidered Kurta", "kurtis", "kurta-full", 2499, 1499, colors=("Ivory", "Blush Pink"), fabric="Chanderi", fit="A-line",
       sleeve="Full", occasion="Festive", flags="new", collections=("festive-edit",), bg="champagne",
       desc="Luminous chanderi with zari-thread yoke and scalloped hem. Comes with a cotton lining."),
    ap("AP-KRT-003", "Mustard Rayon Short Kurti", "kurtis", "kurti-short", 999, 549, colors=("Mustard", "Teal"), fabric="Rayon", fit="Straight",
       sleeve="Short", style="Casual", desc="An easy short kurti with foil-print booti — pair with jeans or palazzos."),
    ap("AP-KRT-004", "Maroon Festive Silk Kurta", "kurtis", "kurti", 2999, 1799, colors=("Maroon", "Wine"), fabric="Silk Blend", fit="Straight",
       occasion="Festive", flags="bestseller", collections=("festive-edit",), bg="blush",
       desc="Rich silk-blend kurta with gota patti neckline and an ornate hem border."),
    # ---------------- sarees
    ap("AP-SAR-001", "Banarasi Silk Blend Saree", "sarees", "saree", 4999, 2999, colors=("Magenta", "Red", "Emerald Green"), fabric="Silk Blend",
       fit="Regular", sleeve="Sleeveless", occasion="Wedding", sizes=["Free Size"], flags="featured,bestseller", collections=("festive-edit", "wedding-season"),
       bg="sand", stock=10, chart=None, desc="Woven in Varanasi-inspired zari florals with a rich pallu. 5.5 m saree + 0.8 m unstitched blouse piece."),
    ap("AP-SAR-002", "Georgette Sequin Party Saree", "sarees", "saree", 3999, 2199, colors=("Black", "Wine"), fabric="Georgette", fit="Regular",
       sleeve="Sleeveless", style="Contemporary", occasion="Party", sizes=["Free Size"], flags="new", bg="powder", stock=12, chart=None,
       desc="Feather-light georgette with a shimmering sequin border."),
    ap("AP-SAR-003", "Pastel Chiffon Saree", "sarees", "saree", 2999, 1599, colors=("Peach", "Lavender", "Sage"), fabric="Chiffon", fit="Regular",
       sleeve="Sleeveless", style="Minimal", occasion="Festive", sizes=["Free Size"], collections=("everyday-minimal",), bg="blush", stock=12, chart=None,
       desc="Floaty chiffon in soft pastels with a delicate gold lace edge."),
    # ---------------- ethnic dresses
    ap("AP-DRS-001", "Royal Blue Anarkali Dress", "ethnic-dresses", "anarkali", 3499, 1999, colors=("Royal Blue", "Maroon"), fabric="Georgette",
       fit="Flared", sleeve="Full", occasion="Festive", flags="featured", collections=("festive-edit",), bg="champagne",
       desc="A floor-sweeping anarkali with a zari-embroidered yoke and a 6-metre flare."),
    ap("AP-DRS-002", "Floral Printed Ethnic Maxi", "ethnic-dresses", "anarkali", 2199, 1199, colors=("Peach", "Teal"), fabric="Rayon", fit="Flared",
       sleeve="Three-quarter", style="Fusion", occasion="Daily Wear", flags="new", bg="blush", desc="Tiered printed maxi with gold piping at the waist."),
    # ---------------- western
    ap("AP-TOP-001", "Ivory Satin Wrap Top", "tops", "top", 1299, 699, colors=("Ivory", "Black", "Blush Pink"), fabric="Viscose", fit="Regular",
       sleeve="Full", style="Formal", occasion="Office", flags="bestseller", collections=("everyday-minimal",), bg="powder",
       desc="A fluid satin-finish wrap top with tie waist — boardroom to dinner."),
    ap("AP-TOP-002", "Blush Peplum Top", "tops", "peplum", 1199, 649, colors=("Blush Pink", "Lavender"), fabric="Crepe", fit="Slim", sleeve="Puff",
       style="Contemporary", occasion="Party", flags="new", bg="blush", desc="Puff-sleeve peplum top with a sweetheart neckline."),
    ap("AP-TOP-003", "Classic White Linen Shirt", "tops", "top", 1499, 899, colors=("White", "Beige"), fabric="Linen Blend", fit="Relaxed", sleeve="Full",
       style="Casual", occasion="Office", collections=("everyday-minimal",), bg="ivory", desc="Breathable linen-blend shirt with a relaxed drop shoulder."),
    ap("AP-TRS-001", "Navy High-Rise Tailored Trousers", "trousers", "trousers", 1799, 999, colors=("Navy", "Black", "Beige"), fabric="Crepe", fit="Slim",
       sleeve="Sleeveless", style="Formal", occasion="Office", flags="bestseller", bg="powder", chart="bottom",
       desc="High-rise, ankle-length trousers with pressed creases and side pockets."),
    ap("AP-TRS-002", "Flowy Wide-Leg Palazzos", "trousers", "palazzo", 1199, 599, colors=("Olive", "Black", "Mustard"), fabric="Rayon", fit="Wide-leg",
       sleeve="Sleeveless", style="Casual", occasion="Daily Wear", bg="sand", chart="bottom", desc="Elasticated wide-leg palazzos that pair with every kurti."),
    ap("AP-CRD-001", "Mustard Printed Co-ord Set", "coord-sets", "coord", 2499, 1399, colors=("Mustard", "Sage"), fabric="Cotton", fit="Relaxed",
       sleeve="Short", style="Casual", occasion="Daily Wear", flags="featured,new", bg="blush",
       desc="Relaxed shirt and straight pants in a gold-foil geometric print."),
    # ---------------- festive apparel
    ap("AP-LHG-001", "Crimson Bridal Lehenga Set", "festive-apparel", "lehenga", 14999, 8999, colors=("Red", "Wine"), fabric="Silk Blend", fit="Flared",
       sleeve="Short", style="Statement", occasion="Wedding", sizes=["S", "M", "L", "XL"], flags="featured", collections=("wedding-season",),
       bg="champagne", stock=5, processing=3, desc="Hand-embellished zardozi lehenga with blouse and net dupatta. Semi-stitched skirt (waist up to 42\")."),
    ap("AP-LHG-002", "Emerald Festive Lehenga", "festive-apparel", "lehenga", 7999, 4499, colors=("Emerald Green", "Magenta"), fabric="Organza",
       fit="Flared", sleeve="Sleeveless", style="Statement", occasion="Festive", sizes=["S", "M", "L", "XL"], flags="new", collections=("festive-edit",),
       bg="sage", stock=7, processing=2, desc="Organza lehenga with sequin borders and a contrast dupatta."),
    ap("AP-FST-001", "Wine Velvet Festive Kurta Set", "festive-apparel", "kurta-full", 4499, 2699, colors=("Wine", "Navy"), fabric="Silk Blend",
       fit="Straight", sleeve="Full", occasion="Festive", flags="bestseller", collections=("festive-edit",), bg="blush",
       desc="Velvet-touch kurta with palazzo and organza dupatta — three-piece festive set."),
]

PLATING_FOR = {"Gold": "Gold-plated", "Rose Gold": "Rose gold-plated", "Silver": "Rhodium-plated", "Oxidised": "Oxidised", "Antique Gold": "Antique gold-plated"}


def _slug(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _build() -> list[dict]:
    out = []
    for r in RAW:
        looks = []
        for c in r["colors"]:
            if r["kind"] == "jewellery":
                looks.append({"color": c, "metal": METAL_OF.get(c, "gold"), "gem": r["gem"], "bg": r["bg"]})
            else:
                looks.append({"color": c, "metal": "gold", "gem": "ruby", "bg": r["bg"], "fabric": SWATCH[c]})
        r = dict(r, slug=_slug(r["name"]), looks=looks)
        out.append(r)
    return out


PRODUCTS = _build()

PAGES = {
   "about": ("About LoveVital", """LoveVital brings you beautiful jewellery and lifestyle products for every occasion. Discover stylish designs, festive essentials, and everyday favorites at affordable prices, all in one place. Shop with love, style, and confidence!"""),
    "contact": ("Contact Us", """## We'd love to hear from you

**Customer care:** janviawadhesh@gmail.com
**Phone / WhatsApp:** +91-8744092015 (Mon–Sat, 10am–7pm IST)

**Registered office:** B1601, Samridhi Grand Avenue, Greater Noida (W), Uttar Pradesh 201305

For order-related queries please keep your order number handy — you can also track your order from **My Account → Orders**."""),
    "faq": ("Frequently Asked Questions", """### Is the jewellery real gold?
No. LoveVital makes premium **artificial (imitation) jewellery** in brass, copper and alloy with gold, rose-gold, rhodium or oxidised plating.

### Will the plating fade?
With proper care (keep away from water and perfume), our anti-tarnish coating keeps pieces looking new for a long time. Every piece comes with a 6-month plating warranty.

### Do you offer Cash on Delivery?
Yes, on orders up to ₹15,000 for serviceable PIN codes. A ₹49 COD fee applies.

### How long does delivery take?
Most orders are dispatched within 1–2 business days and delivered in 3–6 business days. Check the exact estimate for your PIN code on any product page.

### Can I return a product?
Yes — most items can be returned within 7 days of delivery. See our [Returns & Refunds policy](/pages/return-policy)."""),
    "shipping-policy": ("Shipping Policy", """## Shipping

- **Standard delivery:** ₹79, 3–6 business days. **Free on orders above ₹999.**
- **Express delivery:** ₹149, 1–3 business days in metros.
- Orders are dispatched within 1–2 business days (bridal and made-to-order items may take up to 3 days).
- Remote PIN codes (e.g. North-East, J&K, Ladakh, islands) may take 2–5 extra days; COD may be unavailable.
- You'll receive tracking details by email once your order ships."""),
    "return-policy": ("Returns & Refunds", """## Returns & refunds

- Return or replace most items **within 7 days of delivery** from **My Account → Orders**.
- Items must be unused, with original tags and packaging.
- **Not returnable:** bridal sets, maang tikkas and items marked "non-returnable" (for hygiene reasons).
- Once we receive and inspect the item, refunds are issued to the **original payment method** within 5–7 business days. COD orders are refunded by bank transfer/UPI.
- Damaged or wrong item? Contact us within 48 hours with photos and we'll replace it at no cost."""),
    "privacy-policy": ("Privacy Policy", """## Privacy

We collect only the information needed to process your orders and improve your experience: name, contact details, addresses and order history.

- **Payments** are processed by Razorpay. We never see or store your card number, CVV or UPI PIN.
- We never sell your personal data.
- You can request a copy or deletion of your data by emailing janviawadhesh@gmail.com.

*Demo policy — consult a legal professional for production use.*"""),
    "terms": ("Terms of Service", """## Terms

By using this site you agree to our policies on orders, payments, shipping and returns. Prices are in Indian Rupees and inclusive of GST. Product colours may vary slightly due to photography and screen settings.

*Demo terms for evaluation only.*"""),
}
