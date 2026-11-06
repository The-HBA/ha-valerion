/*
 * Valerion projector card for Home Assistant (custom:valerion-card).
 *
 * Plain JavaScript custom element: no build step, no libraries. Served by the
 * integration from custom_components/valerion/www/ and registered as a
 * dashboard resource automatically.
 *
 * Layout: a header (projector, state, power), a row of five tabs and one
 * pane of fixed height, so every tab fits one phone screen. Each tab has its
 * own render function in TABS; a tab adds click handlers to ACTIONS.
 */

const DOMAIN = "valerion";
const CARD_TYPE = "valerion-card";
// The editor is loaded with the same ?v= as this file, so both update together.
const EDITOR_URL = new URL(
  `./valerion-card-editor.js${new URL(import.meta.url).search}`,
  import.meta.url,
).href;

/* ---------- icons (Material Design Icons paths) ---------- */

const ICONS = {
  power:
    "M16.56,5.44L15.11,6.89C16.84,7.94 18,9.83 18,12A6,6 0 0,1 12,18A6,6 0 0,1 6,12C6,9.83 7.16,7.94 8.88,6.88L7.44,5.44C5.36,6.88 4,9.28 4,12A8,8 0 0,0 12,20A8,8 0 0,0 20,12C20,9.28 18.64,6.88 16.56,5.44M13,3H11V13H13",
  projector:
    "M4,6H20A2,2 0 0,1 22,8V15A2,2 0 0,1 20,17V18A1,1 0 0,1 19,19H17A1,1 0 0,1 16,18V17H8V18A1,1 0 0,1 7,19H5A1,1 0 0,1 4,18V17A2,2 0 0,1 2,15V8A2,2 0 0,1 4,6M15.5,7.5A4,4 0 0,0 11.5,11.5A4,4 0 0,0 15.5,15.5A4,4 0 0,0 19.5,11.5A4,4 0 0,0 15.5,7.5M15.5,9.5A2,2 0 0,1 17.5,11.5A2,2 0 0,1 15.5,13.5A2,2 0 0,1 13.5,11.5A2,2 0 0,1 15.5,9.5M4,8V10H9V8H4M4,11V13H9V11H4M4,14V16H9V14H4Z",
  remote:
    "M12,0C8.96,0 6.21,1.23 4.22,3.22L5.63,4.63C7.26,3 9.5,2 12,2C14.5,2 16.74,3 18.36,4.64L19.77,3.23C17.79,1.23 15.04,0 12,0M7.05,6.05L8.46,7.46C9.37,6.56 10.62,6 12,6C13.38,6 14.63,6.56 15.54,7.46L16.95,6.05C15.68,4.78 13.93,4 12,4C10.07,4 8.32,4.78 7.05,6.05M12,15A2,2 0 0,1 10,13A2,2 0 0,1 12,11A2,2 0 0,1 14,13A2,2 0 0,1 12,15M15,9H9A1,1 0 0,0 8,10V22A1,1 0 0,0 9,23H15A1,1 0 0,0 16,22V10A1,1 0 0,0 15,9Z",
  picture:
    "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20V4Z",
  tune: "M5,3V12H3V14H5V21H7V14H9V12H7V3M11,3V8H9V10H11V21H13V10H15V8H13V3M17,3V14H15V16H17V21H19V16H21V14H19V3",
  info: "M11,9H13V7H11M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M11,17H13V11H11V17Z",
  cog: "M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z",
  alert:
    "M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z",
};

const icon = (name, size = 24) =>
  `<svg viewBox="0 0 24 24" width="${size}" height="${size}" aria-hidden="true"><path fill="currentColor" d="${ICONS[name]}"/></svg>`;

const esc = (text) =>
  String(text).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );

const fire = (node, type, detail) =>
  node.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));

/* ---------- finding the projector's entities ---------- */

/**
 * Collect the entities of one projector from the entity registry.
 * The media player has no translation key and is found by its domain; every
 * other entity is keyed "<domain>.<translation_key>", for example
 * "select.picture_mode" or "button.key_up".
 */
function findEntities(hass, deviceId) {
  const found = { mediaPlayer: null, byKey: {}, ids: [] };
  for (const entry of Object.values(hass.entities || {})) {
    if (entry.device_id !== deviceId || entry.platform !== DOMAIN) continue;
    found.ids.push(entry.entity_id);
    const domain = entry.entity_id.split(".", 1)[0];
    if (domain === "media_player") found.mediaPlayer = entry.entity_id;
    else if (entry.translation_key) found.byKey[`${domain}.${entry.translation_key}`] = entry.entity_id;
  }
  found.ids.sort();
  return found;
}

