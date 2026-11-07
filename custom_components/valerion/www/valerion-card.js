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
 *   ctx.card      the card element, for tabs that load data and render again
 * usableWhenOff: false dims the pane while the projector is off or in standby.
 * setup (optional): setup(card, pane) runs once when the card builds its DOM,
 * for listeners that must outlive a render of the pane (held keys, sliders).
 */
const TABS = [
  {
    id: "remote",
    label: "Remote",
    icon: "remote",
    usableWhenOff: false,
    render: renderRemote,
    setup: remoteSetup,
  },
  { id: "picture", label: "Picture", icon: "picture", usableWhenOff: false, render: renderPicture, setup: pictureSetup },
  { id: "advanced", label: "Advanced", icon: "tune", usableWhenOff: false, render: renderAdvanced, setup: advancedSetup },
  { id: "status", label: "Status", icon: "info", usableWhenOff: true, render: renderStatus },
  { id: "settings", label: "Settings", icon: "cog", usableWhenOff: true, render: renderSettings },
];

function renderRemote(ctx) {
  const groups = [remoteInputs(ctx), remotePad(ctx), remoteVolume(ctx)].join("");
  return `<div class="tab tab-remote">${groups || `<p class="rm-none">This projector has no remote keys in Home Assistant.</p>`}</div>`;
}

/** Placeholder for a tab that comes in a later version: what it will hold, and where to find it now. */
function comingLater(ctx, id, title, holds) {
  const link = ctx.hass.user?.is_admin
    ? `<div class="ss-links"><button class="ss-btn pr" data-action="valerion-device-page">${icon("open", 18)}<span>Open the device page</span></button></div>`
    : "";
  return `<div class="tab tab-${id}">${ssGroup(
    title,
    `<p class="ss-quiet cl-p">${esc(holds)} This tab comes in a later version. Until then, these settings are on the projector's device page, under Configuration.</p>${link}`,
  )}</div>`;
}

function renderStatus(ctx) {
  // What the projector reports now: the signal on top, the projector below.
  return `<div class="tab tab-status ss-lay">${statusHero(ctx)}${statusRows(ctx)}<div class="ss-foot ss-wide">Updates automatically every few seconds</div></div>`;
}

function renderSettings(ctx) {
  // Setup help from valerion/card_info, then versions and links.
  const info = cardInfo(ctx);
  return `<div class="tab tab-settings ss-lay">${settingsSetup(ctx, info)}${settingsAbout(ctx, info)}</div>`;
}

/*
 * Click handlers for elements with data-action="<name>" inside a pane:
 * ACTIONS[name](card, element, ctx). Tabs add their own entries.
 */
const ACTIONS = {};

/* ---------- shared controls (Picture and Advanced tabs, sheets) ---------- */

Object.assign(ICONS, {
  lock: "M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z",
  close:
    "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
});

/** Short names of the settings, for the locked line and the scene editor. */
const SETTING_NAMES = {
  "select.picture_mode": "Picture mode",
  "number.laser_level": "Laser level",
  "select.aspect_ratio": "Aspect ratio",
  "select.gamma": "Gamma",
  "select.dynamic_tone_mapping": "Tone mapping",
  "select.color_temperature": "Color temperature",
  "select.enhanced_black_level": "Enhanced black level",
  "select.motion_enhancement": "Motion enhancement",
};

/** Options a select reports but cannot be set to: gamma follows the signal in HDR. */
const READ_ONLY_OPTIONS = { "select.gamma": new Set(["smpte2084", "hlg"]) };

/** The text Home Assistant shows for an option of a select (translated). */
function optionLabel(ctx, stateObj, option) {
  try {
    if (ctx.hass.formatEntityState) return ctx.hass.formatEntityState(stateObj, option);
  } catch (_err) {
    // An older frontend without the second argument: fall back to the key.
  }
  return option;
}

/**
 * True when the projector is on but refuses this setting now: the entity is
 * unavailable because the setting is locked for the current signal and
 * picture mode (or the projector said it is not available).
 */
function settingLocked(ctx, key) {
  const stateObj = ctx.state(key);
  return !!stateObj && ctx.isOn && stateObj.state === "unavailable";
}

/**
 * A select entity as a group with one segmented row of options.
 *   key       "select.<translation_key>"
 *   title     group title (default: SETTING_NAMES)
 *   cols      columns on a phone (default: all options in one row)
 *   colsWide  columns from 600 px wide (default: cols)
 *   only      option keys to show, in this order (default: all, read-only ones left out)
 *   right     extra HTML for the right side of the header
 *   cls       extra class names for the group
 * Returns "" when the entity is missing or locked; lockedLine() names it.
 * While the projector is off the group is drawn without a selection and
 * its buttons are disabled (the pane is dimmed too).
 */
function settingGroup(ctx, key, opts = {}) {
  const stateObj = ctx.state(key);
  if (!stateObj || settingLocked(ctx, key)) return "";
  const readOnly = READ_ONLY_OPTIONS[key] || new Set();
  const all = Array.isArray(stateObj.attributes.options) ? stateObj.attributes.options : [];
  const options = opts.only ? opts.only.filter((o) => all.includes(o)) : all.filter((o) => !readOnly.has(o));
  if (!options.length) return "";
  const current = ctx.isOn ? stateObj.state : undefined;
  const id = `vc-${key.replace(".", "-")}`;
  const usable = ctx.isOn && stateObj.state !== "unavailable";
  const buttons = options
    .map((option) => {
      const selected = option === current;
      return `<button class="pr vc-opt${selected ? " sel" : ""}" data-action="setting-select" data-entity="${esc(stateObj.entity_id)}" data-option="${esc(option)}" aria-pressed="${selected}"${usable ? "" : " disabled"}>${esc(optionLabel(ctx, stateObj, option))}</button>`;
    })
    .join("");
  const cols = opts.cols || options.length;
  const wide = opts.colsWide || cols;
  const title = opts.title || SETTING_NAMES[key] || key;
  return `<section class="vc-grp${opts.cls ? ` ${opts.cls}` : ""}" aria-labelledby="${id}"><div class="vc-h"><span class="vc-t" id="${id}">${esc(title)}</span>${opts.right || ""}</div>
<div class="vc-seg" role="group" aria-labelledby="${id}" style="--n:${cols};--nw:${wide}">${buttons}</div></section>`;
}

/** The current signal for headers and the locked line: "HDR10", or "" when unknown. */
function signalLabel(ctx) {
  const stateObj = ctx.state("sensor.hdr_format");
  if (!ctx.isOn || !ssKnown(stateObj)) return "";
  return ssText(ctx, stateObj);
}

/**
 * One grey line naming the settings of `keys` that are locked now, for
 * example "Locked for HDR10 in HDR Theater: Gamma, Tone mapping".
 * Returns "" when none is locked.
 */
function lockedLine(ctx, keys) {
  const names = keys.filter((key) => settingLocked(ctx, key)).map((key) => SETTING_NAMES[key] || key);
  if (!names.length) return "";
  const signal = signalLabel(ctx);
  const mode = ctx.state("select.picture_mode");
  const inMode = ssKnown(mode) ? ` in ${mode.state}` : "";
  const where = signal ? ` for ${signal}${inMode}` : inMode;
  return `<div class="vc-lock" role="note">${icon("lock", 18)}<span>Locked${esc(where)}: ${esc(names.join(", "))}</span></div>`;
}

ACTIONS["setting-select"] = (card, el, ctx) => {
  if (!ctx.isOn || el.disabled || el.getAttribute("aria-pressed") === "true") return;
  fire(card, "haptic", "selection");
  for (const option of el.parentElement.children) {
    option.classList.toggle("sel", option === el);
    option.setAttribute("aria-pressed", String(option === el));
  }
  remoteCall(card, "select", "select_option", {
    entity_id: el.dataset.entity,
    option: el.dataset.option,
  }).then((ok) => ok || card._renderAll());
};

/*
 * Sheets: a panel that slides up from the bottom on a phone and is a
 * centred dialog on a wider screen. It is a native <dialog> opened with
 * showModal(), so it sits above the dashboard whatever the card is inside.
 *   card.openSheet({ id, title, render(ctx) -> HTML, onClose(card) })
 *   card.closeSheet()        closes it and calls onClose
 * The body is rendered again whenever the projector's entities change;
 * render may return null to keep the body as it is (fields being edited).
 * Elements with data-action use ACTIONS, as in the pane; data-hold keys
 * repeat while held, as on the Remote tab. data-action="sheet-close"
 * closes the sheet (also Escape, the close button and a tap outside).
 */
ACTIONS["sheet-close"] = (card) => card.closeSheet();

/* ---------- Picture tab ---------- */

Object.assign(ICONS, {
  pencil:
    "M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z",
  "pc-plus": "M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z",
});

/** The settings a scene can hold, in the order the backend sends them (scenes.py). */
const PC_SCENE_KEYS = [
  "picture_mode",
  "laser_level",
  "aspect_ratio",
  "gamma",
  "dynamic_tone_mapping",
  "color_temperature",
  "enhanced_black_level",
  "motion_enhancement",
];
/** Settings of this tab, for the locked line. */
const PC_LOCKABLE = ["select.picture_mode", "select.color_temperature", "select.aspect_ratio"];
/** Why applying a scene skipped a setting (scenes.py SKIP_*), in plain words. */
const PC_SKIP_REASONS = {
  locked: "locked for this signal",
  not_settable: "cannot be set",
  not_offered: "not available for this signal",
  refused: "refused by the projector",
  picture_mode_not_set: "picture mode not set",
};
const PC_LASER_MAX = 10;

const pcEntityKey = (key) => `${key === "laser_level" ? "number" : "select"}.${key}`;
const pcSettingName = (key) => SETTING_NAMES[pcEntityKey(key)] || key;
/** "HDR Theater" shows as "Theater": the badge already names the format. */
const pcShortMode = (mode) => mode.replace(/^(HDR10\+|HDR|Dolby Vision)\s+/, "") || mode;
const pcOptions = (stateObj) => (Array.isArray(stateObj?.attributes.options) ? stateObj.attributes.options : []);

function renderPicture(ctx) {
  const parts = [
    pcMode(ctx),
    settingGroup(ctx, "select.color_temperature", { cols: 4, cls: "pc-ct" }),
    pcScenesGroup(ctx),
    pcAspect(ctx),
    lockedLine(ctx, PC_LOCKABLE),
  ];
  return `<div class="tab tab-picture">${parts.join("")}</div>`;
}

/** True while the projector is on and nothing comes in on the input. */
function pcNoSignal(ctx) {
  if (!ctx.isOn) return false;
  const hdr = ctx.state("sensor.hdr_format");
  if (hdr?.state === "no_signal") return true;
  const video = ctx.state("sensor.video_signal");
  return !!video && !ssKnown(video) && !ssKnown(hdr);
}

/**
 * A segmented row of options of one select, as settingGroup draws it.
 * `label(option)` is the text shown; the full option is sent.
 */
function pcSeg(ctx, stateObj, options, { labelledBy, label, cols, colsWide, action = "setting-select" }) {
  const current = ctx.isOn ? stateObj.state : undefined;
  const usable = ctx.isOn && stateObj.state !== "unavailable";
  const buttons = options
    .map((option) => {
      const selected = option === current;
      const full = optionLabel(ctx, stateObj, option);
      const shown = label ? label(full) : full;
      const named = shown !== full ? ` aria-label="${esc(full)}" title="${esc(full)}"` : "";
      return `<button class="pr vc-opt${selected ? " sel" : ""}" data-action="${action}" data-entity="${esc(stateObj.entity_id)}" data-option="${esc(option)}" aria-pressed="${selected}"${named}${usable ? "" : " disabled"}>${esc(shown)}</button>`;
    })
    .join("");
  return `<div class="vc-seg" role="group" aria-labelledby="${labelledBy}" style="--n:${cols};--nw:${colsWide || cols}">${buttons}</div>`;
}

function pcMode(ctx) {
  const key = "select.picture_mode";
  const stateObj = ctx.state(key);
  const options = pcOptions(stateObj);
  if (!stateObj || settingLocked(ctx, key) || !options.length) return "";
  const noSignal = pcNoSignal(ctx);
  const signal = noSignal ? "" : signalLabel(ctx);
  const source = ctx.player?.attributes.source;
  const on = source === "Home" ? " on the home screen" : source ? ` on ${source}` : "";
  let sub = ["Each signal format keeps its own picture mode."];
  if (noSignal) sub = [`No signal${on}.`, "These are the modes it offers now."];
  else if (signal) sub = [`For ${signal}${on}.`, "Each format keeps its own mode."];
  const badge = signal ? `<span class="pc-badge">${esc(signal)}</span>` : "";
  const cols = Math.min(4, options.length);
  const seg = pcSeg(ctx, stateObj, options, { labelledBy: "pc-mode-t", label: pcShortMode, cols });
  return `<section class="vc-grp pc-mode" aria-labelledby="pc-mode-t"><div class="vc-h"><span class="vc-t" id="pc-mode-t">${esc(SETTING_NAMES[key])}</span>${badge}</div>
