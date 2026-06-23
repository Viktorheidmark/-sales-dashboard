"""
Seed script for Solvigo Sales Intelligence demo data.

SYNTHETIC DEMO DATA ONLY. Company, brand and product names are used for
illustration in a synthetic demo. Sales figures, market shares and customer
data are NOT real and do not represent any actual commercial relationship.

Safe to rerun: clears all demo tables in FK-safe order before reinserting.

Reseed command (from backend/ directory):
    python -m scripts.seed_demo_data

=============================================================================
Embedded analytical patterns — discoverable via chat questions
=============================================================================

Coca-Cola Europacific Partners Sverige (Läsk):
  • Coca-Cola Zero Sugar 33 cl  — top product overall (base_weight=10)
  • Coca-Cola Original 33 cl    — stable, slower-growing (base_weight=8)
  • Fanta Orange 33 cl          — summer boost ×2.0 in Jun–Aug; extra ×1.3 in Stockholm/Malmö
  • Sprite Zero Sugar 33 cl     — deliberate +60 % ramp over the final 90 days
  • Coca-Cola Zero Sugar Lemon  — deliberate decline last 30 days (×0.15 weight)
  • Market share within Läsk    — ≈55 % (vs PepsiCo ≈45 %)

PepsiCo Northern Europe (Läsk):
  • Pepsi Max 33 cl             — top product (base_weight=10)
  • Pepsi Max Lime 33 cl        — +50 % ramp over final 90 days
  • 7UP Free 33 cl              — summer boost ×1.6 in Jun–Aug
  • Mountain Dew 33 cl          — concentrated Stockholm/Göteborg (×0.3 elsewhere)
  • Mountain Dew Zero Sugar     — declining last 30 days (×0.2 weight)

Orkla Snacks Sverige / OLW (Chips & snacks):
  • OLW Grillchips 275 g       — top seller (base_weight=10)
  • OLW Cheez Doodles 160 g    — #2 (base_weight=9)
  • OLW Sourcream & Onion 275 g — ×2.5 in Göteborg and Västerås
  • OLW Dill & Gräslök 275 g   — summer spike ×2.0 in Jun–Aug
  • OLW Jordnötsringar 175 g   — declining last 30 days (×0.2 weight)
  • Market share within Chips & snacks ≈52 % (vs Estrella ≈48 %)

Estrella AB (Chips & snacks):
  • Estrella Grillchips 275 g   — top product (base_weight=10)
  • Estrella Sourcream & Onion  — close competitor to OLW equivalent (base_weight=8)
  • Estrella Linschips 90 g     — gradual +50 % growth over final 6 months
  • Estrella Cheddar 180 g      — short-term dip last 30 days (×0.25 weight)
=============================================================================
"""

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import insert as sa_insert

from app.database import SessionLocal
from app.models import (
    Brand,
    Category,
    Customer,
    Order,
    OrderItem,
    Product,
    Region,
    SavedInsight,
    Supplier,
    User,
)
from app.services.auth import hash_password

# ---------------------------------------------------------------------------
# Deterministic randomness
# ---------------------------------------------------------------------------
RNG = random.Random(2024)

TODAY = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
HISTORY_DAYS = 730  # 24 months

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

SUPPLIERS = [
    {"name": "Coca-Cola Europacific Partners Sverige"},
    {"name": "PepsiCo Northern Europe"},
    {"name": "Orkla Snacks Sverige"},
    {"name": "Estrella AB"},
]

CATEGORIES = [
    {"name": "Läsk"},
    {"name": "Chips & snacks"},
]

REGIONS = [
    {"name": "Stockholm"},
    {"name": "Göteborg"},
    {"name": "Malmö"},
    {"name": "Uppsala"},
    {"name": "Västerås"},
    {"name": "Örebro"},
    {"name": "Linköping"},
    {"name": "Helsingborg"},
]

BRANDS = [
    {"name": "Coca-Cola",    "supplier": "Coca-Cola Europacific Partners Sverige"},
    {"name": "Fanta",        "supplier": "Coca-Cola Europacific Partners Sverige"},
    {"name": "Sprite",       "supplier": "Coca-Cola Europacific Partners Sverige"},
    {"name": "Pepsi",        "supplier": "PepsiCo Northern Europe"},
    {"name": "7UP",          "supplier": "PepsiCo Northern Europe"},
    {"name": "Mountain Dew", "supplier": "PepsiCo Northern Europe"},
    {"name": "OLW",          "supplier": "Orkla Snacks Sverige"},
    {"name": "Estrella",     "supplier": "Estrella AB"},
]

