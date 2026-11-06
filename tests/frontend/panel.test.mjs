// Browser tests of the Valerion sidebar panel (valerion-panel) with a fake hass.
// Run from this folder: npm ci, then npm test.

import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";

import { chromium } from "playwright";

import { DESKTOP, openPanel, startServer } from "./harness.mjs";

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

const open = (options) => openPanel(browser, server.url, options);
const cardName = (page) => page.locator("valerion-panel valerion-card .vc-name").textContent();
const picker = (page) => page.locator("valerion-panel .picker");

describe("one projector", () => {
  test("shows the card under the top bar, without a picker", async () => {
    const { page, errors } = await open({ projectors: "one" });
    try {
      assert.equal(await page.locator("valerion-panel .title").textContent(), "Projector");
      assert.equal(await cardName(page), "VisionMaster Pro2");
      assert.equal(await picker(page).isVisible(), false);
      assert.equal(await page.locator("valerion-panel .empty").first().isVisible(), false);
      // The card is the real one: its tabs work inside the panel.
      await page.locator("valerion-panel valerion-card [role=tab]", { hasText: "Status" }).click();
      assert.equal(await page.locator("valerion-panel valerion-card .tab-status").count(), 1);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("phone: full width and a menu button that opens the sidebar", async () => {
    const { page } = await open({ projectors: "one" });
    try {
      const menu = page.locator("valerion-panel .menu");
      assert.equal(await menu.isVisible(), true);
      await menu.click();
      assert.equal(await page.evaluate(() => window.menuToggles), 1);
      const box = await page.locator("valerion-panel valerion-card").boundingBox();
      assert.equal(box.x, 8);
      assert.equal(box.width, 390 - 16);
    } finally {
      await page.close();
    }
  });

  test("desktop: no menu button while the sidebar is docked, card centred", async () => {
    const { page } = await open({ projectors: "one", viewport: DESKTOP });
    try {
      assert.equal(await page.locator("valerion-panel .menu").isVisible(), false);
      const panel = await page.locator("valerion-panel").boundingBox();
      const card = await page.locator("valerion-panel valerion-card").boundingBox();
      assert.equal(card.width, 820 - 32);
      const left = card.x - panel.x;
      const right = panel.x + panel.width - (card.x + card.width);
      assert.ok(Math.abs(left - right) < 1, `centred: ${left} vs ${right}`);
    } finally {
      await page.close();
    }
  });

  test("passes every hass update on to the card", async () => {
    const { page } = await open({ projectors: "one", power: "on" });
    try {
      await page.evaluate(() => {
        const { withState } = window.fake;
        window.panel.hass = withState(window.panel.hass, "media_player.visionmaster_pro2", "off");
      });
      assert.equal(await page.locator("valerion-panel valerion-card .vc-sub").textContent(), "Off");
    } finally {
      await page.close();
    }
  });
});

describe("two projectors", () => {
  test("a picker lists both; the choice is remembered in this browser", async () => {
    const { page, errors } = await open({ projectors: "two" });
    try {
      assert.equal(await picker(page).isVisible(), true);
      const select = page.locator("valerion-panel .picker select");
      assert.deepEqual(await select.locator("option").allTextContents(), [
        "VisionMaster Max",
        "VisionMaster Pro2",
      ]);
      // Without a stored choice the first by name is shown.
      assert.equal(await cardName(page), "VisionMaster Max");

      await select.selectOption({ label: "VisionMaster Pro2" });
      await page.locator("valerion-panel valerion-card .vc-name", { hasText: "Pro2" }).waitFor();
      assert.equal(
        await page.evaluate(() => localStorage.getItem("valerion-panel-device")),
        "device_pro2",
      );

      // A later visit opens the chosen projector.
      await page.reload();
      await page.waitForFunction(() => window.panelReady);
      await page.evaluate(() => window.mountPanel({ projectors: "two", narrow: true }));
      await page.locator("valerion-panel valerion-card .vc-name", { hasText: "Pro2" }).waitFor();
      assert.equal(await select.inputValue(), "device_pro2");
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("a stored projector that is gone falls back to the first", async () => {
    const { page } = await open({ projectors: "two", stored: "device_removed" });
    try {
      assert.equal(await cardName(page), "VisionMaster Max");
    } finally {
      await page.close();
    }
  });

  test("works when the browser blocks storage", async () => {
    const page = await browser.newPage({ viewport: DESKTOP });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error));
    await page.addInitScript(() => {
      Object.defineProperty(window, "localStorage", {
        get() {
          throw new Error("blocked");
        },
      });
    });
    try {
      await page.goto(`${server.url}/panel.html`);
      await page.waitForFunction(() => window.panelReady);
      await page.evaluate(() => window.mountPanel({ projectors: "two" }));
      await page.locator("valerion-panel valerion-card .vc-name").waitFor();
      await page.locator("valerion-panel .picker select").selectOption({ label: "VisionMaster Pro2" });
      await page.locator("valerion-panel valerion-card .vc-name", { hasText: "Pro2" }).waitFor();
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });
});

describe("no projector", () => {
  test("a short message instead of the card", async () => {
    const { page, errors } = await open({ projectors: "none" });
    try {
      const empty = page.locator("valerion-panel .empty").first();
      await empty.waitFor();
      assert.match(await empty.textContent(), /No projector yet/);
      assert.equal(await page.locator("valerion-panel valerion-card").count(), 0);
      assert.equal(await picker(page).isVisible(), false);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("the card appears once a projector is added", async () => {
    const { page } = await open({ projectors: "none" });
    try {
      await page.evaluate(() => {
        const { makeHass, withProjectors, DEVICE_ID } = window.fake;
        window.panel.hass = withProjectors(makeHass(), [DEVICE_ID]);
      });
      assert.equal(await cardName(page), "VisionMaster Pro2");
      assert.equal(await page.locator("valerion-panel .empty").first().isVisible(), false);
    } finally {
      await page.close();
    }
  });
});