<div class="pc-sub">${sub.map((s) => `<span>${esc(s)}</span>`).join("")}</div>${seg}</section>`;
}

function pcAspect(ctx) {
  const key = "select.aspect_ratio";
  const stateObj = ctx.state(key);
  const options = pcOptions(stateObj);
  if (!stateObj || settingLocked(ctx, key) || !options.length) return "";
  if (pcNoSignal(ctx)) {
    return `<div class="pc-note pc-ar" role="note">${icon("info", 18)}<span>Aspect ratio needs an HDMI signal.</span></div>`;
  }
  const normal = options.filter((o) => !o.startsWith("anamorphic_"));
  const lens = options.filter((o) => o.startsWith("anamorphic_"));
  const value = ctx.isOn && options.includes(stateObj.state) ? optionLabel(ctx, stateObj, stateObj.state) : "";
  const opts = { action: "picture-aspect" };
  const rows = [];
  if (normal.length) {
    rows.push(pcSeg(ctx, stateObj, normal, { ...opts, labelledBy: "pc-ar-t", cols: normal.length }));
  }
  if (lens.length) {
    const short = (text) => text.replace(/^Anamorphic\s+/i, "") || text;
    const seg = pcSeg(ctx, stateObj, lens, { ...opts, labelledBy: "pc-ana-t", label: short, cols: lens.length });
    rows.push(`<div class="pc-ana"><span class="pc-lbl" id="pc-ana-t">Anamorphic lens</span>${seg}</div>`);
  }
  return `<section class="vc-grp pc-ar" aria-labelledby="pc-ar-t"><div class="vc-h"><span class="vc-t" id="pc-ar-t">${esc(SETTING_NAMES[key])}</span>${value ? `<span class="vc-v">${esc(value)}</span>` : ""}</div>${rows.join("")}</section>`;
}

/** Aspect ratios sit in two rows: one selection across both. */
ACTIONS["picture-aspect"] = (card, el, ctx) => {
  if (!ctx.isOn || el.disabled || el.getAttribute("aria-pressed") === "true") return;
  for (const other of el.closest(".pc-ar").querySelectorAll(".vc-opt.sel")) {
    other.classList.remove("sel");
    other.setAttribute("aria-pressed", "false");
  }
  ACTIONS["setting-select"](card, el, ctx);
};

/* ----- scenes ----- */

/** The scene list of this projector, cached on the card: { list, failed, pending }. */
function pcSceneState(card) {
  const deviceId = card._config.device_id;
  let st = card._pcScenes;
  if (!st || st.deviceId !== deviceId) {
    st = card._pcScenes = { deviceId, list: null, failed: false, pending: false, seq: 0 };
  }
  return st;
}

/** Ask for the scene list; the pane (and an open editor) render again when it arrives. */
function pcLoadScenes(card) {
  const st = pcSceneState(card);
  const seq = ++st.seq;
  st.pending = true;
  const current = () => card._pcScenes === st && st.seq === seq;
  return Promise.resolve()
    .then(() => card.hass.callWS({ type: `${DOMAIN}/scenes/list`, device_id: st.deviceId }))
    .then(
      (data) => {
        if (!current()) return;
        st.list = Array.isArray(data?.scenes) ? data.scenes : [];
        st.failed = false;
      },
      () => {
        if (current()) st.failed = true;
      },
    )
    .then(() => {
      if (!current()) return;
      st.pending = false;
      if (card._tab === "picture") card._renderPane();
    });
}

/** The scene list for a render; loads it when the tab opens (again on every opening). */
function pcScenes(ctx) {
  const { card } = ctx;
  const st = pcSceneState(card);
  const opening = !card._el?.pane.querySelector(".tab-picture");
  if ((opening || (!st.list && !st.failed)) && !st.pending) pcLoadScenes(card);
  return st;
}

const pcFindScene = (card, id) => (card._pcScenes?.list || []).find((scene) => scene.id === id);

function pcScenesGroup(ctx) {
  const st = pcScenes(ctx);
  const admin = !!ctx.hass.user?.is_admin;
  const list = st.list || [];
  const head = (right = "") =>
    `<div class="vc-h"><span class="vc-t" id="pc-sc-t">Scenes</span>${right}</div>`;
  if (!admin && !list.length) {
    if (st.failed) return "";
    const body = st.list
      ? `<p class="pc-quiet">No scenes yet. An admin can create them here.</p>`
      : `<div class="pc-chips"></div>`;
    return `<section class="vc-grp pc-sc" aria-labelledby="pc-sc-t">${head()}${body}</section>`;
  }
  const off = ctx.isOn ? "" : " disabled";
  const chips = list.map(
    (scene) =>
      `<button class="pr pc-chip" data-action="scene-apply" data-scene="${esc(scene.id)}" title="${esc(scene.name)}"${off}><span>${esc(scene.name)}</span></button>`,
  );
  if (admin) {
    chips.push(
      `<button class="pr pc-chip pc-add" data-action="scene-new" aria-label="New scene">${icon("pc-plus", 18)}<span>New</span></button>`,
    );
  }
  const edit =
    admin && list.length
      ? `<button class="pr pc-tbtn" data-action="scene-edit">${icon("pencil", 18)}<span>Edit</span></button>`
      : "";
  return `<section class="vc-grp pc-sc" aria-labelledby="pc-sc-t">${head(edit)}<div class="pc-chips" role="group" aria-labelledby="pc-sc-t">${chips.join("")}</div></section>`;
}

/** The toast after applying a scene: what was skipped, in plain words. */
function pcApplyMessage(ctx, scene, result) {
  const name = scene.name;
  const skipped = Array.isArray(result?.skipped) ? result.skipped : [];
  const applied = Array.isArray(result?.applied) ? result.applied : [];
  const mode = skipped.find((s) => s.setting === "picture_mode");
  if (mode) {
    // The other settings belong to the scene's mode, so nothing else was sent.
    const wanted = scene.settings?.picture_mode || "Its picture mode";
    const signal = signalLabel(ctx) || "this signal";
    const why = {
      not_offered: `${wanted} is not available for ${signal}`,
      locked: `the picture mode is locked for ${signal}`,
      refused: `the projector refused ${wanted}`,
    };
    return `${name} was not applied: ${why[mode.reason] || `${wanted} could not be set`}.`;
  }
  if (!skipped.length) return `${name} applied.`;
  const names = skipped
    .map((s) => `${pcSettingName(s.setting)} (${PC_SKIP_REASONS[s.reason] || s.reason})`)
    .join(", ");
  return applied.length ? `${name} applied. Skipped: ${names}.` : `${name} was not applied. Skipped: ${names}.`;
}

ACTIONS["scene-apply"] = async (card, el, ctx) => {
  const scene = pcFindScene(card, el.dataset.scene);
  if (!ctx.isOn || el.disabled || !scene) return;
  fire(card, "haptic", "light");
  let message;
  try {
    const result = await ctx.hass.callWS({
      type: `${DOMAIN}/scenes/apply`,
      device_id: card._config.device_id,
      scene_id: scene.id,
    });
    message = pcApplyMessage(card._context(), scene, result);
  } catch (err) {
    message = err?.message || `${scene.name} could not be applied.`;
  }
  fire(card, "hass-notification", { message });
};

/* ----- scene editor (a sheet) ----- */

/*
 * The editor is drawn from a draft on the card (card._pcEdit), which the
 * fields update as they change. When the projector's entities change, the
 * sheet asks for its body again; while the draft would draw the same
 * fields, the body is kept as it is, so typing, focus and an open select
 * are not disturbed. If it must be drawn again (the picture modes changed),
 * the focus and caret go back to the same field.
 */

/** The current value of a setting as a scene option ("" when unknown or locked). */
function pcCurrent(ctx, key) {
  const stateObj = ctx.state(pcEntityKey(key));
  if (!ssKnown(stateObj)) return "";
  if (key === "laser_level") {
    const level = Math.round(Number(stateObj.state));
    return Number.isFinite(level) && level >= 0 && level <= PC_LASER_MAX ? String(level) : "";
  }
  const readOnly = READ_ONLY_OPTIONS[pcEntityKey(key)];
  if (readOnly?.has(stateObj.state)) return "";
  return key === "picture_mode" || pcOptions(stateObj).includes(stateObj.state) ? stateObj.state : "";
}

/** A draft of `scene`, or of a new scene (from the current values while the projector is on). */
function pcDraft(ctx, scene) {
  const settings = {};
  for (const key of PC_SCENE_KEYS) {
    if (scene) settings[key] = key in (scene.settings || {}) ? String(scene.settings[key]) : "";
    else settings[key] = ctx.isOn ? pcCurrent(ctx, key) : "";
  }
  return {
    id: scene?.id ?? null,
    original: scene?.name ?? "",
    name: scene?.name ?? "",
    settings,
    error: "",
    confirm: false,
    busy: false,
    html: null,
  };
}

/** The values a setting row offers: [value, label]. */
function pcChoices(ctx, key, value) {
  const stateObj = ctx.state(pcEntityKey(key));
  let values;
  if (key === "laser_level") {
    values = Array.from({ length: PC_LASER_MAX + 1 }, (_, i) => String(i));
  } else {
    const readOnly = READ_ONLY_OPTIONS[pcEntityKey(key)] || new Set();
    values = pcOptions(stateObj).filter((o) => !readOnly.has(o));
  }
  if (value && !values.includes(value)) values = [...values, value];
  const label = (v) => (stateObj && key !== "laser_level" && key !== "picture_mode" ? optionLabel(ctx, stateObj, v) : v);
  return values.map((v) => [v, label(v)]);
}

function pcEditorHtml(ctx, draft) {
  const list = ctx.card._pcScenes?.list || [];
  const picker = list.length
    ? `<div class="pc-chips pc-pick" role="group" aria-label="Scene to edit">${list
        .map((scene, i) => {
          const on = scene.id === draft.id;
          return `<button class="pr pc-chip" id="pc-pick-${i}" data-action="scene-pick" data-scene="${esc(scene.id)}" aria-pressed="${on}"><span>${esc(scene.name)}</span></button>`;
        })
        .join("")}<button class="pr pc-chip pc-add" id="pc-pick-new" data-action="scene-pick" data-scene="" aria-pressed="${!draft.id}" aria-label="New scene">${icon("pc-plus", 18)}<span>New</span></button></div>`
    : "";
  const rows = PC_SCENE_KEYS.map((key) => {
    const value = draft.settings[key];
    if (!ctx.state(pcEntityKey(key)) && !value) return "";
    const options = pcChoices(ctx, key, value)
      .map(([v, label]) => `<option value="${esc(v)}"${v === value ? " selected" : ""}>${esc(label)}</option>`)
      .join("");
    return `<div class="pc-row"><label class="pc-rl" for="pc-f-${key}">${esc(pcSettingName(key))}</label><select class="pc-sel${value ? " set" : ""}" id="pc-f-${key}" data-pc-field="${key}"><option value=""${value ? "" : " selected"}>Don't change</option>${options}</select></div>`;
  }).join("");
  const busy = draft.busy ? " disabled" : "";
  const del = draft.id
    ? `<button class="pr pc-tbtn pc-danger${draft.confirm ? " pc-confirm" : ""}" id="pc-del" data-action="scene-delete"${busy}>${esc(draft.confirm ? `Delete ${draft.original}?` : "Delete")}</button>`
    : "";
  const error = draft.error ? `<p class="pc-err" role="alert">${esc(draft.error)}</p>` : "";
  return `<p class="pc-hint">Pick only what this scene should change.</p>${picker}
<input class="pc-name" id="pc-f-name" data-pc-field="name" value="${esc(draft.name)}" placeholder="Scene name" aria-label="Scene name" maxlength="100" autocomplete="off" enterkeyhint="done">
<div class="pc-rows">${rows}</div>${error}
<div class="pc-foot">${del}<span class="pc-gap"></span><button class="pr pc-tbtn" id="pc-cancel" data-action="sheet-close">Cancel</button><button class="pr pc-fbtn" id="pc-save" data-action="scene-save"${busy}>Save</button></div>`;
}

