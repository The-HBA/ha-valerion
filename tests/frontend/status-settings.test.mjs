// Browser tests of the card's Status and Settings tabs with a fake hass.
// Run from this folder: npm ci, then npm test.

import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";

import { chromium } from "playwright";

import { openCard, PHONE, startServer } from "./harness.mjs";

let browser;
let server;

before(async () => {
  server = await startServer();
  browser = await chromium.launch();
});

after(async () => {
  await browser?.close();
  await server?.close();
});

const open = (options) => openCard(browser, server.url, options);
const tab = (page, label) => page.locator("valerion-card [role=tab]", { hasText: label }).click();
const texts = (page, selector) => page.locator(`valerion-card .pane ${selector}`).allTextContents();

/** Rows of the pane as [label, value]. */
const rows = (page) =>
  page.evaluate(() =>
    [...window.card.shadowRoot.querySelectorAll(".pane .ss-row")].map((row) => [
      row.querySelector(".ss-n").textContent,
      row.querySelector(".ss-v").textContent,
    ]),
  );

/** Give the card a new hass with `change(hass)` applied, as Home Assistant does on updates. */
const update = (page, change) =>
  page.evaluate((source) => {
    const hass = { ...window.card.hass, states: { ...window.card.hass.states } };
    hass.entities = { ...hass.entities };
    // eslint-disable-next-line no-new-func
    new Function("hass", source)(hass);
    window.card.hass = hass;
  }, change);

/** The hint rows of the Settings tab, once card_info has answered. */
async function hints(page) {
  await page.locator("valerion-card .pane .ss-hint:not(.ss-quiet)").first().waitFor();
  return page.evaluate(() =>
    [...window.card.shadowRoot.querySelectorAll(".pane .ss-hint")].map((hint) => ({
      kind: hint.className.replace(/.*ss-(ok|warn|info).*/, "$1"),
      text: hint.querySelector(".ss-n > div").textContent,
      todo: hint.querySelector("small")?.textContent ?? "",
    })),
  );
}

