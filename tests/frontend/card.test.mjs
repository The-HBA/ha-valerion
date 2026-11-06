// Browser tests of the Valerion card (custom:valerion-card) with a fake hass.
// Run from this folder: npm ci, then npm test.

import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";

import { chromium } from "playwright";

import { openCard, PHONE, startServer } from "./harness.mjs";

const TABS = ["Remote", "Picture", "Advanced", "Status", "Settings"];

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

describe("header and tabs", () => {
  test("shows the projector, its state and five tabs", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      assert.equal(await page.locator("valerion-card .vc-name").textContent(), "VisionMaster Pro2");
      assert.equal(await page.locator("valerion-card .vc-sub").textContent(), "On · HDMI 1");
      const tabs = page.locator("valerion-card [role=tab]");
      assert.deepEqual(await tabs.allTextContents(), TABS);
      assert.equal(await tabs.first().getAttribute("aria-selected"), "true");
      assert.equal(await page.locator("valerion-card .notice").isVisible(), false);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("a tab click shows its pane", async () => {
    const { page } = await open({ power: "on" });
    try {
      await page.locator("valerion-card [role=tab]", { hasText: "Advanced" }).click();
      assert.equal(
        await page.locator("valerion-card [role=tab][aria-selected=true]").textContent(),
        "Advanced",
      );
      assert.equal(await page.locator("valerion-card .pane .tab-advanced").count(), 1);
      // Arrow keys move between tabs, as in any tab list.
      await page.keyboard.press("ArrowRight");
      assert.equal(await page.locator("valerion-card .pane .tab-status").count(), 1);
    } finally {
      await page.close();
    }
  });
});

describe("off and standby", () => {
  for (const [power, text] of [
    ["off", "Off. Turn it on to use the controls."],
    ["standby", "In standby. Turn it on to use the controls."],
  ]) {
    test(`${power}: notice, dimmed controls, power and tabs usable`, async () => {
      const { page } = await open({ power });
      try {
        assert.equal(await page.locator("valerion-card .notice").textContent(), text);
        const pane = page.locator("valerion-card .pane");
        assert.equal(await pane.evaluate((el) => getComputedStyle(el).opacity), "0.35");
        assert.equal(await pane.evaluate((el) => getComputedStyle(el).pointerEvents), "none");
        const power = page.locator("valerion-card .power");
        assert.equal(await power.isEnabled(), true);
        assert.equal(await power.evaluate((el) => getComputedStyle(el).opacity), "1");
        // Status and Settings stay usable while the projector is off.
        await page.locator("valerion-card [role=tab]", { hasText: "Status" }).click();
        assert.equal(await pane.evaluate((el) => getComputedStyle(el).opacity), "1");
      } finally {
        await page.close();
      }
    });
  }

  test("unavailable: power button disabled", async () => {
    const { page } = await open({ power: "unavailable" });
    try {
      assert.equal(await page.locator("valerion-card .power").isEnabled(), false);
      assert.equal(await page.locator("valerion-card .notice").textContent(), "Not reachable right now.");
    } finally {
      await page.close();
    }
  });
});

describe("power button", () => {
  for (const [power, service] of [
    ["on", "turn_off"],
    ["standby", "turn_on"],
    ["off", "turn_on"],
  ]) {
    test(`${power} calls media_player.${service}`, async () => {
      const { page } = await open({ power });
      try {
        await page.locator("valerion-card .power").click();
        const calls = await page.evaluate(() => window.card.hass.calls);
        assert.deepEqual(calls, [
          {
            domain: "media_player",
            service,
            data: { entity_id: "media_player.visionmaster_pro2" },
          },
        ]);
      } finally {
        await page.close();
      }
    });
  }
});

describe("updates", () => {
  test("renders again only when the projector's entities change", async () => {
    const { page } = await open({ power: "on" });
    try {
      const marked = () =>
        page.evaluate(() => window.card.shadowRoot.querySelector(".pane .tab").dataset.mark === "1");
      await page.evaluate(() => {
        window.card.shadowRoot.querySelector(".pane .tab").dataset.mark = "1";
      });
      // Another integration's light changes: nothing to do.
      await page.evaluate(() => {
        window.card.hass = window.fake.withState(window.card.hass, "light.ceiling", "off");
      });
      assert.equal(await marked(), true);
      // The projector goes to standby: header and pane follow.
      await page.evaluate(() => {
        const { hass } = window.card;
        window.card.hass = window.fake.withState(hass, "media_player.visionmaster_pro2", "standby", {});
      });
      assert.equal(await marked(), false);
      assert.equal(await page.locator("valerion-card .vc-sub").textContent(), "Standby");
      assert.equal(await page.locator("valerion-card .notice").isVisible(), true);
    } finally {
      await page.close();
    }
  });
});

describe("fits one phone screen", () => {
  for (const power of ["on", "off"]) {
    test(`every tab fits 390x844 without scrolling (${power})`, async () => {
      const { page } = await open({ power, viewport: PHONE });
      try {
        for (const label of TABS) {
          await page.locator("valerion-card [role=tab]", { hasText: label }).click();
          const box = await page.evaluate(() => {
            const pane = window.card.shadowRoot.querySelector(".pane");
            return {
              bottom: window.card.getBoundingClientRect().bottom,
              right: window.card.getBoundingClientRect().right,
              pageHeight: document.scrollingElement.scrollHeight,
              pageWidth: document.scrollingElement.scrollWidth,
              paneHeight: pane.clientHeight,
              paneContent: pane.scrollHeight,
            };
          });
          assert.ok(box.bottom <= PHONE.height, `${label}: card ends at ${box.bottom}px`);
          assert.ok(box.pageHeight <= PHONE.height, `${label}: page is ${box.pageHeight}px high`);
          assert.ok(box.pageWidth <= PHONE.width, `${label}: page is ${box.pageWidth}px wide`);
          assert.ok(box.paneContent <= box.paneHeight, `${label}: pane content is cut off`);
        }
      } finally {
        await page.close();
      }
    });
  }

  test("every tab has the same height", async () => {
    const { page } = await open({ power: "on" });
    try {
      const heights = new Set();
      for (const label of TABS) {
        await page.locator("valerion-card [role=tab]", { hasText: label }).click();
        heights.add(await page.evaluate(() => window.card.getBoundingClientRect().height));
      }
      assert.equal(heights.size, 1);
    } finally {
      await page.close();
    }
  });
});

describe("card API", () => {
  test("needs a device, suggests the first projector, lists itself", async () => {
    const { page } = await open({ power: "on" });
    try {
      const result = await page.evaluate(() => {
        const Card = customElements.get("valerion-card");
        let error = "";
        try {
          document.createElement("valerion-card").setConfig({ type: "custom:valerion-card" });
        } catch (err) {
          error = err.message;
        }
        return {
          error,
          stub: Card.getStubConfig(window.fake.makeHass()),
          grid: window.card.getGridOptions(),
          listed: window.customCards.filter((c) => c.type === "valerion-card").length,
        };
      });
      assert.match(result.error, /device_id/);
      assert.deepEqual(result.stub, { device_id: "device_pro2" });
      assert.equal(result.grid.columns, 12);
      assert.equal(result.listed, 1);
    } finally {
      await page.close();
    }
  });

  test("the editor offers Valerion projectors and reports changes", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      const result = await page.evaluate(async () => {
        const Card = customElements.get("valerion-card");
        const editor = await Card.getConfigElement();
        editor.setConfig({ type: "custom:valerion-card", device_id: "device_pro2" });
        editor.hass = window.card.hass;
        document.body.append(editor);
        const form = editor.querySelector("ha-form");
        const changed = new Promise((resolve) =>
          editor.addEventListener("config-changed", (ev) => resolve(ev.detail.config)),
        );
        form.dispatchEvent(
          new CustomEvent("value-changed", { detail: { value: { device_id: "device_max" } } }),
        );
        return { schema: form.schema, data: form.data, config: await changed };
      });
      assert.deepEqual(result.schema[0].selector, {
        device: { filter: { integration: "valerion" } },
      });
      assert.deepEqual(result.data, { type: "custom:valerion-card", device_id: "device_pro2" });
      assert.deepEqual(result.config, { type: "custom:valerion-card", device_id: "device_max" });
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });
});