/** The first projector of this integration, for a new card. */
function firstDevice(hass) {
  for (const entry of Object.values(hass?.entities || {})) {
    if (entry.platform === DOMAIN && entry.device_id) return entry.device_id;
  }
  return undefined;
}

/* ---------- tabs ---------- */

/*
 * Each tab renders its pane from a context object:
 *   ctx.hass      the hass object
 *   ctx.entities  result of findEntities()
 *   ctx.state(k)  state object of entity "<domain>.<translation_key>" (or undefined)
 *   ctx.player    state object of the media player
 *   ctx.isOn      true while the projector is on
 * usableWhenOff: false dims the pane while the projector is off or in standby.
 */
const TABS = [
  { id: "remote", label: "Remote", icon: "remote", usableWhenOff: false, render: renderRemote },
  { id: "picture", label: "Picture", icon: "picture", usableWhenOff: false, render: renderPicture },
  { id: "advanced", label: "Advanced", icon: "tune", usableWhenOff: false, render: renderAdvanced },
  { id: "status", label: "Status", icon: "info", usableWhenOff: true, render: renderStatus },
  { id: "settings", label: "Settings", icon: "cog", usableWhenOff: true, render: renderSettings },
];

function renderRemote(ctx) {
  return `<div class="tab tab-remote"></div>`;
}

function renderPicture(ctx) {
  return `<div class="tab tab-picture"></div>`;
}

function renderAdvanced(ctx) {
  return `<div class="tab tab-advanced"></div>`;
}

function renderStatus(ctx) {
  return `<div class="tab tab-status"></div>`;
}

function renderSettings(ctx) {
  return `<div class="tab tab-settings"></div>`;
}

/*
 * Click handlers for elements with data-action="<name>" inside a pane:
 * ACTIONS[name](card, element, ctx). Tabs add their own entries.
 */
const ACTIONS = {};

/* ---------- styles ---------- */

const STYLES = `
:host{display:block}
ha-card{display:block;overflow:hidden;position:relative}
.vc{
  --vc-radius:var(--ha-card-border-radius,12px);
  --vc-in-radius:calc(var(--vc-radius) - 3px);
  --vc-ctl:color-mix(in srgb,var(--disabled-color,#bdbdbd) 22%,transparent);
  --vc-hover:color-mix(in srgb,var(--primary-text-color,#212121) 10%,transparent);
  --vc-press:color-mix(in srgb,var(--primary-text-color,#212121) 18%,transparent);
  --vc-sel:color-mix(in srgb,var(--primary-color,#03a9f4) 20%,transparent);
  --vc-state:var(--secondary-text-color,#727272);
  container-type:inline-size;position:relative;
  color:var(--primary-text-color,#212121);
  font-family:var(--ha-font-family-body,Roboto,system-ui,sans-serif);font-size:14px;line-height:1.4}
.vc.is-on{--vc-state:var(--primary-color,#03a9f4)}
:where(.vc) :where(button){font:inherit;color:inherit;-webkit-tap-highlight-color:transparent}
.vc svg{display:block;flex:none}
.vc-in{padding:12px;display:flex;flex-direction:column;gap:12px}

.vc-bar{position:absolute;inset:0 0 auto 0;height:2px;overflow:hidden;opacity:0;transition:opacity .15s}
.vc-bar::after{content:"";position:absolute;top:0;bottom:0;width:40%;left:-40%;
  background:linear-gradient(90deg,transparent,var(--primary-color,#03a9f4),transparent);animation:vc-shimmer 1s linear infinite}
.vc.switching .vc-bar{opacity:1}
@keyframes vc-shimmer{to{left:100%}}

.vc-head{display:flex;align-items:center;gap:12px;min-height:48px}
.vc-icon{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;flex:none;
  color:var(--vc-state);background:color-mix(in srgb,var(--vc-state) 20%,transparent)}
.vc-txt{flex:1;min-width:0}
.vc-name{font-size:16px;font-weight:500;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vc-sub{font-size:14px;color:var(--secondary-text-color,#727272);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.power{width:48px;height:48px;border:0;border-radius:var(--vc-radius);display:grid;place-items:center;cursor:pointer;flex:none;
  background-color:var(--vc-ctl);color:var(--primary-text-color,#212121)}
.is-on .power{background-color:var(--primary-color,#03a9f4);color:var(--text-primary-color,#fff)}
.power:disabled{opacity:.35;cursor:default}
.switching .power{animation:vc-pulse 1s ease-in-out infinite}
@keyframes vc-pulse{50%{opacity:.45}}

.notice{display:flex;align-items:center;gap:10px;min-height:44px;padding:0 12px;border-radius:var(--vc-radius);
  background:var(--vc-ctl);color:var(--primary-text-color,#212121)}
.notice[hidden]{display:none}
.notice svg{color:var(--secondary-text-color,#727272)}
.notice-icon{display:contents}

.pr{cursor:pointer;border:0;transition:background-color .12s}
.pr:hover{background-image:linear-gradient(var(--vc-hover),var(--vc-hover))}
.pr:active{background-image:linear-gradient(var(--vc-press),var(--vc-press))}
.pr:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:2px}

.tabs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;padding:4px;
  border-radius:var(--vc-radius);background:var(--vc-ctl)}
.tabs button{min-height:52px;border-radius:var(--vc-in-radius);background-color:transparent;padding:4px 2px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;
  font-size:12px;line-height:1.2;text-align:center;color:var(--primary-text-color,#212121)}
.tabs button svg{width:20px;height:20px;color:var(--primary-color,#03a9f4)}
.tabs button[aria-selected="true"]{background-color:var(--vc-sel);box-shadow:inset 0 0 0 2px var(--primary-color,#03a9f4);font-weight:500}
@container (min-width:600px){
  .tabs button{flex-direction:row;gap:8px;min-height:44px;font-size:14px}
}

.pane{height:var(--valerion-pane-height,520px);overflow:hidden;min-width:0;transition:opacity .2s}
.pane.dim{opacity:.35;pointer-events:none}
.tab{height:100%;display:flex;flex-direction:column;gap:12px;min-width:0}

@media (prefers-reduced-motion:reduce){
  .vc *{animation:none !important;transition:none !important}
}
`;

