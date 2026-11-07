# Sale Margin Approval (Odoo 17)

Technical assessment, Parts 1 and 2. Installable module, `depends: ["sale"]`.

## What it does

**Backend (Part 1)**
- `sale.order.margin_percentage`: stored computed Float, 2 decimals, `(amount_total - amount_untaxed) / amount_untaxed * 100`, 0 when the order is empty.
- `sale.order.requires_manager_approval`: stored computed Boolean, `True` when the margin is strictly below 10 %.
- New **Margin Information** tab on the quotation form. The margin turns red (`decoration-danger`) and a red alert banner appears when approval is required.
- **Request Manager Approval** header button (visible on low-margin draft/sent quotations) plus the same logic as a server action in the *Action* menu (list and form, so it works on several orders at once; normal-margin orders in the selection are skipped). It posts the chatter note *"Manager approval requested for low margin order."* and moves draft quotations to *Quotation Sent*.
- Bonus: optional *Margin (%)* column in the quotations list, and *Needs Manager Approval* / *Approval Requested* search filters.

**Portal (Part 2)**
- **Show Margin Info** button in the portal document button group of `/my/orders/<id>` (next to Download / Print, or *View Details* on a quotation).
- JSON route `/my/orders/<int:order_id>/margin_info` returning `{"margin_percentage": 12.5, "requires_manager_approval": false}` (as the JSON-RPC `result`).
- `publicWidget` that fetches the data and fades/slides an inline Bootstrap card in and out.

## Design decisions worth reviewing

1. **Odoo 17 API changes vs. the brief.** The brief mentions `attrs` and `ajax.jsonRpc`; both were removed in 17.0, so the brief's literal API would not run.
   - `attrs` → direct `invisible="..."` / `decoration-danger="..."` expressions.
   - `ajax.jsonRpc` (`web.ajax`) → `jsonrpc` from `@web/core/network/rpc_service`, the official replacement with the same JSON-RPC behaviour.
   - `web.public.widget` → `@web/legacy/js/public/public_widget` (same publicWidget class, ES-module path).
2. **Threshold compared with `float_compare` on 2 decimals.** The raw division is not exact: €99.90 with exactly 10 % tax (€9.99) gives `9.999999999999993`. The Float field already rounds to 2 decimals when the value is assigned; comparing with `float_compare` on the same precision keeps the 10 % rule correct even if that rounding changes. `test_margin_exactly_at_threshold` uses that amount.
3. **"State to sent if not already"** is applied only to *draft* quotations, through Odoo's own `action_quotation_sent`. Moving a confirmed or cancelled order back to *sent* would corrupt the sales flow.
4. **The button is idempotent.** `manager_approval_requested` (+ request date, both `copy=False`) stops a second click from flooding the chatter, and hides the button once a request is pending. Duplicating the quotation resets it.
5. **Security of the route.** Access is verified with `CustomerPortal._document_check_access` (record rules for logged-in portal users, `access_token` for shared links) before any `sudo` read. Unknown or forbidden orders return `{"error": "not_found"}` without leaking whether the order exists.
6. **The formula is not really a margin.** `(total - untaxed) / untaxed` is the *tax rate* of the order (21 % VAT gives 21 %). It is implemented exactly as specified, but in production I would base this on Odoo's `sale_margin` module (`margin_percent` = (price − cost) / price), and I would **not** expose real margins to customers on the portal. The switch is small: depend on `sale_margin` and compute from `margin_percent * 100` (Odoo stores it as a fraction). It also needs cost prices on the products. Note that 0 % VAT orders (intra-EU B2B, export) and empty orders also get 0 % and would always need approval under the current formula.
7. **Stored fields** so the portal route and list filter read a column instead of recomputing, and so managers can group/sort by margin.

## Not production-ready without these

- A real approval **workflow** (request → approve/refuse, with a manager group and a blocking check at confirmation) instead of a flag plus a chatter note. The brief asks only for the note and the state change.
- `manager_approval_requested` is not reset when the order is edited afterwards; with a real workflow, re-opening the request would be part of it.

## Verified

On Odoo 17.0 Community (official `odoo:17` Docker image, PostgreSQL 15, demo data):

- The module installs on a fresh database with no errors.
- All 17 automated tests pass: `0 failed, 0 error(s) of 17 tests`.
- Checked by hand: form tab and red highlight, button and chatter note, server action, list column and filters, and, through the admin's customer preview, the portal button and panel for a low- and a normal-margin order plus the JSON response of `/my/orders/<id>/margin_info` in DevTools.

Not yet checked: the customer's exact Enterprise build (the module depends only on `sale`, and the portal `xpath` anchors `sale.sale_order_portal_template` / `o_download_pdf` and the form's `other_information` page are shared with Community), and a logged-in portal user (the automated route tests cover the access-token path).

## Install and test

```bash
odoo-bin -d <db> -i sale_margin_approval
odoo-bin -d <db> -u sale_margin_approval --test-enable --test-tags /sale_margin_approval --stop-after-init
```

| Test | Expected |
| --- | --- |
| 21 % tax | 21.00 %, no approval |
| 9 % tax | 9.00 %, approval required |
| 10 % tax (boundary) | 10.00 %, **no** approval |
| 9.99 % tax | 9.99 %, approval required |
| Taxes changed on the line | Both fields recompute |
| Order without lines | 0.00 %, no division error |
| Button on a draft | Note posted, state → sent, flag set |
| Button clicked twice | No second note |
| Button on a confirmed order | Stays *sale* |
| Button on a cancelled order | Stays *cancel* |
| Duplicated quotation | Request flag cleared |
| Server action from the list | Same as the button |
| Route + valid token | JSON returned |
| Route + wrong / missing token | `{"error": "not_found"}` |
| Route + another order's token | `{"error": "not_found"}` |
| Route + unknown order id | `{"error": "not_found"}` |

Not covered by automated tests: the browser behaviour of the widget (fade, error notice, mobile layout) and the exact portal XPath. Those need a running instance.

## Files

```
sale_margin_approval/
├── __manifest__.py
├── models/sale_order.py             fields, computes, button logic
├── controllers/portal.py            JSON route
├── data/ir_actions_server.xml       server action (Action menu)
├── views/sale_order_views.xml       form tab, header button, list column, filters
├── views/sale_portal_templates.xml  portal button + inline panel
├── static/src/js/margin_info.js     publicWidget
├── static/src/scss/margin_info.scss fade/slide animation
└── tests/test_sale_margin_approval.py
```
