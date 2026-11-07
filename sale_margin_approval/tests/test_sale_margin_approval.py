import json

from odoo.tests import HttpCase, TransactionCase, tagged


class MarginCommon:

    @classmethod
    def _setup_margin_data(cls):
        cls.partner = cls.env["res.partner"].create({"name": "Tile Customer"})
        cls.product = cls.env["product.product"].create({
            "name": "Floor Tile 60x60",
            "list_price": 100.0,
            "taxes_id": [(5, 0, 0)],
        })
        cls.tax_21 = cls._tax("VAT 21% (test)", 21.0)
        cls.tax_10 = cls._tax("VAT 10% (test)", 10.0)
        cls.tax_9 = cls._tax("VAT 9% (test)", 9.0)

    @classmethod
    def _tax(cls, name, amount):
        return cls.env["account.tax"].create({
            "name": name,
            "amount": amount,
            "amount_type": "percent",
            "type_tax_use": "sale",
        })

    @classmethod
    def _create_order(cls, taxes, price_unit=100.0):
        return cls.env["sale.order"].create({
            "partner_id": cls.partner.id,
            "order_line": [(0, 0, {
                "product_id": cls.product.id,
                "product_uom_qty": 1,
                "price_unit": price_unit,
                "tax_id": [(6, 0, taxes.ids)],
            })],
        })


@tagged("post_install", "-at_install")
class TestSaleMarginApproval(MarginCommon, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_margin_data()

    # --- compute -----------------------------------------------------------

    def test_margin_above_threshold(self):
        order = self._create_order(self.tax_21)
        self.assertAlmostEqual(order.margin_percentage, 21.0, places=2)
        self.assertFalse(order.requires_manager_approval)

    def test_margin_below_threshold(self):
        order = self._create_order(self.tax_9)
        self.assertAlmostEqual(order.margin_percentage, 9.0, places=2)
        self.assertTrue(order.requires_manager_approval)

    def test_margin_exactly_at_threshold(self):
        """10.00 % is NOT below 10 %. 99.90 + 10 % tax (9.99) is the awkward
        case: the raw division gives 9.999999999999993."""
        for price in (100.0, 99.90):
            order = self._create_order(self.tax_10, price_unit=price)
            self.assertAlmostEqual(order.margin_percentage, 10.0, places=2)
            self.assertFalse(order.requires_manager_approval, f"flagged at price {price}")

    def test_margin_just_under_threshold(self):
        order = self._create_order(self.tax_10, price_unit=100.0)
        order.order_line.tax_id = [(6, 0, self._tax("VAT 9.99% (test)", 9.99).ids)]
        self.assertAlmostEqual(order.margin_percentage, 9.99, places=2)
        self.assertTrue(order.requires_manager_approval)

    def test_recompute_when_lines_change(self):
        order = self._create_order(self.tax_21)
        order.order_line.tax_id = [(6, 0, self.tax_9.ids)]
        self.assertAlmostEqual(order.margin_percentage, 9.0, places=2)
        self.assertTrue(order.requires_manager_approval)

    def test_empty_order_no_division_error(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertEqual(order.margin_percentage, 0.0)

    # --- button / server action --------------------------------------------

    def test_request_approval_posts_note_and_sends(self):
        order = self._create_order(self.tax_9)
        self.assertEqual(order.state, "draft")
        order.action_request_manager_approval()
        self.assertEqual(order.state, "sent")
        self.assertTrue(order.manager_approval_requested)
        self.assertTrue(order.manager_approval_request_date)
        self.assertIn(
            "Manager approval requested for low margin order.",
            order.message_ids[0].body,
        )

    def test_request_approval_is_idempotent(self):
        """A second click posts nothing: the manager's chatter is not flooded."""
        order = self._create_order(self.tax_9)
        order.action_request_manager_approval()
        count = len(order.message_ids)
        order.action_request_manager_approval()
        self.assertEqual(len(order.message_ids), count)

    def test_request_approval_keeps_confirmed_orders(self):
        order = self._create_order(self.tax_9)
        order.action_confirm()
        order.action_request_manager_approval()
        self.assertEqual(order.state, "sale")

    def test_request_approval_keeps_cancelled_orders(self):
        order = self._create_order(self.tax_9)
        order._action_cancel()
        order.action_request_manager_approval()
        self.assertEqual(order.state, "cancel")

    def test_duplicated_order_can_request_again(self):
        order = self._create_order(self.tax_9)
        order.action_request_manager_approval()
        copy = order.copy()
        self.assertFalse(copy.manager_approval_requested)
        self.assertFalse(copy.manager_approval_request_date)

    def test_server_action(self):
        """Handles low-margin orders only; a normal order in the same
        selection is left alone."""
        low = self._create_order(self.tax_9)
        normal = self._create_order(self.tax_21)
        action = self.env.ref("sale_margin_approval.action_server_request_manager_approval")
        action.with_context(active_model="sale.order", active_ids=(low | normal).ids).run()
        self.assertEqual(low.state, "sent")
        self.assertTrue(low.manager_approval_requested)
        self.assertEqual(normal.state, "draft")
        self.assertFalse(normal.manager_approval_requested)
        self.assertFalse(normal.message_ids.filtered(
            lambda m: "Manager approval requested" in (m.body or "")))


@tagged("post_install", "-at_install")
class TestSaleMarginPortalRoute(MarginCommon, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_margin_data()
        cls.order = cls._create_order(cls.tax_21)
        cls.order._portal_ensure_token()
        cls.other_order = cls._create_order(cls.tax_9)
        cls.other_order._portal_ensure_token()

    def _call(self, order, access_token=None):
        url = f"/my/orders/{order.id}/margin_info"
        payload = {"jsonrpc": "2.0", "method": "call", "id": 1,
                   "params": {"access_token": access_token}}
        res = self.url_open(url, data=json.dumps(payload),
                            headers={"Content-Type": "application/json"})
        self.assertEqual(res.status_code, 200)
        return res.json()["result"]

    def test_route_with_valid_token(self):
        result = self._call(self.order, self.order.access_token)
        self.assertEqual(result, {"margin_percentage": 21.0, "requires_manager_approval": False})

    def test_route_rejects_bad_token(self):
        self.assertEqual(self._call(self.order, "wrong-token"), {"error": "not_found"})

    def test_route_rejects_missing_token(self):
        self.assertEqual(self._call(self.order), {"error": "not_found"})

    def test_route_rejects_other_orders_token(self):
        """A valid token for order A must not open order B."""
        self.assertEqual(
            self._call(self.other_order, self.order.access_token),
            {"error": "not_found"},
        )

    def test_route_unknown_order(self):
        url = "/my/orders/999999999/margin_info"
        payload = {"jsonrpc": "2.0", "method": "call", "id": 1, "params": {}}
        res = self.url_open(url, data=json.dumps(payload),
                            headers={"Content-Type": "application/json"})
        self.assertEqual(res.json()["result"], {"error": "not_found"})