# Fields: brand, category, name, sku, price (SEK/unit), base_weight, qty_min, qty_max
# qty represents units per order line (e.g. cans in a case, bags in a carton)
PRODUCTS = [
    # ── Coca-Cola Europacific Partners Sverige ── category: Läsk ──────────
    # Stable performer; base_weight=8
    {"brand": "Coca-Cola", "category": "Läsk",
     "name": "Coca-Cola Original 33 cl",         "sku": "CC-001",
     "price": "13.90", "base_weight": 8,  "qty_min": 12, "qty_max": 48},
    # PATTERN: top product overall
    {"brand": "Coca-Cola", "category": "Läsk",
     "name": "Coca-Cola Zero Sugar 33 cl",        "sku": "CC-002",
     "price": "13.90", "base_weight": 10, "qty_min": 12, "qty_max": 48},
    # PATTERN: deliberate decline last 30 days (weight ×0.15)
    {"brand": "Coca-Cola", "category": "Läsk",
     "name": "Coca-Cola Zero Sugar Lemon 33 cl",  "sku": "CC-003",
     "price": "13.90", "base_weight": 6,  "qty_min": 12, "qty_max": 36},
    # PATTERN: summer boost ×2.0 (×1.3 extra in Stockholm/Malmö)
    {"brand": "Fanta",     "category": "Läsk",
     "name": "Fanta Orange 33 cl",                "sku": "CC-004",
     "price": "12.90", "base_weight": 6,  "qty_min": 12, "qty_max": 36},
    {"brand": "Fanta",     "category": "Läsk",
     "name": "Fanta Zero Orange 33 cl",           "sku": "CC-005",
     "price": "12.90", "base_weight": 4,  "qty_min": 12, "qty_max": 36},
    {"brand": "Sprite",    "category": "Läsk",
     "name": "Sprite 33 cl",                      "sku": "CC-006",
     "price": "11.90", "base_weight": 5,  "qty_min": 12, "qty_max": 36},
    # PATTERN: positive growth trend over final 90 days (+60 % ramp)
    {"brand": "Sprite",    "category": "Läsk",
     "name": "Sprite Zero Sugar 33 cl",           "sku": "CC-007",
     "price": "11.90", "base_weight": 4,  "qty_min": 12, "qty_max": 36},

    # ── PepsiCo Northern Europe ── category: Läsk ─────────────────────────
    {"brand": "Pepsi",        "category": "Läsk",
     "name": "Pepsi 33 cl",                       "sku": "PEP-001",
     "price": "12.90", "base_weight": 7,  "qty_min": 12, "qty_max": 48},
    # PATTERN: top PepsiCo product
    {"brand": "Pepsi",        "category": "Läsk",
     "name": "Pepsi Max 33 cl",                   "sku": "PEP-002",
     "price": "12.90", "base_weight": 10, "qty_min": 12, "qty_max": 48},
    # PATTERN: +50 % ramp over final 90 days
    {"brand": "Pepsi",        "category": "Läsk",
     "name": "Pepsi Max Lime 33 cl",              "sku": "PEP-003",
     "price": "12.90", "base_weight": 5,  "qty_min": 12, "qty_max": 36},
    # PATTERN: summer boost ×1.6 in Jun–Aug
    {"brand": "7UP",          "category": "Läsk",
     "name": "7UP Free 33 cl",                    "sku": "PEP-004",
     "price": "11.90", "base_weight": 5,  "qty_min": 12, "qty_max": 36},
    # PATTERN: concentrated Stockholm/Göteborg (×0.3 elsewhere)
    {"brand": "Mountain Dew", "category": "Läsk",
     "name": "Mountain Dew 33 cl",                "sku": "PEP-005",
     "price": "13.90", "base_weight": 4,  "qty_min": 6,  "qty_max": 24},
    # PATTERN: concentrated urban + declining last 30 days (×0.2)
    {"brand": "Mountain Dew", "category": "Läsk",
     "name": "Mountain Dew Zero Sugar 33 cl",     "sku": "PEP-006",
     "price": "13.90", "base_weight": 3,  "qty_min": 6,  "qty_max": 24},

    # ── Orkla Snacks Sverige ── category: Chips & snacks ─────────────────
    # PATTERN: #1 OLW product
    {"brand": "OLW", "category": "Chips & snacks",
     "name": "OLW Grillchips 275 g",              "sku": "OLW-001",
     "price": "31.90", "base_weight": 10, "qty_min": 4,  "qty_max": 20},
    # PATTERN: strong in Göteborg and Västerås (×2.5)
    {"brand": "OLW", "category": "Chips & snacks",
     "name": "OLW Sourcream & Onion 275 g",       "sku": "OLW-002",
     "price": "31.90", "base_weight": 7,  "qty_min": 4,  "qty_max": 20},
    # PATTERN: #2 OLW product
    {"brand": "OLW", "category": "Chips & snacks",
     "name": "OLW Cheez Doodles 160 g",           "sku": "OLW-003",
     "price": "24.90", "base_weight": 9,  "qty_min": 6,  "qty_max": 24},
    {"brand": "OLW", "category": "Chips & snacks",
     "name": "OLW Cheez Ballz 160 g",             "sku": "OLW-004",
     "price": "24.90", "base_weight": 6,  "qty_min": 6,  "qty_max": 24},
    # PATTERN: declining last 30 days (×0.2)
    {"brand": "OLW", "category": "Chips & snacks",
     "name": "OLW Jordnötsringar 175 g",          "sku": "OLW-005",
     "price": "26.90", "base_weight": 6,  "qty_min": 6,  "qty_max": 24},
    # PATTERN: seasonal summer spike ×2.0 in Jun–Aug
    {"brand": "OLW", "category": "Chips & snacks",
     "name": "OLW Dill & Gräslök 275 g",          "sku": "OLW-006",
     "price": "31.90", "base_weight": 5,  "qty_min": 4,  "qty_max": 20},

    # ── Estrella AB ── category: Chips & snacks ───────────────────────────
    # PATTERN: top Estrella product
    {"brand": "Estrella", "category": "Chips & snacks",
     "name": "Estrella Grillchips 275 g",         "sku": "EST-001",
     "price": "29.90", "base_weight": 10, "qty_min": 4,  "qty_max": 20},
    # PATTERN: close competitor to OLW Sourcream & Onion
    {"brand": "Estrella", "category": "Chips & snacks",
     "name": "Estrella Sourcream & Onion 275 g",  "sku": "EST-002",
     "price": "29.90", "base_weight": 8,  "qty_min": 4,  "qty_max": 20},
    # PATTERN: short-term dip last 30 days (×0.25)
    {"brand": "Estrella", "category": "Chips & snacks",
     "name": "Estrella Cheddar 180 g",            "sku": "EST-003",
     "price": "23.90", "base_weight": 6,  "qty_min": 6,  "qty_max": 24},
    # PATTERN: gradual +50 % growth over final 6 months
    {"brand": "Estrella", "category": "Chips & snacks",
     "name": "Estrella Linschips Sourcream & Onion 90 g", "sku": "EST-004",
     "price": "19.90", "base_weight": 4,  "qty_min": 12, "qty_max": 36},
    {"brand": "Estrella", "category": "Chips & snacks",
     "name": "Estrella Jordnötsringar 175 g",     "sku": "EST-005",
     "price": "25.90", "base_weight": 6,  "qty_min": 6,  "qty_max": 24},
    {"brand": "Estrella", "category": "Chips & snacks",
     "name": "Estrella Ostbågar 160 g",           "sku": "EST-006",
     "price": "22.90", "base_weight": 5,  "qty_min": 6,  "qty_max": 24},
]

