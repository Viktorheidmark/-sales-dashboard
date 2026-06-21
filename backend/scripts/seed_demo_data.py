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
    Supplier,
)

# ---------------------------------------------------------------------------
# Deterministic randomness
# ---------------------------------------------------------------------------
RNG = random.Random(42)

TODAY = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
HISTORY_DAYS = 180

# ---------------------------------------------------------------------------
# Static fixture definitions
# ---------------------------------------------------------------------------

SUPPLIERS = [
    {"name": "Nordic Coffee AB"},
    {"name": "Fresh Snacks Ltd"},
    {"name": "Clean Home Co"},
    {"name": "Baltic Roasters AB"},
]

CATEGORIES = [
    {"name": "Coffee"},
    {"name": "Snacks"},
    {"name": "Household"},
    {"name": "Drinks"},
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
    {"name": "Nordic Coffee",   "supplier": "Nordic Coffee AB"},
    {"name": "Fjord Roast",     "supplier": "Nordic Coffee AB"},
    {"name": "Fresh Snacks",    "supplier": "Fresh Snacks Ltd"},
    {"name": "SnackMax",        "supplier": "Fresh Snacks Ltd"},
    {"name": "Clean Home",      "supplier": "Clean Home Co"},
    {"name": "BrightHome",      "supplier": "Clean Home Co"},
    # Competitor brands in Drinks — assigned to Nordic Coffee AB as placeholder
    {"name": "Sparkling North", "supplier": "Nordic Coffee AB"},
    {"name": "Nordic Sips",     "supplier": "Nordic Coffee AB"},
    # Real Coffee competitor with its own supplier
    {"name": "Baltic Roast",    "supplier": "Baltic Roasters AB"},
]

