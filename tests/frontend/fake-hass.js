// A small stand-in for the `hass` object Home Assistant gives a card.
// Only what the card reads: states, entities (the entity registry as the
// frontend sees it), devices, callService and formatEntityState; callWS
// and user for the Settings tab.

export const DEVICE_ID = "device_pro2";
export const OTHER_DEVICE_ID = "device_max";
export const PLAYER = "media_player.visionmaster_pro2";

const LABELS = { on: "On", off: "Off", standby: "Standby", unavailable: "Unavailable" };

function registry() {
  const entry = (entity_id, device_id, platform, translation_key) => ({
    entity_id,
    device_id,
    platform,
    ...(translation_key ? { translation_key } : {}),
  });
  const list = [
    entry("light.ceiling", "device_light", "hue"),
    entry(PLAYER, DEVICE_ID, "valerion"),
    entry("remote.visionmaster_pro2_remote", DEVICE_ID, "valerion", "remote"),
    entry("select.visionmaster_pro2_picture_mode", DEVICE_ID, "valerion", "picture_mode"),
    entry("sensor.visionmaster_pro2_hdr_format", DEVICE_ID, "valerion", "hdr_format"),
    entry("media_player.visionmaster_max", OTHER_DEVICE_ID, "valerion"),
    ...STATUS_ENTITIES.map(([id, key]) => entry(id, DEVICE_ID, "valerion", key)),
    ...REMOTE_KEYS.map((key) => entry(`button.visionmaster_pro2_${key}`, DEVICE_ID, "valerion", `key_${key}`)),
    ...SETTING_ENTITIES.map(([id, key]) => entry(id, DEVICE_ID, "valerion", key)),
    ...LENS_MENUS.map((name) => entry(`button.visionmaster_pro2_${name}_menu`, DEVICE_ID, "valerion", `${name}_menu`)),
  ];
  return Object.fromEntries(list.map((item) => [item.entity_id, item]));
}

function state(entity_id, value, attributes = {}) {
  return { entity_id, state: value, attributes, last_changed: "", last_updated: "" };
}

/** A fresh hass object; `power` is the media player state. */
export function makeHass({ power = "on", source = "HDMI 1", name = "VisionMaster Pro2" } = {}) {
  const calls = [];
  return {
    calls,
    entities: registry(),
    devices: {
      [DEVICE_ID]: { id: DEVICE_ID, name, name_by_user: null },
      [OTHER_DEVICE_ID]: { id: OTHER_DEVICE_ID, name: "VisionMaster Max", name_by_user: null },
    },
    states: {
      "light.ceiling": state("light.ceiling", "on"),
      [PLAYER]: state(PLAYER, power, {
        ...playerAttributes(power),
        ...(power === "on" ? { source, friendly_name: name } : { friendly_name: name }),
      }),
      "remote.visionmaster_pro2_remote": state("remote.visionmaster_pro2_remote", power === "on" ? "on" : "off"),
      "select.visionmaster_pro2_picture_mode": state(
        "select.visionmaster_pro2_picture_mode",
        power === "on" ? "HDR Theater" : "unavailable",
        { options: HDR_PICTURE_MODES },
      ),
      "sensor.visionmaster_pro2_hdr_format": state("sensor.visionmaster_pro2_hdr_format", "HDR10"),
      "media_player.visionmaster_max": state("media_player.visionmaster_max", "off"),
      ...statusStates(power),
      ...settingStates(power),
      ...Object.fromEntries(
        LENS_MENUS.map((name) => [
          `button.visionmaster_pro2_${name}_menu`,
          state(`button.visionmaster_pro2_${name}_menu`, power === "on" && name !== "lens_shift" ? "unknown" : "unavailable"),
        ]),
      ),
      ...Object.fromEntries(
        REMOTE_KEYS.map((key) => [
          `button.visionmaster_pro2_${key}`,
          state(`button.visionmaster_pro2_${key}`, power === "unavailable" ? "unavailable" : "unknown"),
        ]),
      ),
    },
    formatEntityState: (stateObj, value) =>
      value !== undefined
        ? (OPTION_LABELS[value] ?? value)
        : (LABELS[stateObj.state] ?? formatStatus(stateObj)),
    callService(domain, service, data) {
      calls.push({ domain, service, data });
      return Promise.resolve();
    },
    ...websocket(),
  };
}

/** A new hass object with one entity changed, as Home Assistant does on an update. */
export function withState(hass, entityId, value, attributes) {
  const old = hass.states[entityId];
  return {
    ...hass,
    states: { ...hass.states, [entityId]: state(entityId, value, attributes ?? old.attributes) },
  };
}

/**
 * A copy of `hass` that keeps only the Valerion projectors in `deviceIds`
 * (other integrations stay), for pages that list projectors.
 */
