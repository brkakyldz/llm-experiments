"""Customer account records, the way a support tool shows them: the customer, the account's
credits and price adjustments, and every order on the account with its shipments.

Only one order matters to each conversation. The others are filled in from a small catalog with a
seed per customer, so the record is as long and as noisy as a real one and the deciding field is
one of many.
"""

import random
from datetime import date, timedelta

TODAY = "2026-10-19"

CATALOG = [
    ("Ceramic", "Hale stoneware mug", 14.00), ("Ceramic", "Oslo serving bowl", 32.00),
    ("Textiles", "Mira cushion cover", 24.00), ("Textiles", "Lune cotton throw", 58.00),
    ("Lighting", "Saga table lamp", 74.00), ("Lighting", "Orb pendant shade", 46.00),
    ("Kitchen", "Fen oak chopping board", 42.00), ("Kitchen", "Pella cast-iron pot", 95.00),
    ("Bath", "Tidal bath towel", 19.00), ("Bath", "Sana bath mat", 28.00),
    ("Decor", "Edda glass vase", 52.00), ("Decor", "Rune wall clock", 45.00),
    ("Furniture", "Ivo wall shelf", 44.00), ("Outlet", "Kiri bamboo tray", 18.00),
    ("Outlet", "Bly candle holder", 12.00), ("Storage", "Isla wicker basket", 38.00),
]
PROMOS = [None, None, None, "WELCOME10", "AUTUMN15", "CLEAR40"]


def d(s):
    return date.fromisoformat(s)


def plus_days(s, n):
    return (d(s) + timedelta(days=n)).isoformat()


def line(sku, name, price, category, seller="Northwind", **extra):
    out = {"sku": sku, "name": name, "category": category, "price": price, "seller": seller,
           "bundle_id": None, "personalisation": None, "assembled_by_northwind": False}
    out.update(extra)
    return out


def order(oid, order_date, lines, *, deliveries=None, status="delivered", promised=None,
          promo=None, method="Standard", fee=5.99, payment="Visa", moved_by_customer=False):
    """`deliveries` maps a delivery date to the skus in that shipment; one shipment by default.
    A shipment with delivery date None has shipped and not arrived."""
    if deliveries is None:
        deliveries = {plus_days(order_date, 4): [x["sku"] for x in lines]}
    shipments = []
    for n, (when, skus) in enumerate(deliveries.items(), 1):
        shipped = plus_days(order_date, n) if status != "processing" else None
        shipments.append({"shipment": n, "shipped_on": shipped, "delivered_on": when,
                          "items": skus})
    first = min((s["delivered_on"] for s in shipments if s["delivered_on"]), default=None)
    return {"order_id": oid, "order_date": order_date, "status": status, "promo_code": promo,
            "shipping_method": method, "shipping_fee": fee, "payment_method": payment,
            "promised_delivery_date": promised or first or plus_days(order_date, 4),
            "delivery_date_moved_by_customer": moved_by_customer,
            "items": lines, "shipments": shipments}


def filler_orders(seed, before, count=3, exclude=()):
    """Older orders on the same account, all delivered, none relevant to the conversation. They
    never hold a product named in `exclude` (the target's), so the record has one order that fits
    the customer's message."""
    rng = random.Random(seed)
    catalog = [c for c in CATALOG if c[1] not in exclude]
    out, day = [], d(before)
    for k in range(count):
        day -= timedelta(days=rng.randint(9, 40))
        picks = rng.sample(catalog, rng.randint(1, 3))
        lines = [line(f"F{seed % 1000:03d}{k}{j}", name, price, cat)
                 for j, (cat, name, price) in enumerate(picks)]
        fee = 0.00 if sum(x["price"] for x in lines) >= 75 else 5.99
        out.append(order(f"N-{28000 + (seed * 37 + k * 113) % 1900}", day.isoformat(), lines,
                         promo=rng.choice(PROMOS), fee=fee,
                         payment=rng.choice(["Visa", "Visa", "Mastercard"])))
    return out


def account(seed, name, target, *, member_since=None, credits=(), adjustments=(), store_credit=0.0):
    """The record the agent and the judge see. `target` is the order the customer writes about;
    it is listed among the account's other orders, newest first."""
    orders = sorted([target] + filler_orders(seed, target["order_date"],
                                              exclude={x["name"] for x in target["items"]}),
                    key=lambda o: o["order_date"], reverse=True)
    return {
        "today": TODAY,
        "customer": {"customer_id": f"C-{51000 + seed * 7}", "name": name,
                     "northwind_plus": {"member": member_since is not None,
                                        "member_since": member_since}},
        "account": {"store_credit_balance": store_credit,
                    "credits_issued": list(credits),
                    "price_adjustments": list(adjustments)},
        "orders": orders,
    }