# ---------------------------------------------------------------------------
# Customer distribution: region → count of synthetic stores
# ---------------------------------------------------------------------------
REGION_CUSTOMER_COUNTS = {
    "Stockholm":   500,
    "Göteborg":    320,
    "Malmö":       260,
    "Uppsala":     200,
    "Västerås":    160,
    "Örebro":      140,
    "Linköping":   120,
    "Helsingborg": 100,
}
# Total: 1800 customers (within 1500–3000 target)

# Synthetic retailer store chains
STORE_CHAINS = [
    "ICA Maxi", "ICA Kvantum", "ICA Supermarket", "ICA Nära",
    "Coop Forum", "Coop Stormarknad", "Coop Extra", "Coop Konsum",
    "Hemköp", "Willys", "Willys Hemma", "City Gross", "Lidl", "Netto", "Tempo",
]

# Synthetic neighborhood/location names per region
REGION_LOCATIONS: dict[str, list[str]] = {
    "Stockholm": [
        "Östermalm", "Södermalm", "Kungsholmen", "Vasastan", "Bromma",
        "Nacka", "Solna", "Huddinge", "Täby", "Lidingö", "Järfälla",
        "Haninge", "Tyresö", "Botkyrka", "Sundbyberg", "Sollentuna",
        "Upplands Väsby", "Vallentuna", "Södertälje", "Vaxholm",
        "Danderyd", "Ekerö", "Norrtälje", "Nynäshamn", "Sigtuna",
    ],
    "Göteborg": [
        "Haga", "Majorna", "Centrum", "Frölunda", "Mölndal", "Partille",
        "Askim", "Angered", "Örgryte", "Biskopsgården", "Härryda",
        "Öckerö", "Kungsbacka", "Alingsås", "Lerum", "Kungälv",
        "Högsbo", "Bergsjön", "Backa", "Torslanda",
    ],
    "Malmö": [
        "Västra Hamnen", "Husie", "Limhamn", "Hyllie", "Centrum",
        "Rosengård", "Oxie", "Fosie", "Kirseberg", "Vellinge",
        "Staffanstorp", "Trelleborg", "Burlöv", "Svedala",
    ],
    "Uppsala": [
        "Centrum", "Fålhagen", "Gottsunda", "Stenhagen", "Eriksberg",
        "Gränby", "Luthagen", "Sala Backe", "Enköping", "Bälinge",
    ],
    "Västerås": [
        "Centrum", "Bäckby", "Skultuna", "Hälla", "Råby",
        "Tillberga", "Hallstahammar", "Köping", "Irsta",
    ],
    "Örebro": [
        "Centrum", "Varbergahed", "Adolfsberg", "Baronbackarna",
        "Vivalla", "Oxhagen", "Kumla", "Hallsberg", "Glanshammar",
    ],
    "Linköping": [
        "Centrum", "Ryd", "Ekholmen", "Lambohov", "Malmslätt",
        "Vikingstad", "Mjölby", "Motala", "Skäggetorp",
    ],
    "Helsingborg": [
        "Centrum", "Hässleby", "Dalhem", "Planteringen",
        "Miatorp", "Höganäs", "Landskrona", "Ängelholm", "Påarp",
    ],
}

