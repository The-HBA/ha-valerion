/*
 * Visual editor of the Valerion card: pick the projector.
 * Uses Home Assistant's own ha-form with a device selector that lists only
 * Valerion projectors.
 */

const SCHEMA = [
  {
    name: "device_id",
    required: true,
    selector: { device: { filter: { integration: "valerion" } } },
  },
];

const LABELS = { device_id: "Projector" };

class ValerionCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (schema) => LABELS[schema.name] || schema.name;
      this._form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        const config = { ...this._config, ...ev.detail.value };
        if (!config.device_id) delete config.device_id;
        this._config = config;
        this.dispatchEvent(
          new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }),
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = SCHEMA;
    this._form.data = this._config;
  }
}

if (!customElements.get("valerion-card-editor")) {
  customElements.define("valerion-card-editor", ValerionCardEditor);
}
