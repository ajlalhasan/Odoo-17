{
    "name": "Sale Margin Approval",
    "version": "17.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Margin % on quotations, manager-approval flag, and a portal 'Show Margin Info' widget",
    "description": """
Technical assessment - Part 1 & Part 2

* sale.order.margin_percentage (computed, stored, 2 decimals)
* sale.order.requires_manager_approval (computed: margin < 10 %)
* "Margin Information" section on the quotation form, red highlight when approval is needed
* "Request Manager Approval" button + server action (chatter note, draft -> sent)
* Portal: "Show Margin Info" button next to Download / Print, data loaded via
  JSON route /my/orders/<id>/margin_info, publicWidget with fade animation
""",
    "author": "Ajlal Hasan",
    "license": "LGPL-3",
    "depends": ["sale"],
    "data": [
        "data/ir_actions_server.xml",
        "views/sale_order_views.xml",
        "views/sale_portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "sale_margin_approval/static/src/js/margin_info.js",
            "sale_margin_approval/static/src/scss/margin_info.scss",
        ],
    },
    "installable": True,
    "application": False,
}