# Each product: brand, category, name, sku, price (SEK), base_weight
# base_weight controls how often this product appears in orders relative
# to other products in the same pool.
PRODUCTS = [
    # Nordic Coffee brand — Coffee category
    {"brand": "Nordic Coffee", "category": "Coffee", "name": "Espresso Dark Roast 500g",  "sku": "NCO-001", "price": "89.00",  "weight": 9},
    {"brand": "Nordic Coffee", "category": "Coffee", "name": "Organic Medium Roast 250g", "sku": "NCO-002", "price": "72.00",  "weight": 6},
    {"brand": "Nordic Coffee", "category": "Drinks", "name": "Cold Brew Can",              "sku": "NCO-003", "price": "29.00",  "weight": 7},
    {"brand": "Nordic Coffee", "category": "Coffee", "name": "Decaf Blend 250g",           "sku": "NCO-004", "price": "69.00",  "weight": 4},
    {"brand": "Nordic Coffee", "category": "Coffee", "name": "Single Origin Ethiopia 200g","sku": "NCO-005", "price": "99.00",  "weight": 3},
    {"brand": "Nordic Coffee", "category": "Drinks", "name": "Cold Brew Nitro Can",        "sku": "NCO-006", "price": "35.00",  "weight": 3},

    # Fjord Roast — Coffee (competitor-ish brand for Nordic Coffee AB)
    {"brand": "Fjord Roast",   "category": "Coffee", "name": "Fjord Dark Roast 500g",     "sku": "FJR-001", "price": "79.00",  "weight": 5},
    {"brand": "Fjord Roast",   "category": "Coffee", "name": "Fjord Light Roast 250g",    "sku": "FJR-002", "price": "65.00",  "weight": 4},
    {"brand": "Fjord Roast",   "category": "Drinks", "name": "Fjord Cold Brew Can",        "sku": "FJR-003", "price": "27.00",  "weight": 3},
    {"brand": "Fjord Roast",   "category": "Coffee", "name": "Fjord Espresso Pods 16-pack","sku": "FJR-004", "price": "59.00",  "weight": 3},

    # Fresh Snacks brand — Snacks category
    {"brand": "Fresh Snacks",  "category": "Snacks", "name": "Protein Bar Chocolate",     "sku": "FSN-001", "price": "24.00",  "weight": 8},
    {"brand": "Fresh Snacks",  "category": "Snacks", "name": "Protein Bar Peanut",        "sku": "FSN-002", "price": "24.00",  "weight": 7},
    {"brand": "Fresh Snacks",  "category": "Snacks", "name": "Trail Mix Berry",           "sku": "FSN-003", "price": "39.00",  "weight": 6},
    {"brand": "Fresh Snacks",  "category": "Snacks", "name": "Oat Snack Bar",             "sku": "FSN-004", "price": "19.00",  "weight": 5},
    {"brand": "Fresh Snacks",  "category": "Snacks", "name": "Nut Butter Pouch",          "sku": "FSN-005", "price": "32.00",  "weight": 4},

    # SnackMax brand — Snacks category
    {"brand": "SnackMax",      "category": "Snacks", "name": "SnackMax Protein Bar",      "sku": "SMX-001", "price": "22.00",  "weight": 5},
    {"brand": "SnackMax",      "category": "Snacks", "name": "SnackMax Trail Mix",        "sku": "SMX-002", "price": "35.00",  "weight": 4},
    {"brand": "SnackMax",      "category": "Snacks", "name": "SnackMax Rice Cakes",       "sku": "SMX-003", "price": "28.00",  "weight": 4},
    {"brand": "SnackMax",      "category": "Snacks", "name": "SnackMax Protein Chips",    "sku": "SMX-004", "price": "26.00",  "weight": 3},

    # Clean Home brand — Household category
    {"brand": "Clean Home",    "category": "Household", "name": "Eco Cleaning Spray",         "sku": "CLH-001", "price": "49.00",  "weight": 7},
    {"brand": "Clean Home",    "category": "Household", "name": "Kitchen Degreaser",           "sku": "CLH-002", "price": "55.00",  "weight": 6},
    {"brand": "Clean Home",    "category": "Household", "name": "Laundry Liquid 1L",           "sku": "CLH-003", "price": "79.00",  "weight": 5},
    {"brand": "Clean Home",    "category": "Household", "name": "Dishwashing Tablets 30-pack", "sku": "CLH-004", "price": "89.00",  "weight": 5},
    {"brand": "Clean Home",    "category": "Household", "name": "All-Purpose Wipes 60-pack",   "sku": "CLH-005", "price": "39.00",  "weight": 4},

    # BrightHome brand — Household category
    {"brand": "BrightHome",   "category": "Household", "name": "BrightHome Floor Cleaner",    "sku": "BHO-001", "price": "59.00",  "weight": 5},
    {"brand": "BrightHome",   "category": "Household", "name": "BrightHome Glass Cleaner",    "sku": "BHO-002", "price": "45.00",  "weight": 4},
    {"brand": "BrightHome",   "category": "Household", "name": "BrightHome Toilet Tabs",      "sku": "BHO-003", "price": "69.00",  "weight": 4},
    {"brand": "BrightHome",   "category": "Household", "name": "BrightHome Fabric Softener",  "sku": "BHO-004", "price": "75.00",  "weight": 3},

    # Baltic Roast — real Coffee competitor (Baltic Roasters AB)
    {"brand": "Baltic Roast",  "category": "Coffee", "name": "Baltic Dark Roast 500g",      "sku": "BLR-001", "price": "82.00",  "weight": 7},
    {"brand": "Baltic Roast",  "category": "Coffee", "name": "Baltic Medium Roast 250g",    "sku": "BLR-002", "price": "68.00",  "weight": 6},
    {"brand": "Baltic Roast",  "category": "Coffee", "name": "Baltic Espresso Blend 500g",  "sku": "BLR-003", "price": "85.00",  "weight": 5},
    {"brand": "Baltic Roast",  "category": "Coffee", "name": "Baltic Single Origin 200g",   "sku": "BLR-004", "price": "95.00",  "weight": 4},

    # Sparkling North — competitor in Drinks
    {"brand": "Sparkling North","category": "Drinks", "name": "Sparkling Water Lemon 6-pack", "sku": "SPN-001", "price": "39.00",  "weight": 6},
    {"brand": "Sparkling North","category": "Drinks", "name": "Sparkling Water Plain 6-pack", "sku": "SPN-002", "price": "35.00",  "weight": 5},
    {"brand": "Sparkling North","category": "Drinks", "name": "Sparkling Elderflower Can",    "sku": "SPN-003", "price": "19.00",  "weight": 4},

    # Nordic Sips — competitor in Drinks
    {"brand": "Nordic Sips",   "category": "Drinks", "name": "Nordic Sips Green Tea Can",     "sku": "NDS-001", "price": "22.00",  "weight": 4},
    {"brand": "Nordic Sips",   "category": "Drinks", "name": "Nordic Sips Berry Boost",       "sku": "NDS-002", "price": "25.00",  "weight": 4},
    {"brand": "Nordic Sips",   "category": "Drinks", "name": "Nordic Sips Ginger Shot",       "sku": "NDS-003", "price": "18.00",  "weight": 3},
]

