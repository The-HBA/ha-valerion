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
      [PLAYER]: state(PLAYER, power, power === "on" ? { source, friendly_name: name } : { friendly_name: name }),
      "remote.visionmaster_pro2_remote": state("remote.visionmaster_pro2_remote", power === "on" ? "on" : "off"),
      "select.visionmaster_pro2_picture_mode": state("select.visionmaster_pro2_picture_mode", "HDR Theater"),
      "sensor.visionmaster_pro2_hdr_format": state("sensor.visionmaster_pro2_hdr_format", "HDR10"),
      "media_player.visionmaster_max": state("media_player.visionmaster_max", "off"),
      ...statusStates(power),
    },
    formatEntityState: (stateObj) => LABELS[stateObj.state] ?? formatStatus(stateObj),
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
  version: "0.0.22",
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
