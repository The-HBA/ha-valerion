// The sheet the Picture and Advanced tabs open: a native dialog above the
// dashboard, closed by Escape, the close button, a tap outside or an action.

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

/** Open a test sheet whose body shows the player's state and counts onClose calls. */
async function openTestSheet(page) {
  await page.evaluate(() => {
    window.sheetClosed = 0;
    window.card.openSheet({
      id: "test",
      title: (ctx) => `Sheet ${ctx.isOn ? "on" : "off"}`,
      render: (ctx) =>
        `<p class="t-state">${ctx.player.state}</p><button class="t-done" data-action="sheet-close">Done</button>`,
      onClose: () => {
        window.sheetClosed += 1;
      },
    });
  });
}

const dialog = (page) => page.locator("valerion-card dialog.sheet");

describe("sheet", () => {
  test("opens above the page with a title and body", async () => {
    const { page, errors } = await openCard(browser, server.url);
    try {
      await openTestSheet(page);
      assert.equal(await dialog(page).evaluate((el) => el.open), true);
      assert.equal(await page.locator("valerion-card .sheet-t").textContent(), "Sheet on");
      assert.equal(await page.locator("valerion-card .t-state").textContent(), "on");
      assert.equal(await page.evaluate(() => window.card.sheetId), "test");
      // On a phone it sits at the bottom, full width.
      const box = await page.locator("valerion-card .sheet-in").boundingBox();
      assert.ok(Math.abs(box.y + box.height - 844) <= 1, `bottom at ${box.y + box.height}`);
      assert.ok(box.width >= 389, `width ${box.width}`);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("renders again when the projector changes", async () => {
    const { page } = await openCard(browser, server.url);
    try {
      await openTestSheet(page);
      await page.evaluate(() => {
        window.card.hass = window.fake.withState(window.card.hass, "media_player.visionmaster_pro2", "standby");
      });
      assert.equal(await page.locator("valerion-card .t-state").textContent(), "standby");
      assert.equal(await page.locator("valerion-card .sheet-t").textContent(), "Sheet off");
    } finally {
      await page.close();
    }
  });

  for (const [how, close] of [
    ["Escape", (page) => page.keyboard.press("Escape")],
    ["the close button", (page) => page.locator("valerion-card .sheet-x").click()],
    ["an action in the body", (page) => page.locator("valerion-card .t-done").click()],
    ["a tap outside", (page) => page.mouse.click(195, 20)],
  ]) {
    test(`closes with ${how} and calls onClose once`, async () => {
      const { page, errors } = await openCard(browser, server.url);
      try {
        await openTestSheet(page);
        await close(page);
        assert.equal(await dialog(page).evaluate((el) => el.open), false);
        assert.equal(await page.evaluate(() => window.sheetClosed), 1);
        assert.equal(await page.evaluate(() => window.card.sheetId), null);
        assert.deepEqual(errors, []);
      } finally {
        await page.close();
      }
    });
  }

  test("a second sheet replaces the first without its onClose", async () => {
    const { page } = await openCard(browser, server.url);
    try {
      await openTestSheet(page);
      await page.evaluate(() =>
        window.card.openSheet({ id: "second", title: "Second", render: () => "<p>two</p>" }),
      );
      assert.equal(await page.evaluate(() => window.sheetClosed), 0);
      assert.equal(await page.evaluate(() => window.card.sheetId), "second");
    } finally {
      await page.close();
    }
  });

  test("is a centred dialog on a wide screen", async () => {
    const { page } = await openCard(browser, server.url, { viewport: { width: 1024, height: 800 } });
    try {
      await openTestSheet(page);
      const box = await page.locator("valerion-card .sheet-in").boundingBox();
      assert.ok(box.width <= 480, `width ${box.width}`);
      assert.ok(Math.abs(box.x + box.width / 2 - 512) <= 2, `centre ${box.x + box.width / 2}`);
      assert.ok(box.y > 0 && box.y + box.height < 800);
    } finally {
      await page.close();
    }
  });
});
