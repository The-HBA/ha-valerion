// Picture and Advanced tabs before their controls exist: what they will hold
// and a way to the device page.

import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";

import { chromium } from "playwright";

import { openCard, startServer } from "./harness.mjs";

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

describe("tabs that come later", () => {
  for (const [tab, title] of [
    ["Picture", "Picture settings"],
    ["Advanced", "Advanced settings"],
  ]) {
    test(`${tab} says where the settings are now`, async () => {
      const { page, errors } = await openCard(browser, server.url, { power: "on" });
      try {
        await page.locator("valerion-card [role=tab]", { hasText: tab }).click();
        const pane = page.locator("valerion-card .pane");
        assert.match(await pane.textContent(), new RegExp(title));
        assert.match(await pane.textContent(), /comes in a later version/);
        await pane.locator("[data-action=valerion-device-page]").click();
        assert.match(await page.evaluate(() => location.pathname), /^\/config\/devices\/device\//);
        assert.deepEqual(errors, []);
      } finally {
        await page.close();
      }
    });
  }
});
