"""
Seed script for Solvigo Sales Dashboard demo data.

Safe to rerun: clears demo tables in FK-safe order before reinserting.
Run from the backend/ directory:

    python -m scripts.seed_demo_data
"""

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Make sure backend/ is on sys.path when run as __main__
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
RNG = random.Random(42)

TODAY = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
HISTORY_DAYS = 180

# ---------------------------------------------------------------------------
# Static fixture definitions
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SYNTHETIC DEMO DATA ONLY.
# Company, brand and product names are used for illustration in a synthetic
# demo. Sales figures, market shares and customer data are NOT real and do
# not represent any actual commercial relationship.
# ---------------------------------------------------------------------------

SUPPLIERS = [
    {"name": "Arla Sverige"},
    {"name": "Skånemejerier"},
    {"name": "Coca-Cola Europacific Partners Sverige"},
    {"name": "Orkla Sverige"},
]

CATEGORIES = [
    {"name": "Mejeri"},
    {"name": "Dryck"},
    {"name": "Mat och snacks"},
]

REGIONS = [
    {"name": "Stockholm"},
    {"name": "Göteborg"},
    {"name": "Malmö"},
    {"name": "Uppsala"},
    {"name": "Online"},
]

# brand_name → supplier_name
BRANDS = [
    {"name": "Arla",                  "supplier": "Arla Sverige"},
    {"name": "KESO",                  "supplier": "Arla Sverige"},
    {"name": "Skånemejerier",         "supplier": "Skånemejerier"},
    {"name": "Coca-Cola",             "supplier": "Coca-Cola Europacific Partners Sverige"},
    {"name": "Fanta",                 "supplier": "Coca-Cola Europacific Partners Sverige"},
    {"name": "Sprite",                "supplier": "Coca-Cola Europacific Partners Sverige"},
    {"name": "Felix",                 "supplier": "Orkla Sverige"},
    {"name": "Kalles",                "supplier": "Orkla Sverige"},
    {"name": "OLW",                   "supplier": "Orkla Sverige"},
]

# Each product: brand, category, name, sku, price (SEK), base_weight
# base_weight controls how often this product appears in orders relative
# to other products in the same pool.
PRODUCTS = [
    # Arla brand — Mejeri category
    {"brand": "Arla", "category": "Mejeri", "name": "Arla Mellanmjölk 1,5 l",        "sku": "ARLA-001", "price": "19.90", "weight": 9},
    {"brand": "Arla", "category": "Mejeri", "name": "Arla Standardmjölk 1,5 l",      "sku": "ARLA-002", "price": "20.90", "weight": 6},
    {"brand": "Arla", "category": "Mejeri", "name": "Arla Grekisk Yoghurt Naturell", "sku": "ARLA-003", "price": "27.90", "weight": 5},
    {"brand": "Arla", "category": "Dryck",  "name": "Arla Iced Coffee Latte",        "sku": "ARLA-004", "price": "24.90", "weight": 7},

    # KESO brand — Mejeri category
    {"brand": "KESO", "category": "Mejeri", "name": "KESO Cottage Cheese",           "sku": "ARLA-005", "price": "22.90", "weight": 8},
    {"brand": "KESO", "category": "Mejeri", "name": "KESO Proteinpudding Choklad",   "sku": "ARLA-006", "price": "18.90", "weight": 4},

    # Skånemejerier — Mejeri competitor (aggregate only in Arla's view)
    {"brand": "Skånemejerier", "category": "Mejeri", "name": "Skånemejerier Lättmjölk 1,5 l",     "sku": "SKAN-001", "price": "18.90", "weight": 6},
    {"brand": "Skånemejerier", "category": "Mejeri", "name": "Skånemejerier Kvarg Vanilj",        "sku": "SKAN-002", "price": "24.90", "weight": 5},
    {"brand": "Skånemejerier", "category": "Mejeri", "name": "Skånemejerier Yoghurt Naturell",    "sku": "SKAN-003", "price": "21.90", "weight": 5},
    {"brand": "Skånemejerier", "category": "Mejeri", "name": "Skånemejerier Drickyoghurt Jordgubb","sku": "SKAN-004", "price": "16.90", "weight": 4},

    # Coca-Cola, Fanta, Sprite — Dryck category
    {"brand": "Coca-Cola", "category": "Dryck", "name": "Coca-Cola Zero Sugar 1,5 l", "sku": "COCA-001", "price": "26.90", "weight": 9},
    {"brand": "Coca-Cola", "category": "Dryck", "name": "Coca-Cola Original 1,5 l",   "sku": "COCA-002", "price": "26.90", "weight": 8},
    {"brand": "Fanta",     "category": "Dryck", "name": "Fanta Orange 1,5 l",         "sku": "COCA-003", "price": "24.90", "weight": 6},
    {"brand": "Sprite",    "category": "Dryck", "name": "Sprite Zero 1,5 l",          "sku": "COCA-004", "price": "24.90", "weight": 5},
    {"brand": "Coca-Cola", "category": "Dryck", "name": "Coca-Cola Zero Sugar 33 cl", "sku": "COCA-005", "price": "12.90", "weight": 7},

    # Felix, Kalles, OLW — Mat och snacks category
    {"brand": "Felix",  "category": "Mat och snacks", "name": "Felix Ketchup 1 kg",        "sku": "OLW-001", "price": "32.90", "weight": 7},
    {"brand": "Kalles", "category": "Mat och snacks", "name": "Kalles Kaviar Original",    "sku": "OLW-002", "price": "29.90", "weight": 6},
    {"brand": "OLW",    "category": "Mat och snacks", "name": "OLW Grillchips",            "sku": "OLW-003", "price": "26.90", "weight": 8},
    {"brand": "OLW",    "category": "Mat och snacks", "name": "OLW Cheez Doodles",         "sku": "OLW-004", "price": "24.90", "weight": 7},
    {"brand": "OLW",    "category": "Mat och snacks", "name": "OLW Sourcream & Onion",     "sku": "OLW-005", "price": "26.90", "weight": 6},
    {"brand": "Felix",  "category": "Mat och snacks", "name": "Felix Potatismos Pulver",   "sku": "OLW-006", "price": "21.90", "weight": 4},
]

