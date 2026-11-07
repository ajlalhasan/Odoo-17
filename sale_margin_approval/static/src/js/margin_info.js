/** @odoo-module **/

/**
 * "Show Margin Info" button on the portal order page.
 *
 * Odoo 17 note: the legacy `web.ajax` module (ajax.jsonRpc) was removed in 17.0.
 * Its drop-in replacement is `jsonrpc` from "@web/core/network/rpc_service",
 * which performs the same JSON-RPC POST and resolves with `result`.
 * The widget itself is the standard publicWidget (formerly `web.public.widget`).
 */
import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";

const ANIMATION_MS = 250; // keep in sync with margin_info.scss

publicWidget.registry.SaleMarginInfo = publicWidget.Widget.extend({
    selector: ".o_margin_info_btn",
    events: {
        click: "_onClick",
    },

    start() {
        this.orderId = parseInt(this.el.dataset.orderId, 10);
        this.accessToken = this.el.dataset.accessToken || undefined;
        this.panel = document.getElementById(`o_margin_info_panel_${this.orderId}`);
        this.label = this.el.querySelector("span");
        this.isOpen = false;
        this.isLoading = false;
        return this._super(...arguments);
    },

    destroy() {
        clearTimeout(this._hideTimer);
        this._super(...arguments);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    async _onClick(ev) {
        ev.preventDefault();
        if (!this.panel || this.isLoading) {
            return;
        }
        if (this.isOpen) {
            this._hide();
            return;
        }
        // Fetch on every open: the salesperson may have changed the order meanwhile.
        this._setLoading(true);
        try {
            const data = await jsonrpc(`/my/orders/${this.orderId}/margin_info`, {
                access_token: this.accessToken,
            });
            this._render(data);
        } catch {
            this._renderError(_t("Margin information could not be loaded. Please try again."));
        } finally {
            this._setLoading(false);
        }
        this._show();
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _render(data) {
        if (!data || data.error) {
            this._renderError(_t("Margin information is not available for this order."));
            return;
        }
        const content = this.panel.querySelector(".o_margin_info_content");
        const error = this.panel.querySelector(".o_margin_info_error");
        const pct = this.panel.querySelector(".o_margin_info_pct");
        const badge = this.panel.querySelector(".o_margin_info_approval");

        error.classList.add("d-none");
        content.classList.remove("d-none");
        pct.textContent = `${Number(data.margin_percentage).toFixed(2)} %`;
        pct.classList.toggle("text-danger", data.requires_manager_approval);

        badge.textContent = data.requires_manager_approval ? _t("Required") : _t("Not required");
        badge.classList.toggle("text-bg-danger", data.requires_manager_approval);
        badge.classList.toggle("text-bg-success", !data.requires_manager_approval);
    },

    _renderError(message) {
        const error = this.panel.querySelector(".o_margin_info_error");
        error.textContent = message;
        error.classList.remove("d-none");
        this.panel.querySelector(".o_margin_info_content").classList.add("d-none");
    },

    _show() {
        clearTimeout(this._hideTimer);
        this.panel.hidden = false;
        // Next frame so the browser registers the start state before transitioning.
        requestAnimationFrame(() => this.panel.classList.add("o_margin_info_open"));
        this.isOpen = true;
        this.el.setAttribute("aria-expanded", "true");
        this.label.textContent = _t("Hide Margin Info");
    },

    _hide() {
        this.panel.classList.remove("o_margin_info_open");
        this._hideTimer = setTimeout(() => (this.panel.hidden = true), ANIMATION_MS);
        this.isOpen = false;
        this.el.setAttribute("aria-expanded", "false");
        this.label.textContent = _t("Show Margin Info");
    },

    _setLoading(loading) {
        this.isLoading = loading;
        this.el.disabled = loading;
        this.el.classList.toggle("o_margin_info_loading", loading);
    },
});

export default publicWidget.registry.SaleMarginInfo;
