from odoo import http
from odoo.exceptions import AccessError, MissingError

from odoo.addons.portal.controllers.portal import CustomerPortal


class SaleMarginPortal(CustomerPortal):

    @http.route(
        "/my/orders/<int:order_id>/margin_info",
        type="json",
        auth="public",
        methods=["POST"],
    )
    def portal_order_margin_info(self, order_id, access_token=None, **kwargs):
        """Return the margin information of one portal order as JSON.

        Called through JSON-RPC (``jsonrpc`` in Odoo 17, formerly ``ajax.jsonRpc``),
        so the HTTP body is ``{"jsonrpc": "2.0", "id": .., "result": {...}}`` and
        ``result`` is exactly the payload from the specification:
        ``{"margin_percentage": 12.5, "requires_manager_approval": false}``.

        Access is checked the same way the portal order page checks it: the
        logged-in partner's record rules, or a valid ``access_token`` for
        anonymous links. Only after that check do we read with sudo.
        """
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return {"error": "not_found"}
        return order_sudo._get_margin_info()