/** After the body is drawn again, put the focus, caret and scroll position back. */
function pcKeepFocus(card) {
  const body = card._el.sheetBody;
  const active = card.shadowRoot.activeElement;
  const id = body.contains(active) ? active.id : "";
  const range = active?.tagName === "INPUT" ? [active.selectionStart, active.selectionEnd] : null;
  const scroll = body.scrollTop;
  Promise.resolve().then(() => {
    body.scrollTop = scroll;
    const el = id && body.querySelector(`#${id}`);
    if (!el) return;
    el.focus({ preventScroll: true });
    if (range && el.setSelectionRange) el.setSelectionRange(range[0], range[1]);
  });
}

function pcEditorRender(ctx) {
  const { card } = ctx;
  const draft = card._pcEdit;
  if (!draft) return "";
  const html = pcEditorHtml(ctx, draft);
  // Nothing to change: keep the fields as they are (see the sheet API).
  if (html === draft.html && card._el.sheetBody.firstChild) return null;
  draft.html = html;
  pcKeepFocus(card);
  return html;
}

function pcOpenEditor(card, scene) {
  card._pcEdit = pcDraft(card._context(), scene || null);
  card.openSheet({
    id: "scene-editor",
    title: (ctx) => (ctx.card._pcEdit?.id ? "Edit scene" : "New scene"),
    render: pcEditorRender,
    onClose: (c) => {
      c._pcEdit = null;
    },
  });
}

function pcEditError(card, draft, message) {
  draft.error = message;
  draft.busy = false;
  if (card._pcEdit === draft) card._renderSheet();
}

Object.assign(ACTIONS, {
  "scene-edit": (card) => {
    const first = card._pcScenes?.list?.[0];
    if (first) pcOpenEditor(card, first);
  },
  "scene-new": (card) => pcOpenEditor(card, null),
  "scene-pick": (card, el, ctx) => {
    const scene = pcFindScene(card, el.dataset.scene);
    if (el.getAttribute("aria-pressed") === "true") return;
    card._pcEdit = pcDraft(ctx, scene || null);
    card._renderSheet();
  },
  "scene-save": async (card, _el, ctx) => {
    const draft = card._pcEdit;
    if (!draft || draft.busy) return;
    const name = draft.name.trim();
    const settings = {};
    for (const key of PC_SCENE_KEYS) {
      const value = draft.settings[key];
      if (value !== "") settings[key] = key === "laser_level" ? Number(value) : value;
    }
    if (!name) return pcEditError(card, draft, "Enter a name for the scene.");
    if (!Object.keys(settings).length) return pcEditError(card, draft, "Pick at least one setting to change.");
    draft.busy = true;
    draft.error = "";
    card._renderSheet();
    const message = { type: `${DOMAIN}/scenes/save`, device_id: card._config.device_id, name, settings };
    if (draft.id) message.scene_id = draft.id;
    let reply;
    try {
      reply = await ctx.hass.callWS(message);
    } catch (err) {
      return pcEditError(card, draft, err?.message || "The scene could not be saved.");
    }
    await pcLoadScenes(card);
    if (card._pcEdit === draft) card.closeSheet();
    fire(card, "hass-notification", { message: `${reply?.scene?.name || name} saved.` });
  },
  "scene-delete": async (card, _el, ctx) => {
    const draft = card._pcEdit;
    if (!draft?.id || draft.busy) return;
    if (!draft.confirm) {
      draft.confirm = true;
      card._renderSheet();
      return;
    }
    draft.busy = true;
    card._renderSheet();
    try {
      await ctx.hass.callWS({ type: `${DOMAIN}/scenes/delete`, device_id: card._config.device_id, scene_id: draft.id });
    } catch (err) {
      draft.confirm = false;
      return pcEditError(card, draft, err?.message || "The scene could not be deleted.");
    }
    await pcLoadScenes(card);
    if (card._pcEdit === draft) card.closeSheet();
    fire(card, "hass-notification", { message: `${draft.original} deleted.` });
  },
});

/** Runs once when the card builds its DOM (see TABS): the editor's fields update its draft. */
function pictureSetup(card, _pane) {
  const body = card._el.sheetBody;
  const onField = (ev) => {
    const draft = card._pcEdit;
    const el = ev.target;
    const field = el?.dataset?.pcField;
    if (!draft || card.sheetId !== "scene-editor" || !field) return;
    if (field === "name") draft.name = el.value;
    else {
      draft.settings[field] = el.value;
      el.classList.toggle("set", el.value !== "");
    }
    // The fields show the draft now; an entity update need not draw them again.
    draft.html = pcEditorHtml(card._context(), draft);
  };
  body.addEventListener("input", onField);
  body.addEventListener("change", onField);
  body.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" || ev.isComposing || ev.target?.dataset?.pcField !== "name" || !card._pcEdit) return;
    ev.preventDefault();
    ACTIONS["scene-save"](card, ev.target, card._context());
  });
}

/* ---------- end of Picture tab ---------- */

/* ---------- Status and Settings tabs ---------- */