describe("status tab", () => {
  test("on: the signal on top, the projector below", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      await tab(page, "Status");
      assert.deepEqual(await texts(page, ".ss-kick"), ["Now playing on HDMI 1"]);
      assert.deepEqual(await texts(page, ".ss-big"), ["4K HDR10"]);
      assert.deepEqual(await texts(page, ".ss-sub"), ["3840×2160p 24 Hz · HDR Theater"]);
      assert.deepEqual(await texts(page, ".ss-chip"), ["Dolby Atmos", "10-bit", "YUV 4:2:0", "BT.2020"]);
      assert.deepEqual(await rows(page), [
        ["Power", "On"],
        ["AWOL Link", "Answering"],
        ["LED status", "Normal"],
        ["Laser level", "8 of 10"],
        ["Fans", "1830, 1770 rpm"],
        ["Temperatures", "33, 48 °C"],
      ]);
      // Status stays usable while off, so it is never dimmed.
      assert.equal(await page.locator("valerion-card .pane.dim").count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("off: nothing playing, values unknown", async () => {
    const { page, errors } = await open({ power: "off" });
    try {
      await tab(page, "Status");
      assert.deepEqual(await texts(page, ".ss-big"), ["Nothing"]);
      assert.deepEqual(await texts(page, ".ss-sub"), ["The projector is off."]);
      assert.equal(await page.locator("valerion-card .pane .ss-chip").count(), 0);
      const found = Object.fromEntries(await rows(page));
      assert.equal(found.Power, "Off");
      assert.equal(found["AWOL Link"], "Silent (connected, no reply)");
      assert.equal(found.Fans, "Unknown");
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("on without a signal", async () => {
    const { page } = await open({ power: "on" });
    try {
      await tab(page, "Status");
      await update(
        page,
        `hass.states["sensor.visionmaster_pro2_video_signal"] = { ...hass.states["sensor.visionmaster_pro2_video_signal"], state: "unknown" };
         hass.states["sensor.visionmaster_pro2_hdr_format"] = { ...hass.states["sensor.visionmaster_pro2_hdr_format"], state: "no_signal" };`,
      );
      assert.deepEqual(await texts(page, ".ss-big"), ["No signal"]);
      assert.deepEqual(await texts(page, ".ss-sub"), ["Nothing comes in on HDMI 1."]);
    } finally {
      await page.close();
    }
  });

  test("shows nothing for entities that do not exist, flags an LED problem", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      await tab(page, "Status");
      await update(
        page,
        `for (const id of Object.keys(hass.entities)) {
           if (/fan|temperature|laser|color|audio/.test(id)) delete hass.entities[id];
         }
         hass.states["sensor.visionmaster_pro2_led_status"] = { ...hass.states["sensor.visionmaster_pro2_led_status"], state: "fan_error" };`,
      );
      assert.deepEqual(await rows(page), [
        ["Power", "On"],
        ["AWOL Link", "Answering"],
        ["LED status", "Fan error"],
      ]);
      assert.equal(await page.locator("valerion-card .pane .ss-v.ss-bad").textContent(), "Fan error");
      assert.equal(await page.locator("valerion-card .pane .ss-chip").count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("the last instant update, when instant updates are on", async () => {
    const { page } = await open({ power: "on" });
    try {
      await tab(page, "Status");
      const id = "sensor.visionmaster_pro2_last_status_notification";
      await update(
        page,
        `hass.entities["${id}"] = { entity_id: "${id}", device_id: "device_pro2", platform: "valerion", translation_key: "last_status_notification" };
         hass.states["${id}"] = { entity_id: "${id}", state: "unknown", attributes: {} };`,
      );
      assert.deepEqual((await rows(page)).at(-1), ["Last instant update", "None yet"]);
      const when = new Date();
      when.setHours(21, 3, 0, 0);
      await update(page, `hass.states["${id}"] = { entity_id: "${id}", state: "${when.toISOString()}", attributes: {} };`);
      const [label, value] = (await rows(page)).at(-1);
      assert.equal(label, "Last instant update");
      assert.match(value, /^(21:03|09:03\s?PM)$/);
    } finally {
      await page.close();
    }
  });
});

describe("settings tab", () => {
  test("asks card_info once and shows the setup hints", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      await tab(page, "Settings");
      assert.deepEqual(await hints(page), [
        {
          kind: "warn",
          text: "No MAC address set.",
          todo: "It cannot wake from deep standby. Add it with the gear button on the integration's entry.",
        },
        {
          kind: "info",
          text: "Instant updates are off.",
          todo: "Turn them on with the gear button on the integration's entry.",
        },
        { kind: "info", text: "No security code set.", todo: "Only needed when AWOL Link asks for one." },
        {
          kind: "info",
          text: "No lens shift menu on this model.",
          todo: "Wrong? Use Forget learned locks on the device page.",
        },
      ]);
      assert.deepEqual(await rows(page), [
        ["Model", "VisionMaster Pro2"],
        ["Firmware", "V02.01.00E.Q0718"],
        ["Integration", "0.0.22"],
      ]);
      const links = await page.evaluate(() =>
        [...window.card.shadowRoot.querySelectorAll(".pane a")].map((a) => [a.textContent, a.href, a.target]),
      );
      assert.deepEqual(links, [
        ["Documentation", "https://github.com/The-HBA/ha-valerion", "_blank"],
        ["Report a problem", "https://github.com/The-HBA/ha-valerion/issues", "_blank"],
      ]);

      // A state change renders the tab again without asking again.
      await update(page, `hass.states["light.ceiling"] = { ...hass.states["light.ceiling"], state: "off" };`);
      await update(
        page,
        `hass.states["sensor.visionmaster_pro2_led_status"] = { ...hass.states["sensor.visionmaster_pro2_led_status"], state: "fan_error" };`,
      );
      const calls = () => page.evaluate(() => window.card.hass.ws.calls);
      assert.deepEqual(await calls(), [{ type: "valerion/card_info", device_id: "device_pro2" }]);
      // Opening the tab again asks again (the entry may have been reloaded).
      await tab(page, "Status");
      await tab(page, "Settings");
      await hints(page);
      assert.equal((await calls()).length, 2);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("another projector in the card asks again", async () => {
    const { page } = await open({ power: "on" });
    try {
      await tab(page, "Settings");
      await hints(page);
      await page.evaluate(() => window.card.setConfig({ type: "custom:valerion-card", device_id: "device_max" }));
      await page.waitForFunction(() => window.card.hass.ws.calls.length === 2);
      assert.deepEqual((await page.evaluate(() => window.card.hass.ws.calls)).at(-1), {
        type: "valerion/card_info",
        device_id: "device_max",
      });
    } finally {
      await page.close();
    }
  });

  test("hints when everything is set up, and unsupported menus", async () => {
    const { page } = await open({ power: "on" });
    try {
      await page.evaluate(() => {
        window.card.hass.ws.handlers["valerion/card_info"] = () => ({
          entry_id: "entry_pro2",
          version: "0.0.22",
          model: "VisionMaster Max",
          firmware: null,
          setup: {
            wake_on_lan: true,
            security_code: true,
            status_notifications: true,
            notifications_listening: true,
            unsupported_menus: ["lens_shift", "zoom", "focus"],
          },
        });
      });
      await tab(page, "Settings");
      assert.deepEqual(
        (await hints(page)).map(({ kind, text }) => [kind, text]),
        [
          ["ok", "Wake-on-LAN is set up."],
          ["ok", "Instant updates are on."],
          ["ok", "Security code is set."],
          ["info", "No lens shift, zoom or focus menu on this model."],
        ],
      );
      // No firmware known: its row is left out.
      assert.deepEqual(await rows(page), [
        ["Model", "VisionMaster Max"],
        ["Integration", "0.0.22"],
      ]);
    } finally {
      await page.close();
    }
  });

  test("instant updates on but not listening", async () => {
    const { page } = await open({ power: "on" });
    try {
      await page.evaluate(() => {
        const reply = window.card.hass.ws.handlers["valerion/card_info"]();
        reply.setup.status_notifications = true;
        window.card.hass.ws.handlers["valerion/card_info"] = () => reply;
      });
      await tab(page, "Settings");
      assert.deepEqual((await hints(page))[1], {
        kind: "warn",
        text: "Instant updates cannot start.",
        todo: "Port 4352 is in use. See Settings, Repairs.",
      });
    } finally {
      await page.close();
    }
  });

  test("a failed card_info shows a quiet note and the device registry's details", async () => {
    const { page, errors } = await open({ power: "off" });
    try {
      await page.evaluate(() => {
        const { hass } = window.card;
        hass.ws.handlers["valerion/card_info"] = () => {
          throw { code: "projector_not_found", message: "Not found" };
        };
        hass.devices.device_pro2.model = "VisionMaster Pro2";
        hass.devices.device_pro2.sw_version = "V02.01.00E.Q0718";
      });
      await tab(page, "Settings");
      const note = page.locator("valerion-card .pane .ss-quiet");
      await note.filter({ hasText: "not available" }).waitFor();
      assert.equal(await note.textContent(), "Setup details are not available right now.");
      assert.deepEqual(await rows(page), [
        ["Model", "VisionMaster Pro2"],
        ["Firmware", "V02.01.00E.Q0718"],
      ]);
      assert.equal(await page.locator("valerion-card .pane a").count(), 2);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("a hass without callWS fails quietly too", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      await update(page, `delete hass.callWS;`);
      await tab(page, "Settings");
      await page.locator("valerion-card .pane .ss-quiet", { hasText: "not available" }).waitFor();
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("the device page button, for administrators only", async () => {
    const { page } = await open({ power: "on" });
    try {
      await tab(page, "Settings");
      await hints(page);
      const button = page.locator("valerion-card .pane [data-action=valerion-device-page]");
      const navigated = page.evaluate(
        () => new Promise((resolve) => window.addEventListener("location-changed", () => resolve(location.pathname))),
      );
      await button.click();
      assert.equal(await navigated, "/config/devices/device/device_pro2");

      await update(page, `hass.user = { ...hass.user, is_admin: false };`);
      await tab(page, "Status");
      await tab(page, "Settings");
      await hints(page);
      assert.equal(await button.count(), 0);
    } finally {
      await page.close();
    }
  });
});

describe("fits one phone screen", () => {
  test("Status and Settings fit with every row and hint shown", async () => {
    const { page } = await open({ power: "on", viewport: PHONE });
    try {
      await page.evaluate(() => {
        const reply = window.card.hass.ws.handlers["valerion/card_info"]();
        reply.setup.status_notifications = true;
        reply.setup.unsupported_menus = ["lens_shift", "zoom", "focus"];
        window.card.hass.ws.handlers["valerion/card_info"] = () => reply;
      });
      const id = "sensor.visionmaster_pro2_last_status_notification";
      await update(
        page,
        `hass.entities["${id}"] = { entity_id: "${id}", device_id: "device_pro2", platform: "valerion", translation_key: "last_status_notification" };
         hass.states["${id}"] = { entity_id: "${id}", state: "2026-11-01T21:03:00Z", attributes: {} };`,
      );
      for (const label of ["Status", "Settings"]) {
        await tab(page, label);
        if (label === "Settings") await hints(page);
        const box = await page.evaluate(() => {
          const pane = window.card.shadowRoot.querySelector(".pane");
          const tabEl = pane.querySelector(".tab");
          const overflowing = [...pane.querySelectorAll(".ss-v, .ss-big, .ss-sub, .ss-btn")].filter(
            (el) => el.scrollWidth > el.clientWidth + 1,
          ).length;
          return {
            bottom: window.card.getBoundingClientRect().bottom,
            pageWidth: document.scrollingElement.scrollWidth,
            paneHeight: pane.clientHeight,
            paneContent: pane.scrollHeight,
            tabContent: tabEl.scrollHeight,
            overflowing,
          };
        });
        assert.ok(box.bottom <= PHONE.height, `${label}: card ends at ${box.bottom}px`);
        assert.ok(box.pageWidth <= PHONE.width, `${label}: page is ${box.pageWidth}px wide`);
        assert.ok(box.paneContent <= box.paneHeight, `${label}: pane content is cut off`);
        assert.ok(box.tabContent <= box.paneHeight, `${label}: tab content is ${box.tabContent}px high`);
        assert.equal(box.overflowing, 0, `${label}: a text is cut off`);
      }
    } finally {
      await page.close();
    }
  });

  test("two columns on a tablet", async () => {
    const { page } = await open({ power: "on", viewport: { width: 820, height: 1180 } });
    try {
      // The test page is a phone-sized column; a sections dashboard is wider.
      await page.evaluate(() => {
        document.getElementById("view").style.maxWidth = "800px";
      });
      for (const label of ["Status", "Settings"]) {
        await tab(page, label);
        const tops = await page.evaluate(() =>
          [...window.card.shadowRoot.querySelectorAll(".pane .ss-grp")].map((el) => el.getBoundingClientRect().top),
        );
        assert.equal(tops.length, 2);
        assert.equal(tops[0], tops[1], `${label}: groups side by side`);
      }
    } finally {
      await page.close();
    }
  });
});