# ---------------------------------------------------------------------------
# Customer distribution: region → (count, order_multiplier)
# Stockholm is largest; Malmö boosted for Fresh Snacks later via product pool
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
    For Fresh Snacks orders in Malmö we apply a regional weight boost later.
    """
    nordic_coffee_skus = {
        "NCO-001": 9, "NCO-002": 6, "NCO-003": 7, "NCO-004": 4,
        "NCO-005": 3, "NCO-006": 3,
        "FJR-001": 5, "FJR-002": 4, "FJR-003": 3, "FJR-004": 3,
        # Baltic Roast appears at low weight in Nordic pool for market-share visibility
        "BLR-001": 2, "BLR-002": 2, "BLR-003": 1, "BLR-004": 1,
        # competitors for market share in Drinks
        "SPN-001": 3, "SPN-002": 2, "NDS-001": 2, "NDS-002": 2,
    }
    baltic_roasters_skus = {
        # BLR weights kept lower so Baltic holds ~25–35% of Coffee-category revenue
        "BLR-001": 4, "BLR-002": 3, "BLR-003": 3, "BLR-004": 2,
        # Nordic/Fjord products dominate even Baltic customers' baskets
        "NCO-001": 7, "NCO-002": 5, "FJR-001": 5, "FJR-002": 4,
    }
    fresh_snacks_skus = {
        "FSN-001": 8, "FSN-002": 7, "FSN-003": 6, "FSN-004": 5, "FSN-005": 4,
        "SMX-001": 5, "SMX-002": 4, "SMX-003": 4, "SMX-004": 3,
    }
    clean_home_skus = {
        "CLH-001": 7, "CLH-002": 6, "CLH-003": 5, "CLH-004": 5, "CLH-005": 4,
        "BHO-001": 5, "BHO-002": 4, "BHO-003": 4, "BHO-004": 3,
    }

    def build(sku_map):
        return [(products_by_sku[sku], w) for sku, w in sku_map.items() if sku in products_by_sku]

    return {
        "Nordic Coffee AB":   build(nordic_coffee_skus),
        "Fresh Snacks Ltd":   build(fresh_snacks_skus),
        "Clean Home Co":      build(clean_home_skus),
        "Baltic Roasters AB": build(baltic_roasters_skus),
    }


# ---------------------------------------------------------------------------
# Time multipliers
# ---------------------------------------------------------------------------

def nordic_coffee_trend_multiplier(order_date: datetime) -> float:
    """Gentle upward trend for Nordic Coffee over last 90 days."""
    days_ago = (TODAY - order_date).days
    if days_ago <= 90:
        # linearly ramp from 1.0 (90 days ago) to 1.6 (today)
        return 1.0 + 0.6 * (1 - days_ago / 90)
    return 1.0


def cold_brew_decay_multiplier(sku: str, order_date: datetime) -> float:
    """Cold Brew Can declines materially in last 30 days."""
    if sku not in ("NCO-003", "NCO-006"):
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
    db.query(OrderItem).delete()
    db.query(Order).delete()
    db.query(Customer).delete()
    db.query(Product).delete()
    db.query(Brand).delete()
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

                    # Pattern 1 & 4: Nordic Coffee Stockholm uplift + trend
                    if supplier_name == "Nordic Coffee AB" and region_name == "Stockholm":
                        w *= 1.5
                    if supplier_name == "Nordic Coffee AB":
                        w *= nordic_coffee_trend_multiplier(order_date)

                    # Pattern 3: Cold Brew decay in last 30 days
                    w *= cold_brew_decay_multiplier(prod.sku, order_date)

                    # Pattern 5: Fresh Snacks stronger in Malmö
                    if supplier_name == "Fresh Snacks Ltd" and region_name == "Malmö":
                        if prod.sku.startswith("FSN-"):
                            w *= 2.0

                    # Pattern 6: Clean Home stable (no extra modifiers)

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
