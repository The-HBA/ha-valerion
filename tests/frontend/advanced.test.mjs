// Browser tests of the card's Advanced tab: settings, laser level, lens menus and the lens sheet.
// Run from this folder: npm ci, then npm test.

import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";

import { chromium } from "playwright";

import { openCard, PHONE, startServer } from "./harness.mjs";

const DEV = "visionmaster_pro2";
const LASER = `number.${DEV}_laser_level`;
const KEY = (name) => `button.${DEV}_${name}`;
const RETURN = { domain: "button", service: "press", data: { entity_id: KEY("return") } };
const MENU = (name) => ({ domain: "button", service: "press", data: { entity_id: KEY(`${name}_menu`) } });

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

/**
 * Open the card on the Advanced tab. `variants` are helpers of fake-hass.js
 * applied first: "max" (three lens menus), "sdr", "noSignal", "forget".
 */
async function open(options = {}, variants = []) {
  const opened = await openCard(browser, server.url, options);
  const { page } = opened;
  if (options.wide) await page.addStyleTag({ content: ".view{max-width:none}" });
  await page.evaluate(async (list) => {
    const fake = await import("/fake-hass.js");
    const helpers = { max: fake.asMaxLens, sdr: fake.asSdr, noSignal: fake.asNoSignal, forget: fake.withForgetLocks };
    let hass = window.card.hass;
    for (const name of list) hass = helpers[name](hass);
    window.card.hass = hass;
    window.events = [];
    window.card.addEventListener("hass-notification", (ev) => window.events.push(ev.detail));
  }, variants);
  await page.locator("valerion-card [role=tab]", { hasText: "Advanced" }).click();
  // card_info arrives and the lens group renders again.
  await page.waitForFunction(() => window.card._cardInfo && !window.card._cardInfo.pending);
  await page.waitForTimeout(150);
  return opened;
}

const $ = (page, selector) => page.locator(`valerion-card ${selector}`);
const calls = (page) => page.evaluate(() => window.card.hass.calls);
const clearCalls = (page) => page.evaluate(() => window.card.hass.calls.splice(0));
const wait = (page, ms) => page.waitForTimeout(ms);
const waitCalls = (page, count) =>
  page.waitForFunction((n) => window.card.hass.calls.length >= n, count, { timeout: 3000 });

/** Change the hass object in the page: fn(hass, fake, arg) returns the new one. */
const updateHass = (page, fn, arg) =>
  page.evaluate(
    ([source, value]) => {
      const update = new Function("hass", "fake", "arg", `return (${source})(hass, fake, arg);`);
      window.card.hass = update(window.card.hass, window.fake, value);
    },
    [fn.toString(), arg],
  );

const setLaser = (page, value) =>
  updateHass(page, (hass, fake, v) => fake.withState(hass, "number.visionmaster_pro2_laser_level", v), value);

/** Service calls stay pending until releaseCalls() resolves them. */
const gateCalls = (page) =>
  page.evaluate(() => {
    const { hass } = window.card;
    window.gate = [];
    hass.callService = (domain, service, data) => {
      hass.calls.push({ domain, service, data });
      return new Promise((resolve) => window.gate.push(resolve));
    };
  });
const releaseCalls = (page) =>
  page.evaluate(() => {
    for (const resolve of window.gate.splice(0)) resolve();
  });

const groupTitles = (page) => $(page, ".tab-advanced .vc-t").allTextContents();
const selected = (page, key) =>
  $(page, `.vc-opt.sel[data-entity="select.${DEV}_${key}"]`).allTextContents();
const lensKeys = (page) => $(page, ".ad-lens [data-menu]").evaluateAll((els) => els.map((el) => el.dataset.menu));

async function holdMouse(page, locator, ms) {
  const box = await locator.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await wait(page, ms);
  await page.mouse.up();
}