export function withProjectors(hass, deviceIds) {
  const keep = (entry) => entry.platform !== "valerion" || deviceIds.includes(entry.device_id);
  const entities = Object.fromEntries(Object.entries(hass.entities).filter(([, entry]) => keep(entry)));
  const devices = Object.fromEntries(
    Object.entries(hass.devices).filter(([id]) => deviceIds.includes(id)),
  );
  const states = Object.fromEntries(
    Object.entries(hass.states).filter(([id]) => !hass.entities[id] || id in entities),
  );
  return { ...hass, entities, devices, states };
}

/* ---------- Status and Settings tabs ---------- */

// Entities the Status tab reads:
// [entity_id, translation_key, state when on, state otherwise, attributes].
const STATUS_ENTITIES = [
  ["sensor.visionmaster_pro2_video_signal", "video_signal", "3840×2160p 24 Hz", "unknown"],
  ["sensor.visionmaster_pro2_audio_format", "audio_format", "dolby_atmos", "unknown"],
  ["sensor.visionmaster_pro2_color_depth", "color_depth", "bit_10", "unknown"],
  ["sensor.visionmaster_pro2_color_format", "color_format", "yuv_420", "unknown"],
  ["sensor.visionmaster_pro2_color_primaries", "color_primaries", "bt2020", "unknown"],
  ["sensor.visionmaster_pro2_led_status", "led_status", "normal", "unknown"],
  ["sensor.visionmaster_pro2_awol_link_status", "link_status", "answering", "silent"],
  ["sensor.visionmaster_pro2_fan_1", "fan_speed", "1830", "unknown", { unit_of_measurement: "rpm" }],
  ["sensor.visionmaster_pro2_fan_2", "fan_speed", "1770", "unknown", { unit_of_measurement: "rpm" }],
  ["sensor.visionmaster_pro2_temperature_1", "temperature", "33", "unknown", { unit_of_measurement: "°C" }],
  ["sensor.visionmaster_pro2_temperature_2", "temperature", "48", "unknown", { unit_of_measurement: "°C" }],
  ["number.visionmaster_pro2_laser_level", "laser_level", "8", "unknown", { min: 0, max: 10 }],
];

function statusStates(power) {
  return Object.fromEntries(
    STATUS_ENTITIES.map(([id, , on, other, attributes = {}]) => [
      id,
      state(id, power === "on" ? on : other, attributes),
    ]),
  );
}

// Translated states, as Home Assistant's formatEntityState shows them.
const STATUS_LABELS = {
  unknown: "Unknown",
  dolby_atmos: "Dolby Atmos",
  bit_10: "10-bit",
  yuv_420: "YUV 4:2:0",
  bt2020: "BT.2020",
  normal: "Normal",
  fan_error: "Fan error",
  answering: "Answering",
  silent: "Silent (connected, no reply)",
  no_signal: "No signal",
  hdr10: "HDR10",
};

function formatStatus(stateObj) {
  if (STATUS_LABELS[stateObj.state]) return STATUS_LABELS[stateObj.state];
  const unit = stateObj.attributes.unit_of_measurement;
  return unit ? `${stateObj.state} ${unit}` : stateObj.state;
}

/** The reply of valerion/card_info for this projector. */
export const CARD_INFO = {
  entry_id: "entry_pro2",
  version: "0.1.1",
  model: "VisionMaster Pro2",
  firmware: "V02.01.00E.Q0718",
  setup: {
    wake_on_lan: false,
    security_code: false,
    status_notifications: false,
    notifications_listening: false,
    unsupported_menus: ["lens_shift"],
  },
};

/**
 * callWS with one handler per message type. Tests replace entries of
 * `hass.ws.handlers` and read the messages sent in `hass.ws.calls`.
 */
function websocket() {
  const ws = {
    calls: [],
    handlers: {
      "valerion/card_info": () => structuredClone(CARD_INFO),
    },
  };
  return {
    ws,
    user: { id: "owner", name: "Owner", is_admin: true },
    async callWS(message) {
      ws.calls.push(message);
      const handler = ws.handlers[message.type];
      if (!handler) throw { code: "unknown_command", message: "Unknown command." };
      return handler(message);
    },
  };
}

/* ---------- Remote tab ---------- */

/** The navigation keys; each is a button entity "button.<device>_<key>". */
export const REMOTE_KEYS = ["up", "down", "left", "right", "ok", "return", "menu", "settings", "home"];

/** Media player features: turn on/off, select source, volume set, mute and step. */
export const PLAYER_FEATURES = 128 | 256 | 2048 | 4 | 8 | 1024;

/** Media player attributes besides source and name, as Home Assistant sends them. */
function playerAttributes(power) {
  if (power === "unavailable") return { supported_features: PLAYER_FEATURES };
  const attributes = {
    supported_features: PLAYER_FEATURES,
    source_list: ["Home", "HDMI 1", "HDMI 2", "HDMI 3"],
  };
  // Home Assistant leaves out the volume while a media player is off.
  return power === "off" ? attributes : { ...attributes, volume_level: 0.35, is_volume_muted: false };
}