Object.assign(ICONS, {
  link: "M3.9,12C3.9,10.29 5.29,8.9 7,8.9H11V7H7A5,5 0 0,0 2,12A5,5 0 0,0 7,17H11V15.1H7C5.29,15.1 3.9,13.71 3.9,12M8,13H16V11H8V13M17,7H13V8.9H17C18.71,8.9 20.1,10.29 20.1,12C20.1,13.71 18.71,15.1 17,15.1H13V17H17A5,5 0 0,0 22,12A5,5 0 0,0 17,7Z",
  check:
    "M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2M12 20C7.59 20 4 16.41 4 12S7.59 4 12 4 20 7.59 20 12 16.41 20 12 20M16.59 7.58L10 14.17L7.41 11.59L6 13L10 17L18 9L16.59 7.58Z",
  laser:
    "M12,18V6A6,6 0 0,1 18,12A6,6 0 0,1 12,18M20,15.31L23.31,12L20,8.69V4H15.31L12,0.69L8.69,4H4V8.69L0.69,12L4,15.31V20H8.69L12,23.31L15.31,20H20V15.31Z",
  fan: "M12,11A1,1 0 0,0 11,12A1,1 0 0,0 12,13A1,1 0 0,0 13,12A1,1 0 0,0 12,11M12.5,2C17,2 17.11,5.57 14.75,6.75C13.76,7.24 13.32,8.29 13.13,9.22C13.61,9.42 14.03,9.73 14.35,10.13C18.05,8.13 22.03,8.92 22.03,12.5C22.03,17 18.46,17.1 17.28,14.73C16.78,13.74 15.72,13.3 14.79,13.11C14.59,13.59 14.28,14 13.88,14.34C15.87,18.03 15.08,22 11.5,22C7,22 6.91,18.42 9.27,17.24C10.25,16.75 10.69,15.71 10.89,14.79C10.4,14.59 9.97,14.27 9.65,13.87C5.96,15.85 2,15.07 2,11.5C2,7 5.56,6.89 6.74,9.26C7.24,10.25 8.29,10.68 9.22,10.87C9.41,10.39 9.73,9.97 10.14,9.65C8.15,5.96 8.94,2 12.5,2Z",
  thermo: "M15 13V5A3 3 0 0 0 9 5V13A5 5 0 1 0 15 13M12 4A1 1 0 0 1 13 5V8H11V5A1 1 0 0 1 12 4Z",
  history:
    "M13,3A9,9 0 0,0 4,12H1L4.89,15.89L4.96,16.03L9,12H6A7,7 0 0,1 13,5A7,7 0 0,1 20,12A7,7 0 0,1 13,19C11.07,19 9.32,18.21 8.06,16.94L6.64,18.36C8.27,20 10.5,21 13,21A9,9 0 0,0 22,12A9,9 0 0,0 13,3Z",
  open: "M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z",
  help: "M11,18H13V16H11V18M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,6A4,4 0 0,0 8,10H10A2,2 0 0,1 12,8A2,2 0 0,1 14,10C14,12 11,11.75 11,15H13C13,12.75 16,12.5 16,10A4,4 0 0,0 12,6Z",
});

const DOCS_URL = "https://github.com/The-HBA/ha-valerion";
const ISSUES_URL = "https://github.com/The-HBA/ha-valerion/issues";
/** Where the MAC addresses and instant updates are set. */
const OPTIONS_HINT = "the gear button on the integration's entry";

const ssKnown = (stateObj) => !!stateObj && !["unknown", "unavailable"].includes(stateObj.state);
const ssText = (ctx, stateObj) =>
  ctx.hass.formatEntityState ? ctx.hass.formatEntityState(stateObj) : stateObj.state;
const ssRow = (iconName, label, value, warn = false) =>
  `<div class="ss-row">${icon(iconName, 22)}<span class="ss-n">${esc(label)}</span><span class="ss-v${warn ? " ss-bad" : ""}">${esc(value)}</span></div>`;
const ssGroup = (title, body, right = "") =>
  `<section class="ss-grp"><div class="ss-h"><span>${esc(title)}</span>${right}</div>${body}</section>`;

/** Fan and temperature sensors share one translation key, one sensor per slot. */
function ssSlots(ctx, translationKey) {
  const { hass, entities } = ctx;
  return entities.ids
    .filter((id) => id.startsWith("sensor.") && hass.entities[id]?.translation_key === translationKey)
    .map((id) => hass.states[id])
    .filter(Boolean);
}

/** "1770, 1710 rpm" for the slots that report a value. */
function ssSlotValue(ctx, slots) {
  const known = slots.filter(ssKnown);
  if (!known.length) return ssText(ctx, slots[0]);
  const unit = known[0].attributes.unit_of_measurement;
  const numbers = known.map((s) => s.state);
  return unit ? `${numbers.join(", ")} ${unit}` : numbers.join(", ");
}

/** "3840×2160p 24 Hz 3D" as the video signal sensor reports it, split up. */
function ssTiming(text) {
  const match = /^(\d+)×(\d+)([pi])\s+([\d.]+)\s*Hz(\s+3D)?/.exec(text || "");
  if (!match) return null;
  const [, width, height, scan] = match;
  let size = `${height}${scan}`;
  if (Number(width) >= 3800) size = "4K";
  return { size: match[5] ? `${size} 3D` : size };
}

function statusHero(ctx) {
  const { player, isOn } = ctx;
  const hero = (kicker, big, sub, chips = []) =>
    `<section class="ss-grp ss-hero"><span class="ss-kick">${esc(kicker)}</span><span class="ss-big">${esc(big)}</span><span class="ss-sub">${esc(sub)}</span>${
      chips.length ? `<div class="ss-chips">${chips.map((c) => `<span class="ss-chip">${esc(c)}</span>`).join("")}</div>` : ""
    }</section>`;
  if (!isOn) {
    const why = { off: "The projector is off.", standby: "The projector is in standby." };
    return hero("Now playing", "Nothing", why[player?.state] || "The projector is not reachable.");
  }
  const source = player.attributes.source;
  const kicker = source ? `Now playing on ${source}` : "Now playing";
  const video = ctx.state("sensor.video_signal");
  const hdr = ctx.state("sensor.hdr_format");
  const hasSignal = ssKnown(video) || (ssKnown(hdr) && hdr.state !== "no_signal");
  if (!hasSignal) {
    return hero(kicker, "No signal", source ? `Nothing comes in on ${source}.` : "Nothing comes in.");
  }
  const timing = ssKnown(video) ? ssTiming(video.state) : null;
  const big = [timing ? timing.size : ssKnown(video) ? video.state : "", ssKnown(hdr) ? ssText(ctx, hdr) : ""]
    .filter(Boolean)
    .join(" ");
  const mode = ctx.state("select.picture_mode");
  const sub = [timing && video.state, ssKnown(mode) && mode.state].filter(Boolean).join(" · ");
  const chips = ["audio_format", "color_depth", "color_format", "color_primaries"]
    .map((key) => ctx.state(`sensor.${key}`))
    .filter(ssKnown)
    .map((s) => ssText(ctx, s));
  return hero(kicker, big, sub || " ", chips);
}

function statusRows(ctx) {
  const { player } = ctx;
  const rows = [];
  if (player) rows.push(ssRow("power", "Power", ssText(ctx, player)));
  const link = ctx.state("sensor.link_status");
  if (link) rows.push(ssRow("link", "AWOL Link", ssText(ctx, link)));
  const led = ctx.state("sensor.led_status");
  if (led) {
    const problem = ssKnown(led) && led.state !== "normal";
    rows.push(ssRow(problem ? "alert" : "check", "LED status", ssText(ctx, led), problem));
  }
  const laser = ctx.state("number.laser_level");
  if (laser) {
    const max = laser.attributes.max;
    rows.push(ssRow("laser", "Laser level", ssKnown(laser) && max ? `${Number(laser.state)} of ${max}` : ssText(ctx, laser)));
  }
  const fans = ssSlots(ctx, "fan_speed");
  if (fans.length) rows.push(ssRow("fan", fans.length > 1 ? "Fans" : "Fan", ssSlotValue(ctx, fans)));
  const temps = ssSlots(ctx, "temperature");
  if (temps.length) rows.push(ssRow("thermo", temps.length > 1 ? "Temperatures" : "Temperature", ssSlotValue(ctx, temps)));
  // Only exists with instant updates (Status Notification) switched on.
  const last = ctx.state("sensor.last_status_notification");
  if (last) rows.push(ssRow("history", "Last instant update", ssKnown(last) ? ssTime(ctx, last.state) : "None yet"));
  return ssGroup("Projector", `<div class="ss-rows">${rows.join("")}</div>`);
}

/** A time as "21:03" today, else with the date; it never goes stale like "2 min ago". */
function ssTime(ctx, iso) {
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return iso;
  const lang = ctx.hass.locale?.language || undefined;
  const time = when.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
  if (when.toDateString() === new Date().toDateString()) return time;
  return `${when.toLocaleDateString(lang, { day: "numeric", month: "short" })}, ${time}`;
}

/**
 * The card_info reply of this projector, cached on the card. It is asked
 * for once when the Settings tab opens (again on every later opening, to
 * catch an entry reload) and the pane renders again when it arrives.
 * A failure only shows a quiet note.
 */
function cardInfo(ctx) {
  const { card, hass } = ctx;
  const deviceId = card._config.device_id;
  let info = card._cardInfo;
  const fresh = !info || info.deviceId !== deviceId;
  if (fresh) info = card._cardInfo = { deviceId, data: null, failed: false, pending: false };
  // The pane still shows the previous tab while this one renders.
  const opening = !card._el?.pane.querySelector(".tab-settings");
  if ((fresh || opening) && !info.pending) {
    info.pending = true;
    Promise.resolve()
      .then(() => hass.callWS({ type: `${DOMAIN}/card_info`, device_id: deviceId }))
      .then(
        (data) => {
          info.data = data;
          info.failed = false;
        },
        () => {
          info.failed = true;
        },
      )
      .then(() => {
        info.pending = false;
        if (card._cardInfo === info && card._tab === "settings") card._renderPane();
      });
  }
  return info;
}

const MENU_LABELS = { lens_shift: "lens shift", zoom: "zoom", focus: "focus" };

/** One line per setup hint: [kind, text, what to do]; kind is ok, warn or info. */
function setupHints(setup) {
  const hints = [];
  hints.push(
    setup.wake_on_lan
      ? ["ok", "Wake-on-LAN is set up.", ""]
      : ["warn", "No MAC address set.", `It cannot wake from deep standby. Add it with ${OPTIONS_HINT}.`],
  );
  if (!setup.status_notifications) {
    hints.push(["info", "Instant updates are off.", `Turn them on with ${OPTIONS_HINT}.`]);
  } else if (!setup.notifications_listening) {
    hints.push(["warn", "Instant updates cannot start.", "Port 4352 is in use. See Settings, Repairs."]);
  } else {
    hints.push(["ok", "Instant updates are on.", ""]);
  }
  hints.push(
    setup.security_code
      ? ["ok", "Security code is set.", ""]
      : ["info", "No security code set.", "Only needed when AWOL Link asks for one."],
  );
  const menus = (setup.unsupported_menus || []).map((m) => MENU_LABELS[m] || m);
  if (menus.length) {
    const names = menus.length > 1 ? `${menus.slice(0, -1).join(", ")} or ${menus.at(-1)}` : menus[0];
    hints.push(["info", `No ${names} menu on this model.`, "Wrong? Use Forget learned locks on the device page."]);
  }
  return hints;
}

