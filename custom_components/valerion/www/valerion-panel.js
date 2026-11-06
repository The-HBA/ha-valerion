/*
 * Valerion sidebar page for Home Assistant (custom panel "valerion-panel").
 *
 * Shows the Valerion card full screen under a Home Assistant style top bar.
 * With several projectors a picker chooses one; the choice is remembered in
 * this browser. Plain JavaScript custom element: no build step, no libraries.
 *
 * Home Assistant sets three properties on the panel: hass, narrow and panel.
 */

const DOMAIN = "valerion";
const PANEL_TYPE = "valerion-panel";
const STORAGE_KEY = "valerion-panel-device";
// The card is loaded with the same ?v= as this file, so both update together.
const CARD_URL = new URL(`./valerion-card.js${new URL(import.meta.url).search}`, import.meta.url)
  .href;
// How long to wait for Home Assistant's ha-card before showing the card anyway.
const HA_CARD_WAIT_MS = 3000;

const MENU_ICON = "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z";
const PROJECTOR_ICON =
  "M4,6H20A2,2 0 0,1 22,8V15A2,2 0 0,1 20,17V18A1,1 0 0,1 19,19H17A1,1 0 0,1 16,18V17H8V18A1,1 0 0,1 7,19H5A1,1 0 0,1 4,18V17A2,2 0 0,1 2,15V8A2,2 0 0,1 4,6M15.5,7.5A4,4 0 0,0 11.5,11.5A4,4 0 0,0 15.5,15.5A4,4 0 0,0 19.5,11.5A4,4 0 0,0 15.5,7.5M15.5,9.5A2,2 0 0,1 17.5,11.5A2,2 0 0,1 15.5,13.5A2,2 0 0,1 13.5,11.5A2,2 0 0,1 15.5,9.5M4,8V10H9V8H4M4,11V13H9V11H4M4,14V16H9V14H4Z";

