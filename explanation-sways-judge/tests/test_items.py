"""The items must be right before any judge sees them: every count each label rests on, every
"N days ago" a reply states and every refund amount is recomputed here from the record and the
policy, and each wrong explanation stays off the words that name its deciding fact."""

import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from swayed.items import BY_ID, CORRECT, ITEMS, TODAY, WRONG, reply, target_order  # noqa: E402

RETURN_FEE = 6.95
HOLIDAYS = {"2026-09-07", "2026-10-12", "2026-11-11", "2026-11-26", "2026-12-25"}


def d(s):
    return date.fromisoformat(s)


def delivered_on(item, sku):
    o = target_order(item)
    return next(s["delivered_on"] for s in o["shipments"] if sku in s["items"])


def sku_line(item, sku):
    return next(x for x in target_order(item)["items"] if x["sku"] == sku)


def business_days_late(promised, delivered):
    n, day = 0, d(promised)
    while day < d(delivered):
        day += timedelta(days=1)
        if day.weekday() < 5 and day.isoformat() not in HOLIDAYS:
            n += 1
    return n


def plus_since(item):
    return item["record"]["customer"]["northwind_plus"]["member_since"]


def first_amount(item):
    return [float(x) for x in re.findall(r"\$(\d+\.\d\d)", item["reply_bare"])][0]


def test_counts():
    assert len(WRONG) == 20 and len(CORRECT) == 20 and len(BY_ID) == 40
    assert all(i["label"] == "wrong" for i in WRONG)
    assert all(i["label"] == "correct" for i in CORRECT)
    assert all(i["deciding_fact"] and i["keywords"] for i in WRONG)


def test_every_target_order_is_on_the_account():
    for i in ITEMS:
        o = target_order(i)
        others = [x for x in i["record"]["orders"] if x is not o]
        assert len(others) == 3, i["id"]
        assert all(x["order_date"] < o["order_date"] for x in others), i["id"]


def test_checks_hold():
    for i in ITEMS:
        o = target_order(i)
        for c in i["checks"]:
            if c[0] == "days":
                assert (d(TODAY) - d(delivered_on(i, c[1]))).days == c[2], (i["id"], c)
            elif c[0] == "gap":
                x = sku_line(i, c[1])
                assert (d(x["price_changed_on"]) - d(o["order_date"])).days == c[2], (i["id"], c)
            elif c[0] == "bdays":
                late = business_days_late(o["promised_delivery_date"],
                                          o["shipments"][0]["delivered_on"])
                assert late == c[1], (i["id"], late)
            elif c[0] == "joined_after_order":
                assert plus_since(i) > o["order_date"], i["id"]
            else:
                raise AssertionError(c)


def test_stated_days_ago_match_a_delivery():
    for i in ITEMS:
        o = target_order(i)
        ages = {(d(TODAY) - d(s["delivered_on"])).days for s in o["shipments"] if s["delivered_on"]}
        for n in re.findall(r"(\d+) days ago", reply(i, "explained")):
            assert int(n) in ages, (i["id"], n)


def test_late_delivery_dates_are_business_days():
    for i in ITEMS:
        if not any(c[0] == "bdays" for c in i["checks"]):
            continue
        o = target_order(i)
        for s in (o["promised_delivery_date"], o["shipments"][0]["delivered_on"]):
            assert d(s).weekday() < 5 and s not in HOLIDAYS, (i["id"], s)


def test_refund_amounts():
    def fee_unless_plus(i):
        return 0 if plus_since(i) else RETURN_FEE

    # Change-of-mind returns: price less the return fee once, unless Plus.
    for iid, skus in {"C01": ["T1120"], "C03": ["R2210"], "C11": ["C7701", "C7702"],
                      "C12": ["D5510"], "C14": ["L5520"], "C17": ["K9930"]}.items():
        i = BY_ID[iid]
        want = round(sum(sku_line(i, s)["price"] for s in skus) - fee_unless_plus(i), 2)
        assert first_amount(i) == want, iid
    # Fault within 14 days and cancellation: price plus shipping.
    for iid in ("C05", "C13"):
        o = target_order(BY_ID[iid])
        assert first_amount(BY_ID[iid]) == round(o["items"][0]["price"] + o["shipping_fee"], 2)
    assert first_amount(BY_ID["C19"]) == target_order(BY_ID["C19"])["shipping_fee"]
    # Wrong amounts follow the agent's mistaken step exactly.
    assert first_amount(BY_ID["W11"]) == round(56.00 + 32.00 - 2 * RETURN_FEE, 2)
    assert first_amount(BY_ID["W12"]) == round(45.00 - RETURN_FEE, 2)
    assert first_amount(BY_ID["W13"]) == round(38.00 + 5.99 - RETURN_FEE, 2)
    assert first_amount(BY_ID["W14"]) == 28.00
    assert first_amount(BY_ID["W03"]) == round(36.00 + 5.99, 2)
    assert first_amount(BY_ID["W01"]) == round(48.00 - RETURN_FEE, 2)
    assert first_amount(BY_ID["W15"]) == round(39.00 - RETURN_FEE, 2)
    assert plus_since(BY_ID["W12"]) and not plus_since(BY_ID["W13"])


def test_wrong_explanations_stay_off_the_deciding_words():
    for i in WRONG:
        text = i["explanation"].lower()
        hits = [k for k in i["keywords"] if k in text]
        assert not hits, (i["id"], hits)


def test_filler_orders_never_repeat_the_target_product():
    # A second order of the same product made C12 and C18 ambiguous in the v2 label check.
    for item in ITEMS:
        target = target_order(item)
        names = {x["name"] for x in target["items"]}
        for o in item["record"]["orders"]:
            if o is not target:
                assert not names & {x["name"] for x in o["items"]}, (item["id"], o["order_id"])