function settingsSetup(ctx, info) {
  const right = ctx.hass.user?.is_admin
    ? `<button class="ss-btn pr" data-action="valerion-device-page">${icon("open", 18)}<span>Device page</span></button>`
    : "";
  let body;
  if (info.data?.setup) {
    const iconFor = { ok: "check", warn: "alert", info: "info" };
    body = setupHints(info.data.setup)
      .map(
        ([kind, text, todo]) =>
          `<div class="ss-hint ss-${kind}">${icon(iconFor[kind], 22)}<div class="ss-n"><div>${esc(text)}</div>${todo ? `<small>${esc(todo)}</small>` : ""}</div></div>`,
      )
      .join("");
  } else {
    const note = info.failed ? "Setup details are not available right now." : "Checking the setup.";
    body = `<div class="ss-hint ss-info ss-quiet">${icon("info", 22)}<div class="ss-n">${note}</div></div>`;
  }
  return ssGroup("Setup", `<div class="ss-rows">${body}</div>`, right);
}

function settingsAbout(ctx, info) {
  // Without card_info, the device registry still knows model and firmware.
  const device = ctx.hass.devices?.[ctx.card._config.device_id];
  const model = info.data?.model || (device?.model !== "Valerion" && device?.model);
  const firmware = info.data?.firmware || device?.sw_version;
  const rows = [
    ["projector", "Model", model],
    ["cog", "Firmware", firmware],
    ["info", "Integration", info.data?.version],
  ]
    .filter(([, , value]) => value)
    .map(([name, label, value]) => ssRow(name, label, value))
    .join("");
  const link = (url, name, label) =>
    `<a class="ss-btn pr" href="${url}" target="_blank" rel="noreferrer">${icon(name, 18)}<span>${label}</span></a>`;
  return ssGroup(
    "About",
    `${rows ? `<div class="ss-rows">${rows}</div>` : ""}<div class="ss-links">${link(DOCS_URL, "help", "Documentation")}${link(ISSUES_URL, "alert", "Report a problem")}</div>`,
  );
}

Object.assign(ACTIONS, {
  // Home Assistant's own navigation: no page reload.
  "valerion-device-page": (card) => {
    history.pushState(null, "", `/config/devices/device/${encodeURIComponent(card._config.device_id)}`);
    fire(window, "location-changed", { replace: false });
  },
});

/* ---------- Remote tab ---------- */

Object.assign(ICONS, {
  up: "M7.41,15.41L12,10.83L16.59,15.41L18,14L12,8L6,14L7.41,15.41Z",
  down: "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z",
  left: "M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z",
  right: "M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z",
  back: "M20 13.5C20 17.09 17.09 20 13.5 20H6V18H13.5C16 18 18 16 18 13.5S16 9 13.5 9H7.83L10.91 12.09L9.5 13.5L4 8L9.5 2.5L10.92 3.91L7.83 7H13.5C17.09 7 20 9.91 20 13.5Z",
  home: "M12 5.69L17 10.19V18H15V12H9V18H7V10.19L12 5.69M12 3L2 12H5V20H11V14H13V20H19V12H22",
  menu: "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z",
  keySettings:
    "M3,17V19H9V17H3M3,5V7H13V5H3M13,21V19H21V17H13V15H11V21H13M7,9V11H3V13H7V15H9V9H7M21,13V11H11V13H21M15,9H17V7H21V5H17V3H15V9Z",
  volume:
    "M14,3.23V5.29C16.89,6.15 19,8.83 19,12C19,15.17 16.89,17.84 14,18.7V20.77C18,19.86 21,16.28 21,12C21,7.72 18,4.14 14,3.23M16.5,12C16.5,10.23 15.5,8.71 14,7.97V16C15.5,15.29 16.5,13.76 16.5,12M3,9V15H7L12,20V4L7,9H3Z",
  volumeOff:
    "M12,4L9.91,6.09L12,8.18M4.27,3L3,4.27L7.73,9H3V15H7L12,20V13.27L16.25,17.53C15.58,18.04 14.83,18.46 14,18.7V20.77C15.38,20.45 16.63,19.82 17.68,18.96L19.73,21L21,19.73L12,10.73M19,12C19,12.94 18.8,13.82 18.46,14.64L19.97,16.15C20.62,14.91 21,13.5 21,12C21,7.72 18,4.14 14,3.23V5.29C16.89,6.15 19,8.83 19,12M16.5,12C16.5,10.23 15.5,8.71 14,7.97V10.18L16.45,12.63C16.5,12.43 16.5,12.21 16.5,12Z",
  plus: "M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z",
  minus: "M19,13H5V11H19V13Z",
});

/** A held key waits this long before it repeats, then repeats at most this often (ms). */
const REMOTE_REPEAT_DELAY = 400;
const REMOTE_REPEAT_EVERY = 180;
/** A key held longer than this stops on its own, in case a release got lost (ms). */
const REMOTE_HOLD_MAX = 30000;
/** Keys that repeat while held, as on the projector's own remote. */
const REMOTE_REPEATS = new Set(["up", "down", "left", "right", "volume_up", "volume_down"]);
/** Home Assistant's volume 0..1 is 0..100 on the projector. */
const REMOTE_VOLUME_MAX = 100;
/** Media player features (MediaPlayerEntityFeature). */
const MP_VOLUME_SET = 4;
const MP_VOLUME_MUTE = 8;
const MP_VOLUME_STEP = 1024;
const MP_SELECT_SOURCE = 2048;

const remoteSupports = (player, feature) => {
  const features = player?.attributes.supported_features;
  return typeof features !== "number" || (features & feature) !== 0;
};

/**
 * The service call of a key: its button entity (button.key_<name>), or the
 * remote entity when that button is missing or disabled. Volume steps are the
 * media player's. Returns null when nothing in Home Assistant sends the key.
 */
function remoteKeyCall(ctx, name) {
  if (name === "volume_up" || name === "volume_down") {
    const { player } = ctx;
    if (!player || !remoteSupports(player, MP_VOLUME_STEP)) return null;
    return { domain: "media_player", service: name, data: { entity_id: player.entity_id } };
  }
  const button = ctx.entities.byKey[`button.key_${name}`];
  if (button) return { domain: "button", service: "press", data: { entity_id: button } };
  const remote = ctx.entities.byKey["remote.remote"];
  if (remote) {
    return { domain: "remote", service: "send_command", data: { entity_id: remote, command: name } };
  }
  return null;
}

/** Attributes of a key button, or null when the key does not exist. */
function remoteKeyAttrs(ctx, name, label) {
  const call = remoteKeyCall(ctx, name);
  if (!call) return null;
  const usable = ctx.isOn && ctx.hass.states[call.data.entity_id]?.state !== "unavailable";
  return `data-hold="${name}" aria-label="${esc(label)}"${usable ? "" : " disabled"}`;
}

function remoteInputs(ctx) {
  const { player } = ctx;
  const sources = player?.attributes.source_list;
  if (!Array.isArray(sources) || !sources.length || !remoteSupports(player, MP_SELECT_SOURCE)) return "";
  const current = ctx.isOn ? player.attributes.source : undefined;
  const options = sources
    .map((source) => {
      const selected = source === current;
      return `<button class="pr rm-opt${selected ? " sel" : ""}" data-action="remote-input" data-source="${esc(source)}" aria-pressed="${selected}"${ctx.isOn ? "" : " disabled"}>${esc(source)}</button>`;
    })
    .join("");
  return `<section class="rm-grp rm-in" aria-labelledby="rm-in-t"><div class="rm-h"><span class="rm-t" id="rm-in-t">Input</span></div>
<div class="rm-seg" role="group" aria-labelledby="rm-in-t" style="--n:${sources.length}">${options}</div></section>`;
}

function remotePad(ctx) {
  const arrow = (name, label) => {
    const attrs = remoteKeyAttrs(ctx, name, label);
    return attrs ? `<button class="pr rm-dk rm-${name}" ${attrs}>${icon(name, 30)}</button>` : "";
  };
  const ok = remoteKeyAttrs(ctx, "ok", "OK");
  const arrows = [arrow("up", "Up"), arrow("left", "Left"), arrow("right", "Right"), arrow("down", "Down")].join("");
  const keys = [
    ["return", "back", "Back"],
    ["home", "home", "Home"],
    ["menu", "menu", "Menu"],
    ["settings", "keySettings", "Settings"],
  ]
    .map(([name, glyph, label]) => {
      const attrs = remoteKeyAttrs(ctx, name, label);
      return attrs ? `<button class="pr rm-key" ${attrs}>${icon(glyph)}<span>${esc(label)}</span></button>` : "";
    })
    .filter(Boolean);
  if (!arrows && !ok && !keys.length) return "";
  const okKey = ok ? `<button class="pr rm-dk rm-ok" ${ok}>OK</button>` : "";
  const pad = arrows || ok ? `<div class="rm-dpad" role="group" aria-label="Navigation">${arrows}${okKey}</div>` : "";
  const row = keys.length ? `<div class="rm-keys" style="--n:${keys.length}">${keys.join("")}</div>` : "";
  return `<section class="rm-grp rm-pad" aria-label="Keys">${pad}${row}</section>`;
}

function remoteVolume(ctx) {
  const { player } = ctx;
  if (!player) return "";
  const canSet = remoteSupports(player, MP_VOLUME_SET);
  const canMute = remoteSupports(player, MP_VOLUME_MUTE);
  const minus = remoteKeyAttrs(ctx, "volume_down", "Volume down");
  const plus = remoteKeyAttrs(ctx, "volume_up", "Volume up");
  if (!canSet && !canMute && !minus && !plus) return "";
  const level = player.attributes.volume_level;
  const value = typeof level === "number" ? Math.round(level * REMOTE_VOLUME_MAX) : null;
  const muted = player.attributes.is_volume_muted === true;
  const off = ctx.isOn ? "" : " disabled";
  const shown = muted ? "Muted" : (value ?? "");
  const mute = canMute
    ? `<button class="pr rm-ib${muted ? " sel" : ""}" data-action="remote-mute" aria-pressed="${muted}" aria-label="Mute"${off}>${icon(muted ? "volumeOff" : "volume")}</button>`
    : "";
  const step = (attrs, glyph) => (attrs ? `<button class="pr rm-ib" ${attrs}>${icon(glyph)}</button>` : "");
  const now = value ?? 0;
  const focus = ctx.isOn ? `tabindex="0"` : `tabindex="-1" aria-disabled="true"`;
  const slider = canSet
    ? `<div class="rm-slider${muted ? " dim" : ""}" data-slider="volume" role="slider" aria-label="Volume" aria-valuemin="0" aria-valuemax="${REMOTE_VOLUME_MAX}" aria-valuenow="${now}"${muted ? ` aria-valuetext="Muted, ${now}"` : ""} ${focus} style="--f:${now / REMOTE_VOLUME_MAX}"><div class="rm-fill"></div><div class="rm-hdl"></div></div>`
    : `<span class="rm-gap"></span>`;
  return `<section class="rm-grp rm-vol" aria-labelledby="rm-vol-t"><div class="rm-h"><span class="rm-t" id="rm-vol-t">Volume</span><span class="rm-v">${shown}</span></div>
<div class="rm-row">${mute}${step(minus, "minus")}${slider}${step(plus, "plus")}</div></section>`;
}