/* ---------- Picture and Advanced tabs ---------- */

/** Picture modes the Pro2 offers for HDR10 (select.picture_mode options). */
export const HDR_PICTURE_MODES = [
  "HDR Vivid",
  "HDR Standard",
  "HDR Sports",
  "HDR Energy Saving",
  "HDR Game",
  "HDR Theater",
  "FILMMAKER MODE",
  "IMAX Mode",
];

/** The lens menus: buttons "button.<device>_<name>_menu". The Pro2 has no lens shift (unavailable). */
export const LENS_MENUS = ["lens_shift", "zoom", "focus"];

// Setting selects: [entity_id, translation_key, option when on, options].
// Options are the option keys Home Assistant sends. In this HDR10 example
// gamma is locked (a built-in lock), so it is unavailable while on.
export const SETTING_ENTITIES = [
  [
    "select.visionmaster_pro2_aspect_ratio",
    "aspect_ratio",
    "ratio_16_9",
    [
      "auto",
      "ratio_4_3",
      "zoom",
      "ratio_16_9",
      "ratio_21_9",
      "ratio_32_9",
      "anamorphic_16_9",
      "anamorphic_2_39_1",
      "anamorphic_1_85_1",
      "anamorphic_2_0_1",
    ],
  ],
  ["select.visionmaster_pro2_gamma", "gamma", "unavailable", ["gamma_2_0", "gamma_2_2", "gamma_2_4", "bt1886"]],
  ["select.visionmaster_pro2_dynamic_tone_mapping", "dynamic_tone_mapping", "low", ["off", "low", "high"]],
  ["select.visionmaster_pro2_color_temperature", "color_temperature", "standard", ["warm1", "warm2", "standard", "cool"]],
  ["select.visionmaster_pro2_enhanced_black_level", "enhanced_black_level", "medium", ["off", "low", "medium", "high"]],
  [
    "select.visionmaster_pro2_motion_enhancement",
    "motion_enhancement",
    "off",
    ["off", "custom", "film", "clear", "standard", "smooth"],
  ],
];

function settingStates(power) {
  return Object.fromEntries(
    SETTING_ENTITIES.map(([id, , on, options]) => [id, state(id, power === "on" ? on : "unavailable", { options })]),
  );
}

/** Translated option keys, as formatEntityState(stateObj, option) shows them. */
const OPTION_LABELS = {
  auto: "Auto",
  ratio_4_3: "4:3",
  zoom: "Zoom",
  ratio_16_9: "16:9",
  ratio_21_9: "21:9",
  ratio_32_9: "32:9",
  anamorphic_16_9: "Anamorphic 16:9",
  anamorphic_2_39_1: "Anamorphic 2.39:1",
  anamorphic_1_85_1: "Anamorphic 1.85:1",
  anamorphic_2_0_1: "Anamorphic 2.0:1",
  gamma_2_0: "2.0",
  gamma_2_2: "2.2",
  gamma_2_4: "2.4",
  bt1886: "BT.1886",
  smpte2084: "SMPTE 2084 (HDR)",
  hlg: "HLG",
  off: "Off",
  low: "Low",
  medium: "Medium",
  high: "High",
  warm1: "Warm 1",
  warm2: "Warm 2",
  standard: "Standard",
  cool: "Cool",
  custom: "Custom",
  film: "Film",
  clear: "Clear",
  smooth: "Smooth",
};

/* ---------- Picture tab tests ---------- */

/** The scenes valerion/scenes/list returns for a new hass object. */
export const SCENES = [
  {
    id: "scene_movie",
    name: "Movie night",
    settings: { picture_mode: "HDR Theater", laser_level: 6, color_temperature: "warm1", aspect_ratio: "ratio_21_9" },
    entity_id: "scene.visionmaster_pro2_movie_night",
  },
  {
    id: "scene_sports",
    name: "Sports",
    settings: { picture_mode: "HDR Sports", motion_enhancement: "smooth" },
    entity_id: "scene.visionmaster_pro2_sports",
  },
  {
    id: "scene_day",
    name: "Daytime",
    settings: { laser_level: 10, enhanced_black_level: "off" },
    entity_id: "scene.visionmaster_pro2_daytime",
  },
];

Object.assign(STATUS_LABELS, { sdr: "SDR", hlg: "HLG", hdr10_plus: "HDR10+", dolby_vision: "Dolby Vision" });

/**
 * Scene commands on top of the websocket above, with the scenes kept in
 * `hass.ws.scenes`. Save checks the name as scenes.py does; apply applies
 * every setting. Tests replace handlers for other replies.
 */