/** The pane shows everything without scrolling, inside a 390x844 phone. */
async function assertFits(page, label) {
  const box = await page.evaluate(() => {
    const pane = window.card.shadowRoot.querySelector(".pane");
    return {
      bottom: window.card.getBoundingClientRect().bottom,
      pageWidth: document.scrollingElement.scrollWidth,
      paneHeight: pane.clientHeight,
      paneContent: pane.scrollHeight,
      paneWidth: pane.clientWidth,
      paneContentWidth: pane.scrollWidth,
    };
  });
  assert.ok(box.bottom <= PHONE.height, `${label}: card ends at ${box.bottom}px`);
  assert.ok(box.pageWidth <= PHONE.width, `${label}: page is ${box.pageWidth}px wide`);
  assert.ok(box.paneContent <= box.paneHeight, `${label}: pane content ${box.paneContent} > ${box.paneHeight}`);
  assert.ok(box.paneContentWidth <= box.paneWidth, `${label}: pane content is too wide`);
}

describe("advanced tab: what it shows", () => {
  test("HDR10: signal line, laser, settings with selections, gamma locked", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      assert.equal(await $(page, ".ad-sig").textContent(), "Settings for HDR10 · 3840×2160p 24 Hz");
      assert.deepEqual(await groupTitles(page), [
        "Laser level",
        "Enhanced black level",
        "Dynamic tone mapping",
        "Motion enhancement",
      ]);
      assert.equal(await $(page, ".ad-lv").textContent(), "8");
      assert.equal(await $(page, "[data-ad-slider]").getAttribute("aria-valuenow"), "8");
      assert.equal(await $(page, ".ad-tick").count(), 9);
      assert.deepEqual(await selected(page, "enhanced_black_level"), ["Medium"]);
      assert.deepEqual(await selected(page, "dynamic_tone_mapping"), ["Low"]);
      assert.deepEqual(await selected(page, "motion_enhancement"), ["Off"]);
      assert.deepEqual(
        await $(page, `[data-entity="select.${DEV}_motion_enhancement"]`).allTextContents(),
        ["Off", "Custom", "Film", "Clear", "Standard", "Smooth"],
      );
      // Gamma is locked in HDR10: no group, named in the locked line.
      assert.equal(await $(page, `[data-entity="select.${DEV}_gamma"]`).count(), 0);
      assert.equal(await $(page, ".vc-lock").textContent(), "Locked for HDR10 in HDR Theater: Gamma");
      assert.equal(await $(page, ".ad-forget").count(), 0);
      assert.equal(await $(page, ".tab-advanced button:disabled").count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("SDR: gamma shown, tone mapping locked", async () => {
    const { page, errors } = await open({ power: "on" }, ["sdr"]);
    try {
      assert.equal(await $(page, ".ad-sig").textContent(), "Settings for SDR · 1920×1080p 24 Hz");
      assert.deepEqual(await groupTitles(page), ["Laser level", "Enhanced black level", "Gamma", "Motion enhancement"]);
      assert.deepEqual(
        await $(page, `[data-entity="select.${DEV}_gamma"]`).allTextContents(),
        ["2.0", "2.2", "2.4", "BT.1886"],
      );
      assert.deepEqual(await selected(page, "gamma"), ["2.2"]);
      assert.equal(await $(page, `[data-entity="select.${DEV}_dynamic_tone_mapping"]`).count(), 0);
      assert.equal(await $(page, ".vc-lock").textContent(), "Locked for SDR in Theater: Tone mapping");
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("tapping an option calls select.select_option", async () => {
    const { page } = await open({ power: "on" });
    try {
      await $(page, `[data-entity="select.${DEV}_enhanced_black_level"][data-option="high"]`).click();
      assert.deepEqual(await calls(page), [
        {
          domain: "select",
          service: "select_option",
          data: { entity_id: `select.${DEV}_enhanced_black_level`, option: "high" },
        },
      ]);
      assert.deepEqual(await selected(page, "enhanced_black_level"), ["High"]);
    } finally {
      await page.close();
    }
  });

  test("Forget learned locks sits beside the locked line and presses its button", async () => {
    const { page } = await open({ power: "on" }, ["forget"]);
    try {
      const forget = $(page, ".ad-lock .ad-forget");
      assert.equal(await forget.getAttribute("aria-label"), "Forget learned locks");
      await forget.click();
      assert.deepEqual(await calls(page), [
        { domain: "button", service: "press", data: { entity_id: KEY("forget_learned_locks") } },
      ]);
    } finally {
      await page.close();
    }
  });

  for (const power of ["off", "standby"]) {
    test(`${power}: everything drawn, no selection, all disabled, nothing sent`, async () => {
      const { page, errors } = await open({ power });
      try {
        assert.equal(await $(page, ".pane").evaluate((el) => getComputedStyle(el).opacity), "0.35");
        assert.equal(await $(page, ".ad-sig").count(), 0);
        assert.equal(await $(page, ".vc-lock").count(), 0);
        assert.deepEqual(await groupTitles(page), [
          "Laser level",
          "Enhanced black level",
          "Dynamic tone mapping",
          "Gamma",
          "Motion enhancement",
        ]);
        assert.equal(await $(page, ".tab-advanced .sel").count(), 0);
        assert.equal(await $(page, ".tab-advanced button:enabled").count(), 0);
        assert.equal(await $(page, ".ad-lv").textContent(), "");
        const slider = $(page, "[data-ad-slider]");
        assert.equal(await slider.getAttribute("tabindex"), "-1");
        assert.equal(await slider.getAttribute("aria-disabled"), "true");
        // The Pro2 has no lens shift (card_info), even while its button cannot tell.
        assert.deepEqual(await lensKeys(page), ["zoom", "focus"]);
        await $(page, "[data-ad-step='1']").evaluate((el) => {
          const init = { bubbles: true, composed: true, pointerId: 3, isPrimary: true, button: 0 };
          el.dispatchEvent(new PointerEvent("pointerdown", init));
          el.dispatchEvent(new PointerEvent("pointerup", init));
        });
        await wait(page, 500);
        assert.deepEqual(await calls(page), []);
        assert.deepEqual(errors, []);
      } finally {
        await page.close();
      }
    });
  }
});

describe("advanced tab: laser level", () => {
  test("a drag shows the value and sends one number.set_value on release", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      const box = await $(page, "[data-ad-slider]").boundingBox();
      const y = box.y + box.height / 2;
      await page.mouse.move(box.x + box.width * 0.8, y);
      await page.mouse.down();
      for (const f of [0.6, 0.45, 0.3]) {
        await page.mouse.move(box.x + box.width * f, y, { steps: 3 });
      }
      assert.deepEqual(await calls(page), []);
      assert.equal(await $(page, ".ad-lv").textContent(), "3");
      await page.mouse.up();
      await waitCalls(page, 1);
      await wait(page, 100);
      assert.deepEqual(await calls(page), [
        { domain: "number", service: "set_value", data: { entity_id: LASER, value: 3 } },
      ]);
      assert.equal(await $(page, "[data-ad-slider]").getAttribute("aria-valuenow"), "3");
      // A render before the projector reports the new value keeps it shown.
      await updateHass(page, (hass, fake) => fake.withState(hass, "sensor.visionmaster_pro2_fan_1", "1900"));
      assert.equal(await $(page, ".ad-lv").textContent(), "3");
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("minus and plus send one step down and up", async () => {
    const { page } = await open({ power: "on" });
    try {
      await $(page, "[data-ad-step='-1']").click();
      await waitCalls(page, 1);
      assert.deepEqual((await calls(page)).map((c) => c.data.value), [7]);
      await setLaser(page, "7");
      await $(page, "[data-ad-step='1']").click();
      await waitCalls(page, 2);
      await $(page, "[data-ad-step='1']").click();
      await waitCalls(page, 3);
      assert.deepEqual((await calls(page)).map((c) => c.data.value), [7, 8, 9]);
      assert.ok((await calls(page)).every((c) => c.service === "set_value" && c.data.entity_id === LASER));
    } finally {
      await page.close();
    }
  });

  test("holding plus repeats, one call at a time, and stops at the maximum", async () => {
    const { page } = await open({ power: "on" });
    try {
      await setLaser(page, "2");
      await gateCalls(page);
      const plus = $(page, "[data-ad-step='1']");
      const box = await plus.boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await wait(page, 900);
      // The first call has not returned: nothing more is sent.
      assert.deepEqual((await calls(page)).map((c) => c.data.value), [3]);
      // Released calls return at once from here on.
      await page.evaluate(() => {
        const { hass } = window.card;
        hass.callService = (domain, service, data) => {
          hass.calls.push({ domain, service, data });
          return Promise.resolve();
        };
      });
      await releaseCalls(page);
      await wait(page, 2200);
      await page.mouse.up();
      await wait(page, 300);
      const values = (await calls(page)).map((c) => c.data.value);
      assert.deepEqual(values, [3, 4, 5, 6, 7, 8, 9, 10]);
      assert.equal(await $(page, ".ad-lv").textContent(), "10");
    } finally {
      await page.close();
    }
  });

  test("keyboard: arrows, Home and End; the value stays within 0 to 10", async () => {
    const { page } = await open({ power: "on" });
    try {
      await $(page, "[data-ad-slider]").focus();
      const values = async () => (await calls(page)).map((c) => c.data.value);
      await page.keyboard.press("ArrowRight");
      await waitCalls(page, 1);
      await page.keyboard.press("End");
      await waitCalls(page, 2);
      await page.keyboard.press("ArrowRight");
      await page.keyboard.press("ArrowUp");
      await wait(page, 100);
      assert.deepEqual(await values(), [9, 10]);
      await page.keyboard.press("Home");
      await waitCalls(page, 3);
      await page.keyboard.press("ArrowLeft");
      await page.keyboard.press("ArrowDown");
      await wait(page, 100);
      assert.deepEqual(await values(), [9, 10, 0]);
      assert.equal(await $(page, "[data-ad-slider]").getAttribute("aria-valuenow"), "0");
      // The focus stays on the slider when the pane renders again.
      await updateHass(page, (hass, fake) => fake.withState(hass, "sensor.visionmaster_pro2_fan_1", "1900"));
      assert.equal(
        await page.evaluate(() => window.card.shadowRoot.activeElement?.hasAttribute("data-ad-slider")),
        true,
      );
    } finally {
      await page.close();
    }
  });

  test("values sent while a call is on its way: only the newest follows", async () => {
    const { page } = await open({ power: "on" });
    try {
      await gateCalls(page);
      await $(page, "[data-ad-slider]").focus();
      for (let i = 0; i < 4; i++) await page.keyboard.press("ArrowLeft");
      assert.deepEqual((await calls(page)).map((c) => c.data.value), [7]);
      await releaseCalls(page);
      await waitCalls(page, 2);
      await releaseCalls(page);
      await wait(page, 100);
      assert.deepEqual((await calls(page)).map((c) => c.data.value), [7, 4]);
    } finally {
      await page.close();
    }
  });
});

describe("advanced tab: lens menus", () => {
  test("Pro2: zoom and focus only (lens shift unavailable and unsupported)", async () => {
    const { page } = await open({ power: "on" });
    try {
      assert.deepEqual(await lensKeys(page), ["zoom", "focus"]);
      assert.deepEqual(await $(page, ".ad-lens [data-menu]").allTextContents(), ["Zoom", "Focus"]);
    } finally {
      await page.close();
    }
  });

  test("a projector with all three menus shows all three", async () => {
    const { page } = await open({ power: "on" }, ["max"]);
    try {
      assert.deepEqual(await lensKeys(page), ["lens_shift", "zoom", "focus"]);
      assert.deepEqual(await $(page, ".ad-lens [data-menu]").allTextContents(), ["Lens shift", "Zoom", "Focus"]);
    } finally {
      await page.close();
    }
  });

  test("a menu missing from card_info is left out although its button is available", async () => {
    const { page } = await open({ power: "on" }, ["max"]);
    try {
      await page.evaluate(() => {
        window.card._cardInfo.data.setup.unsupported_menus = ["focus"];
        window.card._renderPane();
      });
      assert.deepEqual(await lensKeys(page), ["lens_shift", "zoom"]);
    } finally {
      await page.close();
    }
  });
});

describe("advanced tab: lens sheet", () => {
  const sheetOpen = (page) => $(page, "dialog.sheet").evaluate((el) => el.open);

  test("Zoom presses the zoom menu and opens the sheet with its keys", async () => {
    const { page, errors } = await open({ power: "on" }, ["max"]);
    try {
      await $(page, ".ad-lens [data-menu='zoom']").click();
      await waitCalls(page, 1);
      assert.deepEqual(await calls(page), [MENU("zoom")]);
      assert.equal(await sheetOpen(page), true);
      assert.equal(await page.evaluate(() => window.card.sheetId), "lens");
      assert.equal(await $(page, ".sheet-t").textContent(), "Zoom");
      assert.match(await $(page, ".ad-instr").textContent(), /^Left and right zoom in and out\./);
      assert.deepEqual(
        await $(page, ".ad-sw [data-menu]").evaluateAll((els) => els.map((el) => [el.dataset.menu, el.getAttribute("aria-pressed")])),
        [["lens_shift", "false"], ["zoom", "true"], ["focus", "false"]],
      );
      assert.deepEqual(
        await $(page, ".ad-dpad [data-hold]").evaluateAll((els) => els.map((el) => el.dataset.hold)),
        ["up", "left", "right", "down", "ok"],
      );
      assert.deepEqual(await $(page, ".ad-skeys .rm-key").allTextContents(), ["Back", "Menu"]);
      assert.equal(await $(page, ".ad-sheet button:disabled").count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("Focus: left and right only, no Menu key; one menu: no switcher", async () => {
    const { page } = await open({ power: "on" });
    try {
      await page.evaluate(() => {
        window.card._cardInfo.data.setup.unsupported_menus = ["lens_shift", "zoom"];
        window.card._renderPane();
      });
      await $(page, ".ad-lens [data-menu='focus']").click();
      assert.equal(await $(page, ".sheet-t").textContent(), "Focus");
      assert.equal(
        await $(page, ".ad-instr").textContent(),
        "Left and right adjust the focus. Stop when text on screen is sharp.",
      );
      assert.deepEqual(
        await $(page, ".ad-dpad [data-hold]").evaluateAll((els) => els.map((el) => el.dataset.hold)),
        ["left", "right", "ok"],
      );
      assert.deepEqual(await $(page, ".ad-skeys .rm-key").allTextContents(), ["Back"]);
      assert.equal(await $(page, ".ad-sw").count(), 0);
    } finally {
      await page.close();
    }
  });

  test("a held arrow in the sheet repeats until release", async () => {
    const { page } = await open({ power: "on" }, ["max"]);
    try {
      await $(page, ".ad-lens [data-menu='zoom']").click();
      await waitCalls(page, 1);
      await clearCalls(page);
      await holdMouse(page, $(page, ".ad-dpad [data-hold='right']"), 1000);
      await wait(page, 100);
      const presses = await calls(page);
      assert.ok(presses.length >= 3, `${presses.length} presses`);
      assert.ok(presses.every((c) => c.data.entity_id === KEY("right")));
    } finally {
      await page.close();
    }
  });

  test("switching menu sends Return, then presses the other menu", async () => {
    const { page } = await open({ power: "on" }, ["max"]);
    try {
      await $(page, ".ad-lens [data-menu='zoom']").click();
      await waitCalls(page, 1);
      await gateCalls(page);
      await $(page, ".ad-sw [data-menu='focus']").click();
      assert.equal(await $(page, ".sheet-t").textContent(), "Focus");
      assert.match(await $(page, ".ad-instr").textContent(), /adjust the focus/);
      await wait(page, 100);
      // One after the other: the menu waits for Return to return.
      assert.deepEqual(await calls(page), [MENU("zoom"), RETURN]);
      await releaseCalls(page);
      await waitCalls(page, 3);
      await releaseCalls(page);
      assert.deepEqual(await calls(page), [MENU("zoom"), RETURN, MENU("focus")]);
    } finally {
      await page.close();
    }
  });

  for (const [how, close] of [
    ["Done", (page) => $(page, ".ad-done").click()],
    ["Escape", (page) => page.keyboard.press("Escape")],
    ["the close button", (page) => $(page, ".sheet-x").click()],
    ["a tap outside", (page) => page.mouse.click(195, 20)],
  ]) {
    test(`${how} closes the sheet and sends Return once`, async () => {
      const { page, errors } = await open({ power: "on" }, ["max"]);
      try {
        await $(page, ".ad-lens [data-menu='zoom']").click();
        await waitCalls(page, 1);
        await close(page);
        await waitCalls(page, 2);
        await wait(page, 200);
        assert.equal(await sheetOpen(page), false);
        assert.deepEqual(await calls(page), [MENU("zoom"), RETURN]);
        assert.deepEqual(errors, []);
      } finally {
        await page.close();
      }
    });
  }

  test("the projector turning off disables the keys; Done then sends nothing", async () => {
    const { page } = await open({ power: "on" }, ["max"]);
    try {
      await $(page, ".ad-lens [data-menu='zoom']").click();
      await waitCalls(page, 1);
      await updateHass(page, (hass, fake) => fake.withState(hass, "media_player.visionmaster_pro2", "standby", {}));
      assert.equal(await $(page, ".ad-dpad [data-hold]:enabled").count(), 0);
      assert.equal(await $(page, ".ad-skeys button:enabled").count(), 0);
      assert.equal(await $(page, ".ad-sw button:enabled").count(), 0);
      await $(page, ".ad-done").click();
      await wait(page, 200);
      assert.equal(await sheetOpen(page), false);
      assert.deepEqual(await calls(page), [MENU("zoom")]);
    } finally {
      await page.close();
    }
  });

  for (const viewport of [PHONE, { width: 820, height: 1180 }]) {
    test(`fits ${viewport.width}x${viewport.height} without scrolling`, async () => {
      const { page } = await open({ power: "on", viewport }, ["max"]);
      try {
        await $(page, ".ad-lens [data-menu='zoom']").click();
        const box = await page.evaluate(() => {
          const body = window.card.shadowRoot.querySelector(".sheet-body");
          const rect = window.card.shadowRoot.querySelector(".sheet-in").getBoundingClientRect();
          return { top: rect.top, bottom: rect.bottom, client: body.clientHeight, content: body.scrollHeight };
        });
        assert.ok(box.content <= box.client, `sheet content ${box.content} > ${box.client}`);
        assert.ok(box.top >= 0 && box.bottom <= viewport.height, `sheet from ${box.top} to ${box.bottom}`);
      } finally {
        await page.close();
      }
    });
  }
});

describe("advanced tab: fits one phone screen", () => {
  for (const [label, power, variants] of [
    ["HDR10, three lens menus, Forget", "on", ["max", "forget"]],
    ["SDR, three lens menus, Forget", "on", ["max", "sdr", "forget"]],
    ["no signal: gamma and tone mapping both shown", "on", ["max", "noSignal"]],
    ["off", "off", ["max"]],
    ["standby", "standby", ["max"]],
  ]) {
    test(`390x844, ${label}`, async () => {
      const { page } = await open({ power, viewport: PHONE }, variants);
      try {
        await assertFits(page, label);
      } finally {
        await page.close();
      }
    });
  }

  test("from 600 px wide: two columns", async () => {
    const { page } = await open({ power: "on", viewport: { width: 820, height: 1180 }, wide: true }, ["max"]);
    try {
      const black = await $(page, `.vc-grp:has([data-entity="select.${DEV}_enhanced_black_level"])`).boundingBox();
      const tone = await $(page, `.vc-grp:has([data-entity="select.${DEV}_dynamic_tone_mapping"])`).boundingBox();
      const motion = await $(page, `.vc-grp:has([data-entity="select.${DEV}_motion_enhancement"])`).boundingBox();
      assert.equal(Math.round(black.y), Math.round(tone.y));
      assert.ok(tone.x > black.x + black.width);
      assert.ok(motion.width > black.width * 1.8);
      // Motion in one row of six.
      const ys = await $(page, `[data-entity="select.${DEV}_motion_enhancement"]`).evaluateAll((els) =>
        new Set(els.map((el) => Math.round(el.getBoundingClientRect().y))).size,
      );
      assert.equal(ys, 1);
      const pane = await page.evaluate(() => {
        const el = window.card.shadowRoot.querySelector(".pane");
        return [el.scrollHeight, el.clientHeight];
      });
      assert.ok(pane[0] <= pane[1]);
    } finally {
      await page.close();
    }
  });
});
