from odoo import _, api, fields, models
from odoo.tools import float_compare

# Threshold below which a quotation needs a manager's blessing.
MARGIN_APPROVAL_THRESHOLD = 10.0
# Same precision as the field: comparisons are made on 2 decimals.
MARGIN_PRECISION = 2


class SaleOrder(models.Model):
    _inherit = "sale.order"

    margin_percentage = fields.Float(
        string="Margin (%)",
        compute="_compute_margin_percentage",
        store=True,  # stored: searchable / groupable, and read cheaply by the portal route
        digits=(16, 2),
        help="(Total - Untaxed) / Untaxed * 100, as defined in the specification.",
    )
    requires_manager_approval = fields.Boolean(
        string="Requires Manager Approval",
        compute="_compute_requires_manager_approval",
        store=True,
        help=f"Set automatically when the margin is below {MARGIN_APPROVAL_THRESHOLD:g} %.",
    )
    manager_approval_requested = fields.Boolean(
        string="Approval Requested",
        readonly=True,
        copy=False,
        help="Set by the 'Request Manager Approval' button; prevents duplicate requests.",
    )
    manager_approval_request_date = fields.Datetime(
        string="Approval Requested On",
        readonly=True,
        copy=False,
    )

    @api.depends("amount_total", "amount_untaxed")
    def _compute_margin_percentage(self):
        for order in self:
            if order.amount_untaxed:
                order.margin_percentage = (
                    (order.amount_total - order.amount_untaxed) / order.amount_untaxed * 100.0
                )
            else:
                # Empty quotation or 100 % discount: avoid ZeroDivisionError.
                order.margin_percentage = 0.0

    @api.depends("margin_percentage")
    def _compute_requires_manager_approval(self):
        """Strictly below the threshold, compared on the field's own precision.

        The raw division is not exact (99.90 untaxed with exactly 10 % tax
        gives 9.999999999999993). The Float field already rounds to 2 decimals
        when the value is assigned; float_compare on the same precision keeps
        the 10 % rule correct even if that rounding is ever changed.
        """
        for order in self:
            order.requires_manager_approval = (
                float_compare(
                    order.margin_percentage,
                    MARGIN_APPROVAL_THRESHOLD,
                    precision_digits=MARGIN_PRECISION,
                )
                < 0
            )

    def action_request_manager_approval(self):
        """Log the request in the chatter and move draft quotations to 'sent'.

        Three deliberate restrictions beyond the literal specification:

        * Only low-margin orders are handled. Running the server action on a
          selection that includes normal orders leaves those untouched.
        * Only *draft* quotations change state, through Odoo's own
          action_quotation_sent. Moving a confirmed ('sale') or
          cancelled order back to 'sent' would corrupt the sales flow, so
          "if not already" is read as "if still a draft".
        * The action is idempotent. A second click (or a second run of the
          server action over the same records) posts nothing and changes
          nothing, so a manager's chatter is not flooded by an impatient user.
        """
        todo = self.filtered(
            lambda o: o.requires_manager_approval and not o.manager_approval_requested
        )
        if not todo:
            return True
        body = _("Manager approval requested for low margin order.")
        for order in todo:
            order.message_post(body=body, subtype_xmlid="mail.mt_note")
        todo.filtered(lambda o: o.state == "draft").action_quotation_sent()
        todo.write({
            "manager_approval_requested": True,
            "manager_approval_request_date": fields.Datetime.now(),
        })
        return True

    def _get_margin_info(self):
        """Payload shared by the portal JSON route (single source of truth)."""
        self.ensure_one()
        return {
            "margin_percentage": round(self.margin_percentage, MARGIN_PRECISION),
            "requires_manager_approval": self.requires_manager_approval,
        }