const pictureBaseWebsocket = websocket;
// makeHass calls websocket() by name, so replacing it adds the scene commands.
websocket = () => {
  const base = pictureBaseWebsocket();
  const { ws } = base;
  ws.scenes = structuredClone(SCENES);
  let next = 1;
  const fail = (code, message) => {
    throw { code, message };
  };
  Object.assign(ws.handlers, {
    "valerion/scenes/list": () => ({ entry_id: "entry_pro2", scenes: structuredClone(ws.scenes) }),
    "valerion/scenes/save": ({ name, scene_id: id, settings }) => {
      const clean = String(name || "").trim();
      if (!clean) fail("invalid_name", "Enter a scene name of 1 to 100 characters.");
      if (ws.scenes.some((s) => s.name.toLowerCase() === clean.toLowerCase() && s.id !== id)) {
        fail("invalid_name", `Another scene of this projector is already called ${clean}.`);
      }
      if (!settings || !Object.keys(settings).length) fail("invalid_settings", "A scene needs at least one picture setting.");
      let scene = ws.scenes.find((s) => s.id === id);
      if (id && !scene) fail("scene_not_found", `This projector has no scene with ID ${id}.`);
      if (!scene) {
        scene = { id: `scene_new_${next++}`, entity_id: null };
        ws.scenes.push(scene);
      }
      Object.assign(scene, { name: clean, settings: structuredClone(settings) });
      return { scene: structuredClone(scene) };
    },
    "valerion/scenes/delete": ({ scene_id: id }) => {
      if (!ws.scenes.some((s) => s.id === id)) fail("scene_not_found", `This projector has no scene with ID ${id}.`);
      ws.scenes = ws.scenes.filter((s) => s.id !== id);
      return null;
    },
    "valerion/scenes/apply": ({ scene_id: id }) => {
      const scene = ws.scenes.find((s) => s.id === id);
      if (!scene) fail("scene_not_found", `This projector has no scene with ID ${id}.`);
      return { applied: Object.keys(scene.settings), skipped: [] };
    },
  });
  return base;
};

/* ---------- Advanced tab tests ---------- */

const ADVANCED_DEVICE = "visionmaster_pro2";

/** Replace states of `hass` (entity_id -> [state, attributes]), as one update. */
function advancedStates(hass, changes) {
  const states = { ...hass.states };
  for (const [id, [value, attributes]] of Object.entries(changes)) {
    states[id] = state(id, value, attributes ?? states[id]?.attributes ?? {});
  }
  return { ...hass, states };
}

/**
 * A projector with all three lens menus, like a VisionMaster Max: the lens
 * shift button is available and card_info reports no unsupported menu.
 */
export function asMaxLens(hass) {
  hass.ws.handlers["valerion/card_info"] = () => ({
    ...structuredClone(CARD_INFO),
    model: "VisionMaster Max",
    setup: { ...CARD_INFO.setup, unsupported_menus: [] },
  });
  const on = hass.states[PLAYER].state === "on";
  return advancedStates(hass, {
    [`button.${ADVANCED_DEVICE}_lens_shift_menu`]: [on ? "unknown" : "unavailable"],
  });
}

/** An SDR signal: gamma can be set, tone mapping is locked. */
export function asSdr(hass) {
  return advancedStates(hass, {
    [`sensor.${ADVANCED_DEVICE}_hdr_format`]: ["SDR"],
    [`sensor.${ADVANCED_DEVICE}_video_signal`]: ["1920×1080p 24 Hz"],
    [`select.${ADVANCED_DEVICE}_picture_mode`]: ["Theater"],
    [`select.${ADVANCED_DEVICE}_gamma`]: ["gamma_2_2"],
    [`select.${ADVANCED_DEVICE}_dynamic_tone_mapping`]: ["unavailable"],
  });
}

/** No signal: no lock is known, so gamma and tone mapping can both be set. */
export function asNoSignal(hass) {
  return advancedStates(hass, {
    [`sensor.${ADVANCED_DEVICE}_hdr_format`]: ["no_signal"],
    [`sensor.${ADVANCED_DEVICE}_video_signal`]: ["unknown"],
    [`select.${ADVANCED_DEVICE}_picture_mode`]: ["Standard"],
    [`select.${ADVANCED_DEVICE}_gamma`]: ["gamma_2_2"],
  });
}

/** Adds the Forget learned locks button entity. */
export function withForgetLocks(hass) {
  const id = `button.${ADVANCED_DEVICE}_forget_learned_locks`;
  const on = hass.states[PLAYER].state === "on";
  return {
    ...hass,
    entities: {
      ...hass.entities,
      [id]: { entity_id: id, device_id: DEVICE_ID, platform: "valerion", translation_key: "forget_learned_locks" },
    },
    states: { ...hass.states, [id]: state(id, on ? "unknown" : "unavailable") },
  };
}