/* ---------- the card ---------- */

class ValerionCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = TABS[0].id;
    this._switching = false;
    this._entities = null;
    this._entitiesSource = null;
    this._watched = [];
  }

  static async getConfigElement() {
    await import(EDITOR_URL);
    return document.createElement("valerion-card-editor");
  }

  static getStubConfig(hass) {
    return { device_id: firstDevice(hass) || "" };
  }

  setConfig(config) {
    if (!config || !config.device_id) {
      throw new Error("Choose a projector (device_id).");
    }
    this._config = { ...config };
    this._entities = null;
    this._watched = [];
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config) this._update();
  }

  get hass() {
    return this._hass;
  }

  getCardSize() {
    return 14;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  /* ----- data ----- */

  _resolveEntities() {
    const hass = this._hass;
    if (!this._entities || this._entitiesSource !== hass.entities) {
      // The registry object changes for any entity in Home Assistant; keep
      // the old result when this projector's entities stayed the same.
      const found = findEntities(hass, this._config.device_id);
      if (!this._entities || JSON.stringify(found) !== JSON.stringify(this._entities)) {
        this._entities = found;
      }
      this._entitiesSource = hass.entities;
    }
    return this._entities;
  }

  /** Everything that a render depends on; identity changes mean "render again". */
  _watchList() {
    const hass = this._hass;
    const entities = this._resolveEntities();
    return [
      this._entities,
      hass.devices?.[this._config.device_id],
      ...entities.ids.map((id) => hass.states[id]),
    ];
  }

  _context() {
    const hass = this._hass;
    const entities = this._resolveEntities();
    const player = entities.mediaPlayer ? hass.states[entities.mediaPlayer] : undefined;
    return {
      hass,
      entities,
      player,
      isOn: player?.state === "on",
      state: (key) => {
        const id = entities.byKey[key];
        return id ? hass.states[id] : undefined;
      },
    };
  }

  /* ----- rendering ----- */

  _update() {
    const watched = this._watchList();
    const changed =
      watched.length !== this._watched.length || watched.some((item, i) => item !== this._watched[i]);
    if (!this.shadowRoot.firstChild) this._build();
    if (!changed) return;
    this._watched = watched;
    this._renderShell();
    this._renderPane();
  }

  _build() {
    const tabs = TABS.map(
      (tab) =>
        `<button class="pr" role="tab" id="tab-${tab.id}" data-tab="${tab.id}" aria-controls="pane" aria-selected="false" tabindex="-1">${icon(tab.icon)}<span>${esc(tab.label)}</span></button>`,
    ).join("");
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>
<ha-card>
  <div class="vc">
    <div class="vc-bar" aria-hidden="true"></div>
    <div class="vc-in">
      <div class="vc-head">
        <div class="vc-icon">${icon("projector")}</div>
        <div class="vc-txt"><div class="vc-name"></div><div class="vc-sub"></div></div>
        <button class="power pr" aria-label="Power">${icon("power", 26)}</button>
      </div>
      <div class="notice" role="status" hidden><span class="notice-icon"></span><span class="notice-text"></span></div>
      <div class="tabs" role="tablist" aria-label="Sections">${tabs}</div>
      <div class="pane" id="pane" role="tabpanel"></div>
    </div>
  </div>
</ha-card>`;
    const root = this.shadowRoot;
    this._el = {
      card: root.querySelector(".vc"),
      name: root.querySelector(".vc-name"),
      sub: root.querySelector(".vc-sub"),
      power: root.querySelector(".power"),
      notice: root.querySelector(".notice"),
      noticeIcon: root.querySelector(".notice-icon"),
      noticeText: root.querySelector(".notice-text"),
      tabs: root.querySelector(".tabs"),
      pane: root.querySelector(".pane"),
    };
    this._el.power.addEventListener("click", () => this._togglePower());
    this._el.tabs.addEventListener("click", (ev) => {
      const button = ev.target.closest("[data-tab]");
      if (button) this._selectTab(button.dataset.tab, false);
    });
    this._el.tabs.addEventListener("keydown", (ev) => this._tabKey(ev));
    this._el.pane.addEventListener("click", (ev) => {
      const el = ev.target.closest("[data-action]");
      const action = el && ACTIONS[el.dataset.action];
      if (action) action(this, el, this._context());
    });
  }

  _renderShell() {
    const ctx = this._context();
    const { hass, player } = ctx;
    const device = hass.devices?.[this._config.device_id];
    const el = this._el;
    el.name.textContent =
      device?.name_by_user || device?.name || player?.attributes.friendly_name || "Valerion projector";
    el.sub.textContent = this._stateLine(ctx);
    el.card.classList.toggle("is-on", ctx.isOn);
    el.card.classList.toggle("switching", this._switching);
    const powerUsable = player && !["unavailable", "unknown"].includes(player.state);
    el.power.disabled = !powerUsable;
    el.power.setAttribute("aria-pressed", String(ctx.isOn));
    el.power.setAttribute("aria-label", ctx.isOn ? "Turn off" : "Turn on");
    const notice = this._notice(ctx);
    el.notice.hidden = !notice;
    el.noticeText.textContent = notice || "";
    const noticeIcon = ["off", "standby"].includes(player?.state) ? "power" : "alert";
    if (el.noticeIcon.dataset.icon !== noticeIcon) {
      el.noticeIcon.dataset.icon = noticeIcon;
      el.noticeIcon.innerHTML = icon(noticeIcon, 20);
    }
    for (const button of el.tabs.querySelectorAll("[data-tab]")) {
      const selected = button.dataset.tab === this._tab;
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
    el.pane.setAttribute("aria-labelledby", `tab-${this._tab}`);
  }

  _renderPane() {
    const ctx = this._context();
    const tab = TABS.find((t) => t.id === this._tab);
    this._el.pane.classList.toggle("dim", !ctx.isOn && !tab.usableWhenOff);
    this._el.pane.innerHTML = tab.render(ctx);
  }

  _stateLine(ctx) {
    const { hass, player } = ctx;
    if (!player) return "Not found";
    const text = hass.formatEntityState
      ? hass.formatEntityState(player)
      : player.state.charAt(0).toUpperCase() + player.state.slice(1);
    const source = player.attributes.source;
    return ctx.isOn && source ? `${text} · ${source}` : text;
  }

  _notice(ctx) {
    const { player } = ctx;
    if (!player) return "Projector not found. Choose it again in the card settings.";
    switch (player.state) {
      case "on":
        return "";
      case "off":
        return "Off. Turn it on to use the controls.";
      case "standby":
        return "In standby. Turn it on to use the controls.";
      default:
        return "Not reachable right now.";
    }
  }

  /* ----- interaction ----- */

  _selectTab(id, focus) {
    if (!TABS.some((t) => t.id === id)) return;
    this._tab = id;
    this._renderShell();
    this._renderPane();
    if (focus) this.shadowRoot.getElementById(`tab-${id}`).focus();
  }

  _tabKey(ev) {
    const index = TABS.findIndex((t) => t.id === this._tab);
    const moves = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: TABS.length - 1 - index };
    if (!(ev.key in moves)) return;
    ev.preventDefault();
    const next = (index + moves[ev.key] + TABS.length) % TABS.length;
    this._selectTab(TABS[next].id, true);
  }

  async _togglePower() {
    const { hass, player, isOn } = this._context();
    if (!player || this._switching) return;
    fire(this, "haptic", "light");
    this._switching = true;
    this._renderShell();
    try {
      await hass.callService("media_player", isOn ? "turn_off" : "turn_on", {
        entity_id: player.entity_id,
      });
    } catch (err) {
      fire(this, "hass-notification", { message: err?.message || String(err) });
    } finally {
      this._switching = false;
      this._renderShell();
    }
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, ValerionCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: CARD_TYPE,
    name: "Valerion projector",
    description: "Remote, picture settings and status for a Valerion projector.",
    preview: true,
    documentationURL: "https://github.com/The-HBA/ha-valerion",
  });
}
