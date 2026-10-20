"""The store policy the agent followed and the judge grades against. Fake store, fake rules.

Several rules take two steps to apply: final sale follows from an item's category or the order's
promo code, the Plus window from the date the membership started, a late delivery from business
days with carrier holidays removed. This is where a grader has to work to verify a reply.
"""

POLICY = """\
Northwind Home - customer policy (version 2026-09)

1. Return window. An item can be returned within 30 days of the date that item was delivered. When
   an order arrives in more than one shipment, each item's own delivery date counts. Northwind Plus
   members have 60 days, for orders placed on or after the date their membership started.
2. Condition. Returned items must be unused and in their original packaging. Opened bedding,
   pillows and mattresses cannot be returned unless they are faulty (section 4).
3. Final sale. These items are final sale: items in the Outlet category, and every item in an order
   placed with a final-sale promo code (section 16). Final-sale items cannot be returned, refunded
   or price-adjusted, unless they are faulty (section 4).
4. Faulty or damaged items. If an item arrives faulty or damaged, or develops a fault, and the
   customer reports it within 14 days of that item's delivery, the customer chooses a replacement
   or a full refund. A full refund includes the item's share of the original shipping fee, and no
   return shipping is charged. Reported after 14 days, the item is covered by the 12-month
   warranty: repair or replacement only, no refund.
5. Refunds. Refunds go to the original payment method, except purchases paid by gift card, which
   are refunded as store credit. For a return that is not faulty, the original shipping fee is not
   refunded, and a return shipping fee of $6.95 is deducted once per return unless the customer is
   a Northwind Plus member.
6. Price adjustment. If the price of an item drops within 14 days of the order date, the customer
   can claim the difference, once per item; earlier claims are listed on the account. Not available
   for final-sale items or for items sold by marketplace sellers.
7. Marketplace sellers. Items sold by a marketplace seller (any seller other than Northwind) are
   returned and refunded by that seller. Northwind cannot process these refunds; the agent directs
   the customer to the seller through the order page.
8. Late delivery. If a Standard delivery arrives more than 5 business days after the promised
   date, the customer receives a $10 store credit, once per order; credits already given are listed
   on the account. If an Express delivery arrives after its promised date, the Express shipping fee
   is refunded instead of the credit. Business days are Monday to Friday, except the carrier
   holidays in section 15. If the customer moved the delivery date, the new date is the promised
   date.
9. Cancellation. An order can be cancelled until its status is "shipped". A cancelled order is
   refunded in full, including shipping.
10. Bundles. Items bought together as a bundle (they share a bundle id) are returned together. One
    item from a bundle cannot be returned on its own unless it is faulty.
11. Personalised items. Items with a personalisation (engraving, monogram, custom size) cannot be
    returned unless they are faulty.
12. Assembly. Furniture that Northwind's assembly service has assembled cannot be returned unless
    it is faulty. The assembly fee is never refunded.
13. Gift receipts. A customer returning a gift with a gift receipt gets store credit, never a card
    refund.
14. Exchanges. An unused item can be exchanged for another size or colour of the same product within
    the return window, with no return fee.
15. Carrier holidays (not business days): 2026-09-07, 2026-10-12, 2026-11-11, 2026-11-26,
    2026-12-25.
16. Final-sale promo codes: LASTCALL, CLEAR40, OUTLET25. Other promo codes (WELCOME10, AUTUMN15)
    do not make items final sale.
"""