const svg = (path, size = 24) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><path fill="currentColor" d="${path}"/></svg>`;

const readChoice = () => {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
};

const storeChoice = (deviceId) => {
  try {
    window.localStorage.setItem(STORAGE_KEY, deviceId);
  } catch {
    // Storage blocked (private window, settings): the choice lasts until reload.
  }
};

/** The Valerion projectors as [{id, name}], sorted by name. */
function findProjectors(hass) {
  const ids = new Set();
  for (const entry of Object.values(hass?.entities || {})) {
    if (entry.platform === DOMAIN && entry.device_id) ids.add(entry.device_id);
  }
  return [...ids]
    .map((id) => {
      const device = hass.devices?.[id];
      return { id, name: device?.name_by_user || device?.name || "Valerion projector" };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * Make sure Home Assistant's ha-card is defined: on a page opened straight
 * from the sidebar no dashboard may have loaded it yet. The card helpers
 * load the built-in cards, and with them ha-card.
 */
async function ensureHaCard() {
  if (customElements.get("ha-card")) return;
  try {
    const helpers = await window.loadCardHelpers?.();
    helpers?.createCardElement({ type: "entities", entities: [] });
  } catch {
    // Older or unusual frontends: the card still works, only without its frame.
  }
  await Promise.race([
    customElements.whenDefined("ha-card"),
    new Promise((resolve) => setTimeout(resolve, HA_CARD_WAIT_MS)),
  ]);
}

const STYLES = `
:host{display:flex;flex-direction:column;height:100%;min-height:100%;box-sizing:border-box;
  background:var(--primary-background-color,#fafafa);color:var(--primary-text-color,#212121);
  font-family:var(--ha-font-family-body,Roboto,system-ui,sans-serif)}
.toolbar{display:flex;align-items:center;gap:4px;flex:none;box-sizing:border-box;
  height:var(--header-height,56px);padding:0 12px;
  background:var(--app-header-background-color,var(--primary-background-color,#fafafa));
  color:var(--app-header-text-color,var(--primary-text-color,#212121));
  border-bottom:var(--app-header-border-bottom,none)}
.menu{width:48px;height:48px;border:0;border-radius:50%;padding:0;
  display:grid;place-items:center;background:none;color:inherit;cursor:pointer;
  -webkit-tap-highlight-color:transparent}
.menu[hidden]{display:none}
.menu:hover{background:color-mix(in srgb,currentColor 8%,transparent)}
.menu:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:-2px}
.title{flex:1;min-width:0;margin-inline-start:12px;font-size:20px;font-weight:400;line-height:1.2;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.content{flex:1;min-height:0;overflow-y:auto;container-type:inline-size}
.wrap{box-sizing:border-box;max-width:820px;margin:0 auto;padding:16px;display:flex;flex-direction:column;gap:12px}
@container (max-width:599px){.wrap{padding:8px}}
.picker{display:flex;align-items:center;gap:8px}
.picker[hidden]{display:none}
.picker select{flex:1;min-width:0;height:48px;padding:0 12px;box-sizing:border-box;
  border:1px solid var(--divider-color,rgba(0,0,0,.12));border-radius:var(--ha-card-border-radius,12px);
  background:var(--card-background-color,#fff);color:var(--primary-text-color,#212121);
  font:inherit;font-size:16px}
.picker select:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:1px}
@container (min-width:600px){.picker select{flex:0 1 360px}}
.empty{display:flex;flex-direction:column;align-items:center;gap:12px;padding:48px 16px;text-align:center;
  color:var(--secondary-text-color,#727272);font-size:16px;line-height:1.4}
.empty[hidden]{display:none}
.empty svg{width:48px;height:48px}
.empty strong{color:var(--primary-text-color,#212121);font-weight:500}
`;

class ValerionPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._narrow = false;
    this._projectors = [];
    this._entitiesSource = undefined;
    this._devicesSource = undefined;
    this._deviceId = null;
    this._cardReady = false;
    this._card = null;
    this._cardDevice = null;
    this._failed = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  get hass() {
    return this._hass;
  }

  set narrow(narrow) {
    this._narrow = Boolean(narrow);
    this._update();
  }

  get narrow() {
    return this._narrow;
  }

  set panel(panel) {
    this._panel = panel;
    this._update();
  }

  get panel() {
    return this._panel;
  }

  connectedCallback() {
    this._build();
    if (!this._loading) {
      this._loading = Promise.all([import(CARD_URL), ensureHaCard()]).then(
        () => {
          this._cardReady = true;
          this._update();
        },
        () => {
          this._failed = true;
          this._update();
        },
      );
    }
    this._update();
  }

  _build() {
    if (this._el) return;
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>
<div class="toolbar">
  <button class="menu" aria-label="Open sidebar" hidden>${svg(MENU_ICON)}</button>
  <div class="title"></div>
</div>
<div class="content">
  <div class="wrap">
    <div class="picker" hidden><select aria-label="Projector"></select></div>
    <div class="empty" hidden>${svg(PROJECTOR_ICON, 48)}<strong>No projector yet</strong>
      <span>Add a Valerion projector under Settings, Devices and services.</span></div>
    <div class="empty failed" role="alert" hidden><strong>The remote could not load</strong>
      <span>Reload the page. After an update, clear the browser cache.</span></div>
    <div class="slot"></div>
  </div>
</div>`;
    const root = this.shadowRoot;
    this._el = {
      menu: root.querySelector(".menu"),
      title: root.querySelector(".title"),
      picker: root.querySelector(".picker"),
      select: root.querySelector(".picker select"),
      empty: root.querySelector(".empty:not(.failed)"),
      failed: root.querySelector(".failed"),
      slot: root.querySelector(".slot"),
    };
    // Home Assistant opens or docks the sidebar on this event, as its own menu button does.
    this._el.menu.addEventListener("click", () =>
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true })),
    );
    this._el.select.addEventListener("change", () => {
      this._deviceId = this._el.select.value;
      storeChoice(this._deviceId);
      this._update();
    });
  }

  _refreshProjectors() {
    const hass = this._hass;
    if (hass.entities === this._entitiesSource && hass.devices === this._devicesSource) return;
    this._entitiesSource = hass.entities;
    this._devicesSource = hass.devices;
    const projectors = findProjectors(hass);
    if (JSON.stringify(projectors) === JSON.stringify(this._projectors)) return;
    this._projectors = projectors;
    this._el.select.innerHTML = "";
    for (const projector of projectors) {
      const option = document.createElement("option");
      option.value = projector.id;
      option.textContent = projector.name;
      this._el.select.append(option);
    }
  }

  _chosen() {
    const ids = this._projectors.map((p) => p.id);
    for (const id of [this._deviceId, readChoice()]) {
      if (id && ids.includes(id)) return id;
    }
    return ids[0] || null;
  }

  _update() {
    if (!this._el || !this._hass) return;
    const el = this._el;
    el.title.textContent = this._panel?.title || "Projector";
    el.menu.hidden = !(this._narrow || this._hass.dockedSidebar === "always_hidden");

    this._refreshProjectors();
    this._deviceId = this._chosen();
    el.picker.hidden = this._projectors.length < 2;
    if (this._deviceId) el.select.value = this._deviceId;
    el.empty.hidden = this._projectors.length > 0;
    el.failed.hidden = !(this._failed && this._deviceId);

    if (!this._deviceId) {
      this._card?.remove();
      this._card = null;
      this._cardDevice = null;
      return;
    }
    if (!this._cardReady) return;
    if (!this._card) {
      this._card = document.createElement("valerion-card");
      el.slot.append(this._card);
    }
    if (this._cardDevice !== this._deviceId) {
      this._card.setConfig({ type: "custom:valerion-card", device_id: this._deviceId });
      this._cardDevice = this._deviceId;
    }
    this._card.hass = this._hass;
  }
}

if (!customElements.get(PANEL_TYPE)) {
  customElements.define(PANEL_TYPE, ValerionPanel);
}