# Orders per customer: base count over HISTORY_DAYS (≈ 24 months)
REGION_ORDER_MULTIPLIER = {
    "Stockholm": 1.4,
    "Göteborg": 1.2,
    "Malmö": 1.1,
    "Uppsala": 1.0,
    "Västerås": 0.95,
    "Örebro": 0.95,
    "Linköping": 0.9,
    "Helsingborg": 0.9,
}
BASE_ORDERS_PER_CUSTOMER = 28  # avg over 24 months ≈ 1.2/month


# ---------------------------------------------------------------------------
# Pattern weight modifiers
# ---------------------------------------------------------------------------

def product_weight(prod: dict, days_ago: int, region_name: str) -> float:
    """
    Return adjusted weight for product selection in a given order context.

    days_ago=0 → today, days_ago=HISTORY_DAYS → start of history.
    Embeds all documented analytical patterns as weight multipliers.
    """
    w = float(prod["base_weight"])
    sku = prod["sku"]
    order_date = TODAY - timedelta(days=days_ago)
    month = order_date.month
    is_summer = month in (6, 7, 8)

    # ── COCA-COLA patterns ─────────────────────────────────────────────────
    # CC Zero Sugar Lemon: deliberate 30-day decline
    if sku == "CC-003" and days_ago <= 30:
        w *= 0.15

    # Sprite Zero Sugar: positive +60 % ramp over final 90 days
    if sku == "CC-007" and days_ago <= 90:
        w *= 1.0 + 0.6 * (1.0 - days_ago / 90.0)

    # Fanta Orange: summer boost; extra in Stockholm/Malmö
    if sku == "CC-004" and is_summer:
        w *= 2.0
        if region_name in ("Stockholm", "Malmö"):
            w *= 1.3

    # Fanta Zero: mild summer lift
    if sku == "CC-005" and is_summer:
        w *= 1.2

    # ── PEPSICO patterns ───────────────────────────────────────────────────
    # Pepsi Max Lime: +50 % ramp over final 90 days
    if sku == "PEP-003" and days_ago <= 90:
        w *= 1.0 + 0.5 * (1.0 - days_ago / 90.0)

    # 7UP Free: summer boost
    if sku == "PEP-004" and is_summer:
        w *= 1.6

    # Mountain Dew (both variants): concentrated in Stockholm/Göteborg
    if sku in ("PEP-005", "PEP-006") and region_name not in ("Stockholm", "Göteborg"):
        w *= 0.3

    # Mountain Dew Zero Sugar: declining last 30 days
    if sku == "PEP-006" and days_ago <= 30:
        w *= 0.2

    # ── OLW patterns ──────────────────────────────────────────────────────
    # Sourcream & Onion: strong in Göteborg and Västerås
    if sku == "OLW-002" and region_name in ("Göteborg", "Västerås"):
        w *= 2.5

    # Dill & Gräslök: seasonal summer spike
    if sku == "OLW-006" and is_summer:
        w *= 2.0

    # Jordnötsringar: declining last 30 days
    if sku == "OLW-005" and days_ago <= 30:
        w *= 0.2

    # ── ESTRELLA patterns ─────────────────────────────────────────────────
    # Linschips: gradual +50 % growth over final 6 months
    if sku == "EST-004" and days_ago <= 180:
        w *= 1.0 + 0.5 * (1.0 - days_ago / 180.0)

    # Cheddar: short-term dip last 30 days
    if sku == "EST-003" and days_ago <= 30:
        w *= 0.25

    return max(w, 0.01)