/** Call a service; a failure is shown as a toast. Resolves to true on success. */
async function remoteCall(card, domain, service, data) {
  try {
    await card.hass.callService(domain, service, data);
    return true;
  } catch (err) {
    fire(card, "hass-notification", { message: err?.message || String(err) });
    return false;
  }
}

/** Send one key press, if the projector is on and the key exists. */
function remoteSendKey(card, name) {
  const ctx = card._context();
  const call = ctx.isOn && remoteKeyCall(ctx, name);
  if (!call) return Promise.resolve(false);
  return remoteCall(card, call.domain, call.service, call.data);
}

ACTIONS["remote-input"] = (card, el, ctx) => {
  if (!ctx.player || el.getAttribute("aria-pressed") === "true") return;
  fire(card, "haptic", "selection");
  for (const option of el.parentElement.children) {
    option.classList.toggle("sel", option === el);
    option.setAttribute("aria-pressed", String(option === el));
  }
  remoteCall(card, "media_player", "select_source", {
    entity_id: ctx.player.entity_id,
    source: el.dataset.source,
  }).then((ok) => ok || card._renderPane());
};

ACTIONS["remote-mute"] = (card, el, ctx) => {
  if (!ctx.player) return;
  fire(card, "haptic", "light");
  remoteCall(card, "media_player", "volume_mute", {
    entity_id: ctx.player.entity_id,
    is_volume_muted: ctx.player.attributes.is_volume_muted !== true,
  });
};

/*
 * Held keys and the volume slider. The pane is rendered again whenever an
 * entity changes (often during a hold: the volume moves), so the listeners
 * sit on the pane and the window, a key is known by its name and not by its
 * element, and a MutationObserver puts the pressed look, the dragged value
 * and the focus back after each render.
 *
 * A tap is sent on release, so scrolling the dashboard across the card sends
 * nothing (the browser cancels the pointer). A key held for
 * REMOTE_REPEAT_DELAY is sent at once and, if it repeats, again until it is
 * released; each send waits for the previous service call to return, so
 * nothing queues up. Enter and Space send on keydown and repeat the same way.
 */
function remoteSetup(card, pane) {
  const st = { hold: null, drag: null, pending: null, focus: null };
  const root = pane.getRootNode();
  const holdKey = (node) => (node instanceof Element ? node.closest("[data-hold]") : null);
  const pathKey = (ev) => ev.composedPath().find((node) => node instanceof Element && node.dataset.hold);

  function stop(send) {
    const hold = st.hold;
    if (!hold) return;
    st.hold = null;
    hold.active = false;
    clearTimeout(hold.timer);
    clearTimeout(hold.limit);
    window.removeEventListener("pointerup", onPointerUp, true);
    window.removeEventListener("pointercancel", onPointerCancel, true);
    window.removeEventListener("keyup", onKeyUp, true);
    pane.querySelector(`[data-hold="${hold.name}"]`)?.classList.remove("held");
    if (send && !hold.sent) hold.send();
  }

  function start(el, how, pointerId) {
    stop(false);
    st.pending = null;
    const hold = { name: el.dataset.hold, how, pointerId, active: true, sent: false, inflight: null };
    hold.send = () => {
      if (!hold.sent) fire(card, "haptic", "light");
      hold.sent = true;
      hold.inflight = remoteSendKey(card, hold.name);
      return hold.inflight;
    };
    const repeat = async () => {
      if (hold.inflight) await hold.inflight;
      while (hold.active) {
        const began = performance.now();
        if (!(await hold.send())) break;
        const wait = REMOTE_REPEAT_EVERY - (performance.now() - began);
        if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
      }
    };
    st.hold = hold;
    el.classList.add("held");
    if (how === "key") hold.send();
    hold.timer = setTimeout(() => {
      if (!hold.active) return;
      if (REMOTE_REPEATS.has(hold.name)) repeat();
      else if (!hold.sent) hold.send();
    }, REMOTE_REPEAT_DELAY);
    hold.limit = setTimeout(() => hold.active && stop(false), REMOTE_HOLD_MAX);
    if (how === "pointer") {
      window.addEventListener("pointerup", onPointerUp, true);
      window.addEventListener("pointercancel", onPointerCancel, true);
    } else {
      window.addEventListener("keyup", onKeyUp, true);
    }
  }

  function onPointerUp(ev) {
    const hold = st.hold;
    if (hold?.how !== "pointer" || ev.pointerId !== hold.pointerId) return;
    stop(pathKey(ev)?.dataset.hold === hold.name);
  }
  function onPointerCancel(ev) {
    if (st.hold?.how === "pointer" && ev.pointerId === st.hold.pointerId) stop(false);
  }
  function onKeyUp(ev) {
    if (st.hold?.how === "key" && (ev.key === "Enter" || ev.key === " ")) {
      ev.preventDefault();
      stop(false);
    }
  }

  pane.addEventListener("pointerdown", (ev) => {
    if (!ev.isPrimary || ev.button !== 0) return;
    const el = holdKey(ev.target);
    if (el) {
      if (el.disabled) return;
      // Touch captures the pointer to the key; release it so leaving the key cancels.
      if (el.hasPointerCapture(ev.pointerId)) el.releasePointerCapture(ev.pointerId);
      start(el, "pointer", ev.pointerId);
      return;
    }
    const slider = ev.target instanceof Element ? ev.target.closest("[data-slider]") : null;
    if (slider && slider.getAttribute("aria-disabled") !== "true") dragStart(slider, ev);
  });
  pane.addEventListener("pointerout", (ev) => {
    const hold = st.hold;
    if (hold?.how !== "pointer" || ev.pointerId !== hold.pointerId) return;
    if (holdKey(ev.relatedTarget)?.dataset.hold !== hold.name) stop(false);
  });
  pane.addEventListener("pointerover", (ev) => {
    const hold = st.hold;
    if (hold?.how !== "pointer" || ev.pointerId !== hold.pointerId) return;
    if (holdKey(ev.target)?.dataset.hold !== hold.name) stop(false);
  });
  pane.addEventListener("contextmenu", (ev) => {
    if (holdKey(ev.target)) ev.preventDefault();
  });
  pane.addEventListener("keydown", (ev) => {
    const el = holdKey(ev.target);
    if (el && (ev.key === "Enter" || ev.key === " ")) {
      ev.preventDefault();
      if (!ev.repeat && !el.disabled) start(el, "key");
      return;
    }
    if (ev.target instanceof Element && ev.target.matches("[data-slider]")) sliderKey(ev);
  });
  pane.addEventListener("keyup", (ev) => {
    if (holdKey(ev.target) && (ev.key === "Enter" || ev.key === " ")) ev.preventDefault();
  });
  // Assistive technology activates a button with a plain click (detail 0).
  pane.addEventListener("click", (ev) => {
    const el = holdKey(ev.target);
    if (el && ev.detail === 0 && !st.hold && !el.disabled) {
      fire(card, "haptic", "light");
      remoteSendKey(card, el.dataset.hold);
    }
  });

  /* ----- volume slider ----- */

  const sliderEl = () => pane.querySelector("[data-slider]");
  const showVolume = (value) => {
    const el = sliderEl();
    if (!el) return;
    el.style.setProperty("--f", String(value / REMOTE_VOLUME_MAX));
    el.setAttribute("aria-valuenow", String(value));
    const out = pane.querySelector(".rm-vol .rm-v");
    if (out) out.textContent = String(value);
  };
  const valueAt = (x) => {
    const box = sliderEl()?.getBoundingClientRect();
    if (!box?.width) return 0;
    const f = Math.min(1, Math.max(0, (x - box.left - 9) / (box.width - 18)));
    return Math.round(f * REMOTE_VOLUME_MAX);
  };
  const setVolume = (value) => {
    const ctx = card._context();
    if (!ctx.player || !ctx.isOn) return;
    st.pending = { value, until: performance.now() + 2000 };
    showVolume(value);
    remoteCall(card, "media_player", "volume_set", {
      entity_id: ctx.player.entity_id,
      volume_level: value / REMOTE_VOLUME_MAX,
    });
  };
  function dragStart(el, ev) {
    el.setPointerCapture(ev.pointerId);
    el.focus({ preventScroll: true });
    st.drag = { pointerId: ev.pointerId, value: valueAt(ev.clientX) };
    showVolume(st.drag.value);
    const move = (e) => {
      if (e.pointerId !== st.drag?.pointerId) return;
      st.drag.value = valueAt(e.clientX);
      showVolume(st.drag.value);
    };
    const end = (e) => {
      if (e.pointerId !== st.drag?.pointerId) return;
      window.removeEventListener("pointermove", move, true);
      window.removeEventListener("pointerup", end, true);
      window.removeEventListener("pointercancel", end, true);
      const { value } = st.drag;
      st.drag = null;
      if (e.type === "pointerup") {
        fire(card, "haptic", "light");
        setVolume(value);
      } else {
        card._renderPane();
      }
    };
    window.addEventListener("pointermove", move, true);
    window.addEventListener("pointerup", end, true);
    window.addEventListener("pointercancel", end, true);
  }
  function sliderKey(ev) {
    const now = Number(ev.target.getAttribute("aria-valuenow")) || 0;
    const moves = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10 };
    let value;
    if (ev.key in moves) value = now + moves[ev.key];
    else if (ev.key === "Home") value = 0;
    else if (ev.key === "End") value = REMOTE_VOLUME_MAX;
    else return;
    ev.preventDefault();
    setVolume(Math.min(REMOTE_VOLUME_MAX, Math.max(0, value)));
  }

  /* ----- after each render ----- */

  const identity = (el) => {
    if (el?.dataset?.hold) return `[data-hold="${el.dataset.hold}"]`;
    return el?.dataset?.slider ? "[data-slider]" : null;
  };
  pane.addEventListener("focusin", (ev) => {
    st.focus = identity(ev.target);
  });
  pane.addEventListener("focusout", (ev) => {
    // A render removes the focused element and fires focusout too; tell the
    // two apart once the render is done.
    const { target } = ev;
    setTimeout(() => {
      if (!target.isConnected) return;
      const now = identity(root.activeElement);
      st.focus = pane.contains(root.activeElement) ? now : null;
      if (st.hold?.how === "key" && now !== `[data-hold="${st.hold.name}"]`) stop(false);
    });
  });
  new MutationObserver(() => {
    const hold = st.hold;
    if (hold) pane.querySelector(`[data-hold="${hold.name}"]`)?.classList.add("held");
    const pending = st.pending && performance.now() < st.pending.until ? st.pending.value : null;
    const value = st.drag ? st.drag.value : pending;
    const rendered = sliderEl()?.getAttribute("aria-valuenow");
    if (!st.drag && rendered === String(pending)) st.pending = null;
    else if (value !== null && rendered !== String(value)) showVolume(value);
    // A focused element that a render removed leaves the focus on the body.
    const lost = !root.activeElement && (!document.activeElement || document.activeElement === document.body);
    if (st.focus && lost) pane.querySelector(st.focus)?.focus({ preventScroll: true });
  }).observe(pane, { childList: true });
}