# ---------------------------------------------------------------------------
# Customer distribution: region → (count, order_multiplier)
# Stockholm is largest; Malmö boosted for Orkla later via product pool
# ---------------------------------------------------------------------------
REGION_CUSTOMERS = {
    "Stockholm": (120, 1.6),
    "Göteborg":  (60,  1.0),
    "Malmö":     (55,  1.0),
    "Uppsala":   (40,  0.8),
    "Online":    (70,  1.2),
}

# ---------------------------------------------------------------------------
# Product pool definitions by supplier context
# Keys: supplier name → list of SKUs with weights
# This controls which products appear in orders for each supplier's "universe"
# (i.e. when an order is attributed to a supplier's customer pool)
# ---------------------------------------------------------------------------

def _build_supplier_pools(products_by_sku):
    """
    Returns dict: supplier_name → [(product_obj, weight), ...]
    For Orkla orders in Malmö we apply a regional weight boost later.
    """
    arla_skus = {
        "ARLA-001": 9, "ARLA-002": 6, "ARLA-003": 5, "ARLA-004": 7,
        "ARLA-005": 8, "ARLA-006": 4,
        # Skånemejerier appears at low weight in Arla pool so it shows up
        # purely as aggregate competitor revenue in the Mejeri market-share view.
        "SKAN-001": 2, "SKAN-002": 2, "SKAN-003": 1, "SKAN-004": 1,
    }
    skanemejerier_skus = {
        # Skånemejerier kept lower so Arla leads the Mejeri category.
        "SKAN-001": 4, "SKAN-002": 3, "SKAN-003": 3, "SKAN-004": 2,
        # Arla products dominate even Skånemejerier customers' baskets.
        "ARLA-001": 7, "ARLA-005": 5, "ARLA-003": 4,
    }
    cocacola_skus = {
        "COCA-001": 9, "COCA-002": 8, "COCA-003": 6, "COCA-004": 5, "COCA-005": 7,
    }
    orkla_skus = {
        "OLW-001": 7, "OLW-002": 6, "OLW-003": 8, "OLW-004": 7,
        "OLW-005": 6, "OLW-006": 4,
    }

    def build(sku_map):
        return [(products_by_sku[sku], w) for sku, w in sku_map.items() if sku in products_by_sku]

    return {
        "Arla Sverige":                              build(arla_skus),
        "Skånemejerier":                             build(skanemejerier_skus),
        "Coca-Cola Europacific Partners Sverige":    build(cocacola_skus),
        "Orkla Sverige":                             build(orkla_skus),
    }