def weighted_choice_product(rng: random.Random, pool: list[dict], days_ago: int, region_name: str) -> dict:
    weights = [product_weight(p, days_ago, region_name) for p in pool]
    return rng.choices(pool, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Customer name generation
# ---------------------------------------------------------------------------

def generate_store_name(rng: random.Random, region_name: str, index: int) -> str:
    chain = rng.choice(STORE_CHAINS)
    locations = REGION_LOCATIONS[region_name]
    location = locations[index % len(locations)]
    number = (index // len(locations)) + 1
    if number > 1:
        return f"{chain} {location} {number}"
    return f"{chain} {location}"


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

def seed(db):
    print("=" * 62)
    print("  WARNING: This will DELETE all demo data and reseed.")
    print("  SYNTHETIC DATA ONLY — not real commercial sales.")
    print("=" * 62)
    print()

    # ------------------------------------------------------------------
    # 1. Clear all tables in FK-safe order
    # ------------------------------------------------------------------
    print("Clearing demo tables (FK-safe order)...")
    db.query(SavedInsight).delete()
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(Customer).delete()
    db.query(Product).delete()
    db.query(Brand).delete()
    db.query(User).delete()
    db.query(Supplier).delete()
    db.query(Region).delete()
    db.query(Category).delete()
    db.commit()
    print("  ✓ Tables cleared\n")

    # ------------------------------------------------------------------
    # 2. Suppliers
    # ------------------------------------------------------------------
    print("Inserting suppliers...")
    supplier_map: dict[str, Supplier] = {}
    for s in SUPPLIERS:
        obj = Supplier(id=uuid.uuid4(), name=s["name"])
        db.add(obj)
        supplier_map[s["name"]] = obj
    db.flush()
    print(f"  ✓ {len(supplier_map)} suppliers")

    # ------------------------------------------------------------------
    # 3. Categories
    # ------------------------------------------------------------------
    print("Inserting categories...")
    category_map: dict[str, Category] = {}
    for c in CATEGORIES:
        obj = Category(id=uuid.uuid4(), name=c["name"])
        db.add(obj)
        category_map[c["name"]] = obj
    db.flush()
    print(f"  ✓ {len(category_map)} categories")

    # ------------------------------------------------------------------
    # 4. Regions
    # ------------------------------------------------------------------
    print("Inserting regions...")
    region_map: dict[str, Region] = {}
    for r in REGIONS:
        obj = Region(id=uuid.uuid4(), name=r["name"])
        db.add(obj)
        region_map[r["name"]] = obj
    db.flush()
    print(f"  ✓ {len(region_map)} regions")

    # ------------------------------------------------------------------
    # 5. Brands
    # ------------------------------------------------------------------
    print("Inserting brands...")
    brand_map: dict[str, Brand] = {}
    for b in BRANDS:
        obj = Brand(
            id=uuid.uuid4(),
            name=b["name"],
            supplier_id=supplier_map[b["supplier"]].id,
        )
        db.add(obj)
        brand_map[b["name"]] = obj
    db.flush()
    print(f"  ✓ {len(brand_map)} brands")

    # ------------------------------------------------------------------
    # 6. Products
    # ------------------------------------------------------------------
    print("Inserting products...")
    product_objs: dict[str, Product] = {}
    for p in PRODUCTS:
        obj = Product(
            id=uuid.uuid4(),
            brand_id=brand_map[p["brand"]].id,
            category_id=category_map[p["category"]].id,
            name=p["name"],
            sku=p["sku"],
            unit_price=Decimal(p["price"]),
        )
        db.add(obj)
        product_objs[p["sku"]] = obj
    db.flush()
    print(f"  ✓ {len(product_objs)} products")

    # Enrich product list with DB object IDs for bulk insert rows
    all_products = [
        {**p, "obj_id": product_objs[p["sku"]].id}
        for p in PRODUCTS
    ]

    # ------------------------------------------------------------------
    # 7. Customers (synthetic retailer stores)
    # ------------------------------------------------------------------
    print("Inserting customers...")
    customer_rows: list[tuple[uuid.UUID, str]] = []
    for region_name, count in REGION_CUSTOMER_COUNTS.items():
        region_obj = region_map[region_name]
        for idx in range(count):
            store_name = generate_store_name(RNG, region_name, idx)
            cid = uuid.uuid4()
            db.add(Customer(id=cid, region_id=region_obj.id, name=store_name))
            customer_rows.append((cid, region_name))
    db.flush()
    total_customers = len(customer_rows)
    print(f"  ✓ {total_customers} customers across {len(REGION_CUSTOMER_COUNTS)} regions")

    # ------------------------------------------------------------------
    # 8. Orders and order items (bulk inserts for performance)
    # ------------------------------------------------------------------
    print("Generating orders and order items...")
    start_dt = TODAY - timedelta(days=HISTORY_DAYS)
    print(f"  Date range: {start_dt.date()} → {(TODAY - timedelta(days=1)).date()}")

    order_dicts: list[dict] = []
    item_dicts:  list[dict] = []

    for customer_id, region_name in customer_rows:
        mult = REGION_ORDER_MULTIPLIER[region_name]
        n_orders = max(1, int(RNG.gauss(BASE_ORDERS_PER_CUSTOMER * mult, 5)))

        for _ in range(n_orders):
            days_ago = RNG.randint(1, HISTORY_DAYS)
            order_date = TODAY - timedelta(days=days_ago)
            order_id = uuid.uuid4()

            order_dicts.append({
                "id": order_id,
                "customer_id": customer_id,
                "order_date": order_date,
            })

            # 2–5 distinct product lines per order
            n_items = RNG.randint(2, 5)
            chosen_skus: set[str] = set()
            attempts = 0
            while len(chosen_skus) < n_items and attempts < n_items * 4:
                attempts += 1
                prod = weighted_choice_product(RNG, all_products, days_ago, region_name)
                sku = prod["sku"]
                if sku in chosen_skus:
                    continue
                chosen_skus.add(sku)

                qty = RNG.randint(prod["qty_min"], prod["qty_max"])
                unit_price = Decimal(prod["price"])
                revenue = unit_price * qty

                item_dicts.append({
                    "id": uuid.uuid4(),
                    "order_id": order_id,
                    "product_id": prod["obj_id"],
                    "quantity": qty,
                    "unit_price": unit_price,
                    "revenue": revenue,
                })

    # Bulk-insert orders
    BATCH = 5000
    print(f"  Bulk-inserting {len(order_dicts):,} orders...")
    for i in range(0, len(order_dicts), BATCH):
        db.execute(sa_insert(Order), order_dicts[i : i + BATCH])
    db.flush()

    # Bulk-insert order items in batches
    print(f"  Bulk-inserting {len(item_dicts):,} order items (batch={BATCH})...")
    for i in range(0, len(item_dicts), BATCH):
        db.execute(sa_insert(OrderItem), item_dicts[i : i + BATCH])

    db.commit()
    print(f"  ✓ {len(order_dicts):,} orders, {len(item_dicts):,} order items committed")

    # ------------------------------------------------------------------
    # 9. Demo users (one per supplier, password: demo1234)
    # ------------------------------------------------------------------
    print("Inserting demo users...")
    pw_hash = hash_password("demo1234")
    demo_users = [
        {"email": "cocacola@demo.solvigo", "supplier": "Coca-Cola Europacific Partners Sverige"},
        {"email": "pepsico@demo.solvigo",  "supplier": "PepsiCo Northern Europe"},
        {"email": "olw@demo.solvigo",      "supplier": "Orkla Snacks Sverige"},
        {"email": "estrella@demo.solvigo", "supplier": "Estrella AB"},
    ]
    for u in demo_users:
        db.add(User(
            id=uuid.uuid4(),
            email=u["email"],
            password_hash=pw_hash,
            supplier_id=supplier_map[u["supplier"]].id,
        ))
    db.commit()
    print(f"  ✓ {len(demo_users)} demo users (password: demo1234)")

    # ------------------------------------------------------------------
    # 10. Summary
    # ------------------------------------------------------------------
    start_date = start_dt.date()
    end_date   = (TODAY - timedelta(days=1)).date()

    print()
    print("=" * 62)
    print("  SEED COMPLETE")
    print("=" * 62)
    print(f"  Suppliers     : {len(SUPPLIERS)}")
    print(f"  Brands        : {len(BRANDS)}")
    print(f"  Products      : {len(PRODUCTS)}")
    print(f"  Categories    : {len(CATEGORIES)}")
    print(f"  Regions       : {len(REGIONS)}")
    print(f"  Customers     : {total_customers:,}")
    print(f"  Orders        : {len(order_dicts):,}")
    print(f"  Order items   : {len(item_dicts):,}")
    print(f"  Date range    : {start_date} → {end_date}  ({HISTORY_DAYS} days)")
    print()
    print("  Demo logins (password: demo1234):")
    for u in demo_users:
        print(f"    {u['email']:<30}  →  {u['supplier']}")
    print()

    # ------------------------------------------------------------------
    # 11. Verification queries
    # ------------------------------------------------------------------
    _verify_patterns(db)


def _verify_patterns(db):
    """
    Run SQL assertions to confirm all documented patterns are present.
    Prints PASS / FAIL for each check.
    """
    from sqlalchemy import text

    print("Running pattern verification queries...")
    checks_passed = 0
    checks_failed = 0

    def check(label: str, sql: str, expected: bool):
        nonlocal checks_passed, checks_failed
        result = db.execute(text(sql)).scalar()
        ok = bool(result) == expected
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {label}  (got: {result})")
        if ok:
            checks_passed += 1
        else:
            checks_failed += 1

    check(
        "CC Zero Sugar 33 cl is #1 Coca-Cola product (all time)",
        """
        SELECT (SELECT p.sku FROM order_items oi
          JOIN products p ON p.id = oi.product_id
          JOIN brands b ON b.id = p.brand_id
          JOIN suppliers s ON s.id = b.supplier_id
          WHERE s.name = 'Coca-Cola Europacific Partners Sverige'
          GROUP BY p.sku ORDER BY SUM(oi.revenue) DESC LIMIT 1) = 'CC-002'
        """,
        expected=True,
    )

    check(
        "Pepsi Max 33 cl is #1 PepsiCo product (all time)",
        """
        SELECT (SELECT p.sku FROM order_items oi
          JOIN products p ON p.id = oi.product_id
          JOIN brands b ON b.id = p.brand_id
          JOIN suppliers s ON s.id = b.supplier_id
          WHERE s.name = 'PepsiCo Northern Europe'
          GROUP BY p.sku ORDER BY SUM(oi.revenue) DESC LIMIT 1) = 'PEP-002'
        """,
        expected=True,
    )

    check(
        "OLW Grillchips 275 g is #1 OLW product (all time)",
        """
        SELECT (SELECT p.sku FROM order_items oi
          JOIN products p ON p.id = oi.product_id
          JOIN brands b ON b.id = p.brand_id
          JOIN suppliers s ON s.id = b.supplier_id
          WHERE s.name = 'Orkla Snacks Sverige'
          GROUP BY p.sku ORDER BY SUM(oi.revenue) DESC LIMIT 1) = 'OLW-001'
        """,
        expected=True,
    )

    check(
        "Estrella Grillchips 275 g is #1 Estrella product (all time)",
        """
        SELECT (SELECT p.sku FROM order_items oi
          JOIN products p ON p.id = oi.product_id
          JOIN brands b ON b.id = p.brand_id
          JOIN suppliers s ON s.id = b.supplier_id
          WHERE s.name = 'Estrella AB'
          GROUP BY p.sku ORDER BY SUM(oi.revenue) DESC LIMIT 1) = 'EST-001'
        """,
        expected=True,
    )

    check(
        "CC Zero Sugar Lemon revenue in last 30 days < prior 30 days",
        """
        SELECT
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '30 days' THEN oi.revenue ELSE 0 END)
          <
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '60 days'
                    AND o.order_date < NOW() - INTERVAL '30 days' THEN oi.revenue ELSE 0 END)
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id WHERE p.sku = 'CC-003'
        """,
        expected=True,
    )

    check(
        "Sprite Zero Sugar growing (last 90 d > prior 90 d)",
        """
        SELECT
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '90 days' THEN oi.revenue ELSE 0 END)
          >
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '180 days'
                    AND o.order_date < NOW() - INTERVAL '90 days' THEN oi.revenue ELSE 0 END)
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id WHERE p.sku = 'CC-007'
        """,
        expected=True,
    )

    check(
        "Fanta Orange summer revenue > winter revenue",
        """
        SELECT
          SUM(CASE WHEN EXTRACT(MONTH FROM o.order_date) IN (6,7,8) THEN oi.revenue ELSE 0 END)
          >
          SUM(CASE WHEN EXTRACT(MONTH FROM o.order_date) IN (12,1,2) THEN oi.revenue ELSE 0 END)
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id WHERE p.sku = 'CC-004'
        """,
        expected=True,
    )

    check(
        "Mountain Dew revenue higher in Stockholm+Göteborg than rest",
        """
        SELECT
          SUM(CASE WHEN r.name IN ('Stockholm','Göteborg') THEN oi.revenue ELSE 0 END)
          >
          SUM(CASE WHEN r.name NOT IN ('Stockholm','Göteborg') THEN oi.revenue ELSE 0 END)
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN customers c ON c.id = o.customer_id JOIN regions r ON r.id = c.region_id
        JOIN products p ON p.id = oi.product_id WHERE p.sku = 'PEP-005'
        """,
        expected=True,
    )

    check(
        "OLW Sourcream & Onion per-store revenue higher in Göteborg/Västerås",
        """
        SELECT
          (SUM(CASE WHEN r.name IN ('Göteborg','Västerås') THEN oi.revenue ELSE 0 END)
           / NULLIF(COUNT(DISTINCT CASE WHEN r.name IN ('Göteborg','Västerås') THEN c.id END), 0))
          >
          (SUM(CASE WHEN r.name NOT IN ('Göteborg','Västerås') THEN oi.revenue ELSE 0 END)
           / NULLIF(COUNT(DISTINCT CASE WHEN r.name NOT IN ('Göteborg','Västerås') THEN c.id END), 0))
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN customers c ON c.id = o.customer_id JOIN regions r ON r.id = c.region_id
        JOIN products p ON p.id = oi.product_id WHERE p.sku = 'OLW-002'
        """,
        expected=True,
    )

    check(
        "OLW Jordnötsringar revenue in last 30 days < prior 30 days",
        """
        SELECT
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '30 days' THEN oi.revenue ELSE 0 END)
          <
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '60 days'
                    AND o.order_date < NOW() - INTERVAL '30 days' THEN oi.revenue ELSE 0 END)
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id WHERE p.sku = 'OLW-005'
        """,
        expected=True,
    )

    check(
        "Estrella Linschips growing (last 90 d > prior 90 d)",
        """
        SELECT
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '90 days' THEN oi.revenue ELSE 0 END)
          >
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '180 days'
                    AND o.order_date < NOW() - INTERVAL '90 days' THEN oi.revenue ELSE 0 END)
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id WHERE p.sku = 'EST-004'
        """,
        expected=True,
    )

    check(
        "Estrella Cheddar revenue in last 30 days < prior 30 days",
        """
        SELECT
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '30 days' THEN oi.revenue ELSE 0 END)
          <
          SUM(CASE WHEN o.order_date >= NOW() - INTERVAL '60 days'
                    AND o.order_date < NOW() - INTERVAL '30 days' THEN oi.revenue ELSE 0 END)
        FROM order_items oi JOIN orders o ON o.id = oi.order_id
        JOIN products p ON p.id = oi.product_id WHERE p.sku = 'EST-003'
        """,
        expected=True,
    )

    check(
        "Coca-Cola market share in Läsk ≥ 50 %",
        """
        SELECT
          (SUM(CASE WHEN s.name = 'Coca-Cola Europacific Partners Sverige' THEN oi.revenue ELSE 0 END)
           / NULLIF(SUM(oi.revenue), 0)) >= 0.50
        FROM order_items oi JOIN products p ON p.id = oi.product_id
        JOIN categories cat ON cat.id = p.category_id
        JOIN brands b ON b.id = p.brand_id JOIN suppliers s ON s.id = b.supplier_id
        WHERE cat.name = 'Läsk'
        """,
        expected=True,
    )

    check(
        "OLW market share in Chips & snacks between 45 % and 65 %",
        """
        SELECT
          (SUM(CASE WHEN s.name = 'Orkla Snacks Sverige' THEN oi.revenue ELSE 0 END)
           / NULLIF(SUM(oi.revenue), 0)) BETWEEN 0.45 AND 0.65
        FROM order_items oi JOIN products p ON p.id = oi.product_id
        JOIN categories cat ON cat.id = p.category_id
        JOIN brands b ON b.id = p.brand_id JOIN suppliers s ON s.id = b.supplier_id
        WHERE cat.name = 'Chips & snacks'
        """,
        expected=True,
    )

    check(
        "Dataset spans at least 24 months (720 days)",
        """
        SELECT (MAX(order_date) - MIN(order_date)) >= INTERVAL '720 days'
        FROM orders
        """,
        expected=True,
    )

    check(
        "All 4 suppliers have ≥ 5000 order items",
        """
        SELECT MIN(cnt) >= 5000
        FROM (
          SELECT s.name, COUNT(*) AS cnt
          FROM order_items oi JOIN products p ON p.id = oi.product_id
          JOIN brands b ON b.id = p.brand_id JOIN suppliers s ON s.id = b.supplier_id
          GROUP BY s.name
        ) t
        """,
        expected=True,
    )

    print()
    total = checks_passed + checks_failed
    print(f"Verification: {checks_passed}/{total} checks passed" + (" ✓" if checks_failed == 0 else " ✗"))
    if checks_failed:
        print(f"  WARNING: {checks_failed} check(s) failed — review patterns above.")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
