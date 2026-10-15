"""Evaluator 2: deterministic end-state check. Looks only at the store before and after the run."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..world import money

# The fields a correct refund is allowed to change on its order.
REFUND_FIELDS = {"status", "refunded_total"}


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class OutcomeResult:
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)


def check_outcome(initial: dict, final: dict, expected_refunds: list[dict]) -> OutcomeResult:
    res = OutcomeResult()
    old_ids = {r["refund_id"] for r in initial["refunds"]}
    new_refunds = [r for r in final["refunds"] if r["refund_id"] not in old_ids]
    expected_orders = {e["order_id"] for e in expected_refunds}

    # O1: exactly the expected refunds exist - one per expected order, none anywhere else.
    if not expected_refunds:
        res.checks.append(Check("O1 refund count", not new_refunds,
                                "no new refunds" if not new_refunds else
                                f"{len(new_refunds)} unexpected refund(s): {_fmt(new_refunds)}"))
    else:
        problems = []
        for e in expected_refunds:
            n = sum(r["order_id"] == e["order_id"] for r in new_refunds)
            if n != 1:
                problems.append(f"order {e['order_id']}: {n} refunds, expected 1")
        stray = [r for r in new_refunds if r["order_id"] not in expected_orders]
        if stray:
            problems.append(f"unexpected refund(s): {_fmt(stray)}")
        res.checks.append(Check("O1 refund count", not problems,
                                "; ".join(problems) or f"exactly one refund for {', '.join(sorted(expected_orders))}"))

        # O2 / O3: amount and method of each expected refund.
        for e in expected_refunds:
            mine = [r for r in new_refunds if r["order_id"] == e["order_id"]]
            if len(mine) != 1:
                res.checks.append(Check("O2 amount", False, f"order {e['order_id']}: no single refund to check"))
                res.checks.append(Check("O3 method", False, f"order {e['order_id']}: no single refund to check"))
                continue
            r = mine[0]
            amount_ok = money(r["amount"]) == money(e["amount"])
            res.checks.append(Check("O2 amount", amount_ok, f"{r['amount']} (expected {money(e['amount'])})"))
            pay = initial["orders"][e["order_id"]]["payment"]
            method_ok = r["method"] == pay["method"] and r["card_last4"] == pay["card_last4"]
            res.checks.append(Check("O3 method", method_ok,
                                    f"{r['method']} *{r['card_last4']} (original {pay['method']} *{pay['card_last4']})"))

    # O4: nothing else changed. Customers and pre-existing refunds are untouched; orders change
    # only on the refund fields, and only for orders that were meant to be refunded.
    changes = []
    if final["customers"] != initial["customers"]:
        changes.append("customers table changed")
    final_by_id = {r["refund_id"]: r for r in final["refunds"]}
    for r in initial["refunds"]:
        if final_by_id.get(r["refund_id"]) != r:
            changes.append(f"existing refund {r['refund_id']} changed")
    for oid, before in initial["orders"].items():
        after = final["orders"].get(oid)
        if after is None:
            changes.append(f"order {oid} deleted")
            continue
        allowed = REFUND_FIELDS if oid in expected_orders else set()
        diff = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k) and k not in allowed)
        if diff:
            changes.append(f"order {oid}: {', '.join(f'{k} {before.get(k)!r}->{after.get(k)!r}' for k in diff)}")
    for oid in final["orders"].keys() - initial["orders"].keys():
        changes.append(f"new order {oid}")
    res.checks.append(Check("O4 no other changes", not changes, "; ".join(changes) or "no other record changed"))
    return res


def _fmt(refunds: list[dict]) -> str:
    return ", ".join(f"{r['refund_id']} order {r['order_id']} {r['amount']}" for r in refunds)