# ---------------------------------------------------------------------------
# Time multipliers
# ---------------------------------------------------------------------------

def arla_trend_multiplier(order_date: datetime) -> float:
    """Gentle upward trend for Arla over last 90 days."""
    days_ago = (TODAY - order_date).days
    if days_ago <= 90:
        # linearly ramp from 1.0 (90 days ago) to 1.6 (today)
        return 1.0 + 0.6 * (1 - days_ago / 90)
    return 1.0


def iced_coffee_decay_multiplier(sku: str, order_date: datetime) -> float:
    """Arla Iced Coffee Latte declines materially in last 30 days."""
    if sku != "ARLA-004":
        return 1.0
    days_ago = (TODAY - order_date).days
    if days_ago <= 30:
        return 0.25
    return 1.0


# ---------------------------------------------------------------------------
# Weighted random choice helper
# ---------------------------------------------------------------------------

def weighted_choice(rng: random.Random, pool: list[tuple]) -> object:
    items, weights = zip(*pool)
    return rng.choices(items, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

def seed(db):
    print("Clearing demo tables...")
    # FK-safe deletion order
    # Saved insights reference supplier_id — clear them so stale product
    # names from a previous dataset never linger in the Insikter drawer.
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
    print("  ✓ Tables cleared")

    # ------------------------------------------------------------------
    # Insert reference data
    # ------------------------------------------------------------------
    print("Inserting suppliers...")
    supplier_map = {}
    for s in SUPPLIERS:
        obj = Supplier(id=uuid.uuid4(), name=s["name"])
        db.add(obj)
        supplier_map[s["name"]] = obj
    db.flush()

    print("Inserting categories...")
    category_map = {}
    for c in CATEGORIES:
        obj = Category(id=uuid.uuid4(), name=c["name"])
        db.add(obj)
        category_map[c["name"]] = obj
    db.flush()

    print("Inserting regions...")
    region_map = {}
    for r in REGIONS:
        obj = Region(id=uuid.uuid4(), name=r["name"])
        db.add(obj)
        region_map[r["name"]] = obj
    db.flush()

    print("Inserting brands...")
    brand_map = {}
    for b in BRANDS:
        obj = Brand(id=uuid.uuid4(), name=b["name"], supplier_id=supplier_map[b["supplier"]].id)
        db.add(obj)
        brand_map[b["name"]] = obj
    db.flush()

    print("Inserting products...")
    product_map = {}  # sku → Product
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
        product_map[p["sku"]] = obj
    db.flush()

    # ------------------------------------------------------------------
    # Build supplier product pools
    # ------------------------------------------------------------------
    supplier_pools = _build_supplier_pools(product_map)

    # ------------------------------------------------------------------
    # Create customers distributed across regions
    # ------------------------------------------------------------------
    print("Inserting customers...")
    # customers_by_supplier: supplier_name → [(customer, region_name, order_mult)]
    customers_by_supplier = {s: [] for s in supplier_map}

    # We assign customers to suppliers in a round-robin + weighted fashion
    # to ensure every supplier has customers in every region.
    supplier_names = list(supplier_map.keys())

    first_names = [
        "Anna", "Erik", "Maria", "Lars", "Sofia", "Johan", "Emma", "Peter",
        "Lena", "Anders", "Karin", "Mikael", "Sara", "Thomas", "Eva", "Henrik",
        "Ingrid", "Mattias", "Åsa", "Jonas", "Malin", "Fredrik", "Elin", "Patrik",
        "Hanna", "Marcus", "Johanna", "Daniel", "Cecilia", "Andreas", "Mia", "Robert",
    ]
    last_names = [
        "Andersson", "Johansson", "Karlsson", "Nilsson", "Eriksson", "Larsson",
        "Olsson", "Persson", "Svensson", "Gustafsson", "Pettersson", "Jonsson",
        "Jansson", "Hansson", "Bengtsson", "Lindström", "Berg", "Lindgren",
        "Lindqvist", "Magnusson", "Lindberg", "Mattsson", "Henriksson", "Eliasson",
    ]

    cust_counter = 0
    for region_name, (count, order_mult) in REGION_CUSTOMERS.items():
        region_obj = region_map[region_name]
        for _ in range(count):
            fn = RNG.choice(first_names)
            ln = RNG.choice(last_names)
            name = f"{fn} {ln}"
            cust = Customer(id=uuid.uuid4(), region_id=region_obj.id, name=name)
            db.add(cust)
            # Assign to a supplier in round-robin
            supplier_name = supplier_names[cust_counter % len(supplier_names)]
            customers_by_supplier[supplier_name].append((cust, region_name, order_mult))
            cust_counter += 1

    db.flush()
    print(f"  ✓ {cust_counter} customers inserted")

    # ------------------------------------------------------------------
    # Generate orders
    # ------------------------------------------------------------------
    print("Generating orders and order items...")
    total_orders = 0
    total_items = 0

    # Target: ≥1500 orders, ≥3000 items across 180 days
    # We'll generate orders per customer proportionally to their order_mult
    # Each customer gets roughly (HISTORY_DAYS / 30 * base_orders_per_month) orders

    base_orders_per_customer_per_month = 1.4  # average across all suppliers

    for supplier_name, cust_list in customers_by_supplier.items():
        pool = supplier_pools[supplier_name]

        for cust, region_name, order_mult in cust_list:
            # How many orders does this customer generate over the history?
            months = HISTORY_DAYS / 30
            n_orders = max(1, int(RNG.gauss(months * base_orders_per_customer_per_month * order_mult, 1)))

            for _ in range(n_orders):
                days_back = RNG.randint(0, HISTORY_DAYS - 1)
                order_date = TODAY - timedelta(days=days_back)

                order = Order(
                    id=uuid.uuid4(),
                    customer_id=cust.id,
                    order_date=order_date,
                )
                db.add(order)

                # 1–4 line items per order
                n_items = RNG.randint(1, 4)

                # Build an adjusted pool for this specific order
                adjusted_pool = []
                for prod, base_w in pool:
                    w = float(base_w)

                    # Pattern 1 & 4: Arla Stockholm uplift + trend
                    if supplier_name == "Arla Sverige" and region_name == "Stockholm":
                        w *= 1.5
                    if supplier_name == "Arla Sverige":
                        w *= arla_trend_multiplier(order_date)

                    # Pattern 3: Arla Iced Coffee Latte decay in last 30 days
                    w *= iced_coffee_decay_multiplier(prod.sku, order_date)

                    # Pattern 5: Orkla stronger in Malmö
                    if supplier_name == "Orkla Sverige" and region_name == "Malmö":
                        if prod.sku.startswith("OLW-"):
                            w *= 2.0

                    # Pattern 6: Coca-Cola stable (no extra modifiers)

                    adjusted_pool.append((prod, max(w, 0.01)))

                chosen_skus = set()
                for _ in range(n_items):
                    prod = weighted_choice(RNG, adjusted_pool)
                    if prod.sku in chosen_skus:
                        continue  # no duplicate products per order
                    chosen_skus.add(prod.sku)

                    qty = RNG.randint(1, 3)
                    price = prod.unit_price
                    revenue = price * qty

                    item = OrderItem(
                        id=uuid.uuid4(),
                        order_id=order.id,
                        product_id=prod.id,
                        quantity=qty,
                        unit_price=price,
                        revenue=revenue,
                    )
                    db.add(item)
                    total_items += 1

                total_orders += 1

    db.commit()
    print(f"  ✓ {total_orders} orders, {total_items} order items inserted")

    # ------------------------------------------------------------------
    # Demo users — one per supplier, all with password "demo1234"
    # ------------------------------------------------------------------
    print("Inserting demo users...")
    DEMO_PASSWORD_HASH = hash_password("demo1234")
    demo_users = [
        {"email": "arla@demo.solvigo",          "supplier": "Arla Sverige"},
        {"email": "skanemejerier@demo.solvigo", "supplier": "Skånemejerier"},
        {"email": "cocacola@demo.solvigo",      "supplier": "Coca-Cola Europacific Partners Sverige"},
        {"email": "orkla@demo.solvigo",         "supplier": "Orkla Sverige"},
    ]
    for u in demo_users:
        obj = User(
            id=uuid.uuid4(),
            email=u["email"],
            password_hash=DEMO_PASSWORD_HASH,
            supplier_id=supplier_map[u["supplier"]].id,
        )
        db.add(obj)
    db.commit()
    print(f"  ✓ {len(demo_users)} demo users created (password: demo1234)")
    print("Seed complete.")


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