/* ---------- Advanced tab ---------- */

function renderAdvanced(ctx) {
  return comingLater(ctx, "advanced", "Advanced settings", "Laser level, black level, motion, gamma, tone mapping and the lens menus.");
}

/** Runs once when the card builds its DOM (see TABS). */
function advancedSetup(_card, _pane) {}

/* ---------- end of Advanced tab ---------- */

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

.pane{height:var(--valerion-pane-height,540px);overflow:hidden;min-width:0;transition:opacity .2s}
.pane.dim{opacity:.35;pointer-events:none}
.tab{height:100%;display:flex;flex-direction:column;gap:12px;min-width:0}

/* ---------- Status and Settings tabs ---------- */
.ss-grp{border:1px solid var(--divider-color,#e0e0e0);border-radius:var(--vc-radius);padding:12px;
  display:flex;flex-direction:column;gap:6px;min-width:0}
.ss-h{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:24px;font-weight:500}
.ss-hero{gap:2px}
.ss-kick{font-size:13px;color:var(--secondary-text-color,#727272)}
.ss-big{font-size:28px;line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ss-sub{color:var(--secondary-text-color,#727272);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ss-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.ss-chip{height:26px;padding:0 10px;border-radius:8px;border:1px solid var(--divider-color,#e0e0e0);
  font-size:13px;display:inline-flex;align-items:center;white-space:nowrap}
.ss-rows{display:flex;flex-direction:column}
.ss-row{display:flex;align-items:center;gap:16px;min-height:34px}
.ss-row svg,.ss-hint svg{color:var(--secondary-text-color,#727272)}
.ss-n{flex:1;min-width:0}
.ss-row .ss-n{white-space:nowrap}
.ss-v{color:var(--secondary-text-color,#727272);text-align:right;font-variant-numeric:tabular-nums;
  min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ss-v.ss-bad{color:var(--error-color,#db4437);font-weight:500}
.ss-foot{margin-top:auto;font-size:12px;color:var(--secondary-text-color,#727272);text-align:center}
.ss-hint{display:flex;align-items:flex-start;gap:16px;padding:6px 0}
.ss-hint .ss-n{padding-top:1px}
.ss-hint small{display:block;font-size:12px;line-height:1.35;color:var(--secondary-text-color,#727272)}
.ss-hint.ss-ok svg{color:var(--success-color,#43a047)}
.ss-hint.ss-warn svg{color:var(--warning-color,#ffa600)}
.ss-quiet{color:var(--secondary-text-color,#727272)}
.ss-btn{min-height:40px;padding:0 12px;border-radius:20px;background-color:transparent;color:var(--primary-color,#03a9f4);
  font-weight:500;font-size:14px;display:inline-flex;align-items:center;gap:6px;text-decoration:none;white-space:nowrap}
.ss-h .ss-btn{margin:-10px -8px -10px 0}
.ss-links{display:flex;flex-wrap:wrap;gap:4px;margin:0 -8px -4px}
.cl-p{margin:0}
@container (min-width:600px){
  .ss-lay{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-rows:auto 1fr;align-items:start}
  .ss-lay > .ss-wide{grid-column:1 / -1;align-self:end}
}

/* ---------- shared controls ---------- */
.vc-grp{border:1px solid var(--divider-color,rgba(0,0,0,.12));border-radius:var(--vc-radius);padding:12px;
  display:flex;flex-direction:column;gap:10px;min-width:0}
.vc-h{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:22px}
.vc-t{font-weight:500}
.vc-v{font-weight:500;font-variant-numeric:tabular-nums;color:var(--secondary-text-color,#727272)}
.vc-seg{display:grid;grid-template-columns:repeat(var(--n,4),minmax(0,1fr));gap:4px;padding:4px;
  border-radius:var(--vc-radius);background:var(--vc-ctl)}
.vc-opt{min-height:var(--vc-opt-h,44px);border-radius:var(--vc-in-radius);background-color:transparent;padding:4px 2px;line-height:1.2;
  text-align:center;overflow-wrap:anywhere;display:flex;align-items:center;justify-content:center}
.vc-opt.sel{background-color:var(--vc-sel);box-shadow:inset 0 0 0 2px var(--primary-color,#03a9f4);font-weight:500}
.vc-opt:disabled{cursor:default;background-image:none}
.is-on .vc-opt:disabled{opacity:.35}
.vc-lock{display:flex;align-items:center;gap:8px;min-height:24px;font-size:13px;color:var(--secondary-text-color,#727272)}
.vc-lock svg{color:var(--secondary-text-color,#727272)}
@container (min-width:600px){
  .vc-seg{grid-template-columns:repeat(var(--nw,var(--n,4)),minmax(0,1fr))}
}

/* ---------- Picture tab (classes pc-) ---------- */
/* On a phone the groups are a little tighter, so all of it fits the pane. */
.tab-picture{gap:8px;--vc-opt-h:40px}
.tab-picture .vc-grp{padding:10px 12px;gap:8px}
.pc-mode .vc-opt{font-size:12px;padding:2px;overflow-wrap:normal}
/* One line: the second sentence drops out (to a hidden line) when it does not fit. */
.pc-sub{margin-top:-4px;height:16px;overflow:hidden;display:flex;flex-wrap:wrap;column-gap:.3em;
  font-size:12px;line-height:16px;color:var(--secondary-text-color,#727272)}
.pc-sub span{white-space:nowrap}
.pc-badge{display:inline-flex;align-items:center;gap:6px;height:22px;box-sizing:border-box;padding:0 10px;border-radius:11px;flex:none;
  border:1px solid var(--divider-color,rgba(0,0,0,.12));font-size:12px;font-weight:500;white-space:nowrap}
.pc-badge::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--primary-color,#03a9f4)}
.pc-ana{display:flex;align-items:center;gap:8px}
.pc-ana .vc-seg{flex:1;min-width:0}
.pc-lbl{flex:none;width:68px;font-size:12px;line-height:1.25;color:var(--secondary-text-color,#727272)}
.pc-note{display:flex;align-items:center;gap:8px;min-height:28px;padding:2px 4px;font-size:13px;color:var(--secondary-text-color,#727272)}
.pc-note svg{color:var(--secondary-text-color,#727272)}
.pc-quiet{margin:0;min-height:40px;display:flex;align-items:center;font-size:13px;color:var(--secondary-text-color,#727272)}
.pc-chips{display:flex;gap:6px;min-height:40px;overflow-x:auto;scrollbar-width:none;margin:-2px;padding:2px}
.pc-chips.pc-pick{flex-wrap:wrap;overflow:visible}
.pc-chips::-webkit-scrollbar{display:none}
.pc-chip{flex:none;min-height:40px;max-width:200px;padding:0 10px;border-radius:var(--vc-radius);box-sizing:border-box;
  border:1px solid var(--divider-color,rgba(0,0,0,.12));background-color:transparent;font:inherit;color:var(--primary-text-color,#212121);
  display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.pc-chip > span{min-width:0;overflow:hidden;text-overflow:ellipsis}
.tab-picture .pc-chip{flex:0 1 auto;min-width:64px}
.pc-chip.pc-add{flex:none;min-width:0;border-style:dashed;color:var(--secondary-text-color,#727272);padding:0 12px 0 10px}
.tab-picture .pc-add span{display:none}
.pc-chip[aria-pressed="true"]{background-color:var(--vc-sel);box-shadow:inset 0 0 0 2px var(--primary-color,#03a9f4);
  border-color:transparent;font-weight:500}
.pc-chip:disabled{cursor:default;background-image:none}
.is-on .pc-chip:disabled{opacity:.35}
.pc-tbtn{min-height:40px;padding:0 12px;border-radius:20px;background-color:transparent;font:inherit;font-weight:500;
  color:var(--primary-color,#03a9f4);display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.vc-h .pc-tbtn{margin:-10px -8px -10px 0}
.pc-tbtn:disabled,.pc-fbtn:disabled{opacity:.5;cursor:default;background-image:none}
@container (min-width:600px){
  .tab-picture{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);align-content:start;gap:12px;--vc-opt-h:44px}
  .tab-picture .vc-grp{padding:12px;gap:10px}
  .pc-mode,.pc-ar,.tab-picture > .vc-lock{grid-column:1 / -1}
  .pc-mode .vc-opt{font-size:14px;padding:4px 2px}
  .pc-sub{font-size:13px}
  .pc-ana{flex-direction:column;align-items:stretch;gap:6px}
  .pc-lbl{width:auto;font-size:13px}
  .tab-picture .pc-add span{display:inline}
}
/* the scene editor, in the sheet */
.pc-hint{margin:0;font-size:13px;color:var(--secondary-text-color,#727272)}
.pc-pick{flex:none}
.pc-name{flex:none;height:44px;width:100%;box-sizing:border-box;padding:0 12px;border:0;
  border-bottom:1px solid var(--secondary-text-color,#727272);border-radius:var(--vc-in-radius) var(--vc-in-radius) 0 0;
  background:var(--vc-ctl);color:var(--primary-text-color,#212121);font:inherit;font-size:15px}
.pc-name:focus{outline:none;border-bottom:2px solid var(--primary-color,#03a9f4)}
.pc-name::placeholder{color:var(--secondary-text-color,#727272)}
.pc-rows{flex:none;border:1px solid var(--divider-color,rgba(0,0,0,.12));border-radius:var(--vc-radius);padding:2px 12px}
.pc-row{display:flex;align-items:center;gap:12px;min-height:50px}
.pc-rl{flex:1;min-width:0}
.pc-sel{flex:none;width:52%;max-width:220px;height:40px;padding:0 8px;border:0;
  border-bottom:1px solid var(--secondary-text-color,#727272);border-radius:var(--vc-in-radius) var(--vc-in-radius) 0 0;
  background:var(--vc-ctl);color:var(--primary-text-color,#212121);font:inherit}
.pc-sel option{background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--primary-text-color,#212121)}
.pc-sel.set{border-bottom-color:var(--primary-color,#03a9f4);font-weight:500}
.pc-sel:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:2px}
.pc-err{margin:0;font-size:13px;color:var(--error-color,#db4437)}
.pc-foot{flex:none;position:sticky;bottom:-16px;margin:0 -16px -16px;padding:8px 16px 16px;display:flex;align-items:center;gap:8px;
  background:var(--ha-card-background,var(--card-background-color,#fff))}
.pc-gap{flex:1}
.pc-fbtn{min-height:44px;padding:0 24px;border-radius:22px;background-color:var(--primary-color,#03a9f4);font:inherit;font-weight:500;
  color:var(--text-primary-color,#fff)}
.pc-danger{color:var(--error-color,#db4437)}
.pc-tbtn.pc-confirm{background-color:color-mix(in srgb,var(--error-color,#db4437) 14%,transparent)}
/* ---------- end of Picture tab styles ---------- */

/* ---------- sheet ---------- */
.sheet{border:0;padding:0;margin:auto auto 0;width:100%;max-width:560px;max-height:min(85vh,720px);box-sizing:border-box;
  border-radius:var(--ha-dialog-border-radius,28px) var(--ha-dialog-border-radius,28px) 0 0;
  background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--primary-text-color,#212121);
  font-family:var(--ha-font-family-body,Roboto,system-ui,sans-serif);font-size:14px;line-height:1.4;
  --vc-radius:var(--ha-card-border-radius,12px);--vc-in-radius:calc(var(--vc-radius) - 3px);
  --vc-ctl:color-mix(in srgb,var(--disabled-color,#bdbdbd) 22%,transparent);
  --vc-hover:color-mix(in srgb,var(--primary-text-color,#212121) 10%,transparent);
  --vc-press:color-mix(in srgb,var(--primary-text-color,#212121) 18%,transparent);
  --vc-sel:color-mix(in srgb,var(--primary-color,#03a9f4) 20%,transparent);
  container-type:inline-size}
.sheet::backdrop{background:rgba(0,0,0,.45)}
.sheet svg{display:block;flex:none}
.sheet-in{display:flex;flex-direction:column;max-height:inherit}
.sheet-handle{width:32px;height:4px;border-radius:2px;margin:10px auto 0;background:var(--divider-color,rgba(0,0,0,.2))}
.sheet-head{display:flex;align-items:center;gap:8px;padding:4px 12px 0}
.sheet-x{width:44px;height:44px;border-radius:50%;background-color:transparent;display:grid;place-items:center;padding:0}
.sheet-t{margin:0;flex:1;font-size:20px;font-weight:400;line-height:1.3}
.sheet-body{padding:8px 16px 16px;overflow:auto;display:flex;flex-direction:column;gap:12px;min-height:0}
@media (min-width:600px){
  .sheet{margin:auto;border-radius:var(--ha-dialog-border-radius,28px);width:calc(100% - 32px);max-width:480px}
  .sheet-handle{display:none}
}

/* ---------- Remote tab ---------- */
.tab-remote{display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:auto 1fr auto;
  grid-template-areas:"in" "pad" "vol";gap:12px}
.rm-in{grid-area:in}.rm-pad{grid-area:pad}.rm-vol{grid-area:vol}
.rm-none{margin:0;color:var(--secondary-text-color,#727272)}
.rm-grp{border:1px solid var(--divider-color,rgba(0,0,0,.12));border-radius:var(--vc-radius);padding:12px;
  display:flex;flex-direction:column;gap:10px;min-width:0}
.rm-h{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:22px}
.rm-t{font-weight:500}
.rm-v{font-weight:500;font-variant-numeric:tabular-nums}
.rm-seg{display:grid;grid-template-columns:repeat(var(--n,4),minmax(0,1fr));gap:4px;padding:4px;
  border-radius:var(--vc-radius);background:var(--vc-ctl)}
.rm-opt{min-height:44px;border-radius:var(--vc-in-radius);background-color:transparent;padding:4px 2px;line-height:1.2;
  text-align:center;overflow-wrap:anywhere;display:flex;align-items:center;justify-content:center}
.rm-opt.sel,.rm-ib.sel{background-color:var(--vc-sel);box-shadow:inset 0 0 0 2px var(--primary-color,#03a9f4);font-weight:500}
.rm-pad{justify-content:center}
.rm-dpad{--d:208px;position:relative;width:var(--d);height:var(--d);flex:none;margin:0 auto;border-radius:50%;
  background:var(--vc-ctl)}
.rm-dk{position:absolute;display:grid;place-items:center;padding:0;border-radius:var(--vc-radius);
  background-color:transparent;color:var(--primary-color,#03a9f4)}
.rm-up{left:31%;right:31%;top:3%;height:28%}
.rm-down{left:31%;right:31%;bottom:3%;height:28%}
.rm-left{top:31%;bottom:31%;left:3%;width:28%}
.rm-right{top:31%;bottom:31%;right:3%;width:28%}
.rm-ok{left:32%;top:32%;width:36%;height:36%;border-radius:50%;
  background-color:var(--ha-card-background,var(--card-background-color,#fff));box-shadow:0 0 0 1px var(--divider-color,rgba(0,0,0,.12));
  font-size:16px;font-weight:500;letter-spacing:.04em;color:var(--primary-text-color,#212121)}
.rm-keys{display:grid;grid-template-columns:repeat(var(--n,4),minmax(0,1fr));gap:8px}
.rm-key{min-height:56px;min-width:44px;padding:6px 4px;border-radius:var(--vc-radius);background-color:var(--vc-ctl);
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;color:var(--primary-color,#03a9f4)}
.rm-key span{font-size:12px;line-height:1.2;color:var(--secondary-text-color,#727272)}
.rm-row{display:flex;align-items:center;gap:8px}
.rm-gap{flex:1}
.rm-ib{width:44px;height:44px;flex:none;padding:0;border-radius:var(--vc-radius);background-color:var(--vc-ctl);
  display:grid;place-items:center;color:var(--primary-color,#03a9f4)}
[data-hold]{touch-action:manipulation;user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}
.pr.held{background-image:linear-gradient(var(--vc-press),var(--vc-press))}
.is-on .tab-remote button:disabled{opacity:.35}
.tab-remote button:disabled{cursor:default;background-image:none}
.rm-slider{--f:0;position:relative;flex:1;min-width:0;height:44px;border-radius:var(--vc-radius);overflow:hidden;cursor:pointer;
  touch-action:pan-y;user-select:none;-webkit-user-select:none;
  background:color-mix(in srgb,var(--primary-color,#03a9f4) 20%,transparent)}
.rm-slider:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:2px}
.rm-slider.dim{opacity:.5}
.rm-fill{position:absolute;inset:0 auto 0 0;width:calc(18px + (100% - 18px) * var(--f));
  border-radius:var(--vc-radius) 0 0 var(--vc-radius);background:var(--primary-color,#03a9f4)}
.rm-hdl{position:absolute;top:50%;left:calc(18px + (100% - 18px) * var(--f) - 10px);width:4px;height:20px;margin-top:-10px;
  border-radius:2px;background:var(--text-primary-color,#fff)}
@container (min-width:600px){
  .tab-remote{grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-rows:auto 1fr;
    grid-template-areas:"pad in" "pad vol";align-items:start}
  .rm-pad{align-self:stretch}
  .rm-vol{align-self:end}
  .rm-dpad{--d:256px}
}

/* ---------- Advanced tab (classes ad-) ---------- */
/* ---------- end of Advanced tab styles ---------- */

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
    this._sheet = null;
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
      card: this,
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
    this._renderAll();
  }

  /** Render the header, the pane and an open sheet. */
  _renderAll() {
    this._renderShell();
    this._renderPane();
    this._renderSheet();
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
  <dialog class="sheet" aria-labelledby="sheet-t">
    <div class="sheet-in">
      <div class="sheet-handle" aria-hidden="true"></div>
      <div class="sheet-head">
        <button class="pr sheet-x" data-action="sheet-close" aria-label="Close">${icon("close")}</button>
        <h2 class="sheet-t" id="sheet-t"></h2>
      </div>
      <div class="sheet-body"></div>
    </div>
  </dialog>
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
      sheet: root.querySelector(".sheet"),
      sheetTitle: root.querySelector(".sheet-t"),
      sheetBody: root.querySelector(".sheet-body"),
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
    for (const tab of TABS) tab.setup?.(this, this._el.pane);
    this._buildSheet();
  }

  /* ----- sheet ----- */

  _buildSheet() {
    const { sheet, sheetBody } = this._el;
    sheet.addEventListener("click", (ev) => {
      // A tap on the backdrop lands on the dialog itself, outside its content.
      if (ev.target === sheet) {
        this.closeSheet();
        return;
      }
      const el = ev.target.closest("[data-action]");
      const action = el && ACTIONS[el.dataset.action];
      if (action) action(this, el, this._context());
    });
    sheet.addEventListener("cancel", (ev) => {
      ev.preventDefault();
      this.closeSheet();
    });
    // Held keys in a sheet repeat as on the Remote tab.
    remoteSetup(this, sheetBody);
  }

  /** Open a sheet; see the comment above ACTIONS["sheet-close"]. */
  openSheet(spec) {
    if (this._sheet) this.closeSheet(false);
    this._sheet = spec;
    this._renderSheet();
    const { sheet } = this._el;
    if (!sheet.open) sheet.showModal();
    sheet.querySelector(".sheet-body [autofocus]")?.focus();
  }

  /** Close the open sheet; `notify` false skips its onClose. */
  closeSheet(notify = true) {
    const spec = this._sheet;
    if (!spec) return;
    this._sheet = null;
    if (this._el.sheet.open) this._el.sheet.close();
    this._el.sheetBody.innerHTML = "";
    if (notify) spec.onClose?.(this);
  }

  /** The id of the open sheet, or null. */
  get sheetId() {
    return this._sheet ? (this._sheet.id ?? "") : null;
  }

  _renderSheet() {
    const spec = this._sheet;
    if (!spec || !this._el) return;
    const ctx = this._context();
    const title = typeof spec.title === "function" ? spec.title(ctx) : spec.title;
    this._el.sheetTitle.textContent = title || "";
    const html = spec.render(ctx);
    if (html !== null) this._el.sheetBody.innerHTML = html;
  }

  disconnectedCallback() {
    this.closeSheet(false);
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
