// A small stand-in for the `hass` object Home Assistant gives a card.
// Only what the card reads: states, entities (the entity registry as the
// frontend sees it), devices, callService and formatEntityState.

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
    ...REMOTE_KEYS.map((key) => entry(`button.visionmaster_pro2_${key}`, DEVICE_ID, "valerion", `key_${key}`)),
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
      "select.visionmaster_pro2_picture_mode": state("select.visionmaster_pro2_picture_mode", "HDR Theater"),
      "sensor.visionmaster_pro2_hdr_format": state("sensor.visionmaster_pro2_hdr_format", "HDR10"),
      "media_player.visionmaster_max": state("media_player.visionmaster_max", "off"),
      ...Object.fromEntries(
        REMOTE_KEYS.map((key) => [
          `button.visionmaster_pro2_${key}`,
          state(`button.visionmaster_pro2_${key}`, power === "unavailable" ? "unavailable" : "unknown"),
        ]),
      ),
    },
    formatEntityState: (stateObj) => LABELS[stateObj.state] ?? stateObj.state,
    callService(domain, service, data) {
      calls.push({ domain, service, data });
      return Promise.resolve();
    },
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
