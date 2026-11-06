// Browser tests of the card's Remote tab: inputs, keys, hold to repeat, volume.
// Run from this folder: npm ci, then npm test.

import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";

import { chromium } from "playwright";

import { openCard, PHONE, startServer } from "./harness.mjs";

const PLAYER = "media_player.visionmaster_pro2";
const KEY = (name) => `button.visionmaster_pro2_${name}`;

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

/** Open the card and record its haptic and notification events. */
async function open(options) {
  const opened = await openCard(browser, server.url, options);
  await opened.page.evaluate(() => {
    window.events = [];
    for (const type of ["haptic", "hass-notification"]) {
      window.card.addEventListener(type, (ev) => window.events.push({ type, detail: ev.detail }));
    }
  });
  return opened;
}

const calls = (page) => page.evaluate(() => window.card.hass.calls);
const events = (page) => page.evaluate(() => window.events);
const key = (page, name) => page.locator(`valerion-card [data-hold="${name}"]`);
const wait = (page, ms) => page.waitForTimeout(ms);

/** Service calls stay pending until release() in the page resolves them. */
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

/** Change the hass object in the page: fn(hass) returns the new one. */
const updateHass = (page, fn, arg) =>
  page.evaluate(
    ([source, value]) => {
      const update = new Function("hass", "fake", "arg", `return (${source})(hass, fake, arg);`);
      window.card.hass = update(window.card.hass, window.fake, value);
    },
    [fn.toString(), arg],
  );

/** Remove registry entries from the hass object. */
const withoutEntities = (page, ids) =>
  updateHass(
    page,
    (hass, fake, list) => {
      const entities = { ...hass.entities };
      for (const id of list) delete entities[id];
      return { ...hass, entities };
    },
    ids,
  );

async function holdMouse(page, locator, ms) {
  const box = await locator.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await wait(page, ms);
  await page.mouse.up();
}

describe("remote tab: states", () => {
  test("on: inputs, D-pad, keys and volume", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      const options = page.locator("valerion-card .rm-in .rm-opt");
      assert.deepEqual(await options.allTextContents(), ["Home", "HDMI 1", "HDMI 2", "HDMI 3"]);
      assert.equal(await options.nth(1).getAttribute("aria-pressed"), "true");
      assert.equal(await page.locator("valerion-card .rm-in .sel").count(), 1);
      const dpad = page.locator("valerion-card .rm-dpad [data-hold]");
      assert.deepEqual(
        await dpad.evaluateAll((els) => els.map((el) => el.dataset.hold)),
        ["up", "left", "right", "down", "ok"],
      );
      assert.deepEqual(await page.locator("valerion-card .rm-keys .rm-key").allTextContents(), [
        "Back",
        "Home",
        "Menu",
        "Settings",
      ]);
      assert.equal(await page.locator("valerion-card .rm-vol .rm-v").textContent(), "35");
      assert.equal(await page.locator("valerion-card [data-slider]").getAttribute("aria-valuenow"), "35");
      assert.equal(await page.locator("valerion-card .tab-remote button:disabled").count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  for (const power of ["off", "standby"]) {
    test(`${power}: everything shown, disabled and dimmed, nothing sent`, async () => {
      const { page, errors } = await open({ power });
      try {
        const pane = page.locator("valerion-card .pane");
        assert.equal(await pane.evaluate((el) => getComputedStyle(el).opacity), "0.35");
        const buttons = page.locator("valerion-card .tab-remote button");
        assert.ok((await buttons.count()) >= 15);
        assert.equal(await page.locator("valerion-card .tab-remote button:enabled").count(), 0);
        // No input is selected while the projector is off.
        assert.equal(await page.locator("valerion-card .rm-in .sel").count(), 0);
        assert.equal(await page.locator("valerion-card [data-slider]").getAttribute("tabindex"), "-1");
        await key(page, "up").evaluate((el) => {
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

  test("unavailable: no inputs, keys disabled, no errors", async () => {
    const { page, errors } = await open({ power: "unavailable" });
    try {
      assert.equal(await page.locator("valerion-card .rm-in").count(), 0);
      assert.equal(await key(page, "ok").isDisabled(), true);
      assert.equal(await page.locator("valerion-card .tab-remote button:enabled").count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("a key whose button is unavailable is disabled while on", async () => {
    const { page } = await open({ power: "on" });
    try {
      await updateHass(page, (hass, fake, id) => fake.withState(hass, id, "unavailable"), KEY("menu"));
      assert.equal(await key(page, "menu").isDisabled(), true);
      assert.equal(await key(page, "home").isDisabled(), false);
    } finally {
      await page.close();
    }
  });
});

describe("remote tab: only what exists", () => {
  test("a key without its button falls back to the remote entity", async () => {
    const { page } = await open({ power: "on" });
    try {
      await withoutEntities(page, [KEY("up")]);
      await key(page, "up").click();
      assert.deepEqual(await calls(page), [
        {
          domain: "remote",
          service: "send_command",
          data: { entity_id: "remote.visionmaster_pro2_remote", command: "up" },
        },
      ]);
    } finally {
      await page.close();
    }
  });

  test("a key with neither button nor remote is left out", async () => {
    const { page } = await open({ power: "on" });
    try {
      await withoutEntities(page, [KEY("up"), KEY("settings"), "remote.visionmaster_pro2_remote"]);
      assert.equal(await key(page, "up").count(), 0);
      assert.equal(await key(page, "settings").count(), 0);
      assert.equal(await key(page, "down").count(), 1);
      assert.equal(await page.locator("valerion-card .rm-keys").getAttribute("style"), "--n:3");
    } finally {
      await page.close();
    }
  });

  test("no keys and no remote: no D-pad group; no source list: no inputs", async () => {
    const { page, errors } = await open({ power: "on" });
    try {
      const keys = ["up", "down", "left", "right", "ok", "return", "menu", "settings", "home"];
      await withoutEntities(page, [...keys.map(KEY), "remote.visionmaster_pro2_remote"]);
      assert.equal(await page.locator("valerion-card .rm-pad").count(), 0);
      await updateHass(page, (hass, fake, id) => {
        const { source_list, ...rest } = hass.states[id].attributes;
        return fake.withState(hass, id, "on", rest);
      }, PLAYER);
      assert.equal(await page.locator("valerion-card .rm-in").count(), 0);
      // The volume still works through the media player.
      assert.equal(await page.locator("valerion-card .rm-vol").count(), 1);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });
});

describe("remote tab: inputs", () => {
  test("a tap selects the input and fires a haptic", async () => {
    const { page } = await open({ power: "on" });
    try {
      await page.locator("valerion-card .rm-opt", { hasText: "HDMI 2" }).click();
      assert.deepEqual(await calls(page), [
        { domain: "media_player", service: "select_source", data: { entity_id: PLAYER, source: "HDMI 2" } },
      ]);
      assert.deepEqual(await events(page), [{ type: "haptic", detail: "selection" }]);
      assert.equal(
        await page.locator("valerion-card .rm-opt", { hasText: "HDMI 2" }).getAttribute("aria-pressed"),
        "true",
      );
      // The selected input sends nothing.
      await page.locator("valerion-card .rm-opt", { hasText: "HDMI 2" }).click();
      assert.equal((await calls(page)).length, 1);
    } finally {
      await page.close();
    }
  });
});

describe("remote tab: keys", () => {
  const KEYS = [
    ["up", "key_up"],
    ["down", "key_down"],
    ["left", "key_left"],
    ["right", "key_right"],
    ["ok", "key_ok"],
    ["return", "key_return"],
    ["home", "key_home"],
    ["menu", "key_menu"],
    ["settings", "key_settings"],
  ];

  test("a tap presses the key's button once, with a haptic", async () => {
    const { page } = await open({ power: "on" });
    try {
      for (const [name] of KEYS) await key(page, name).click();
      assert.deepEqual(
        await calls(page),
        KEYS.map(([name]) => ({ domain: "button", service: "press", data: { entity_id: KEY(name) } })),
      );
      const haptics = (await events(page)).filter((ev) => ev.type === "haptic");
      assert.equal(haptics.length, KEYS.length);
      assert.equal(haptics[0].detail, "light");
    } finally {
      await page.close();
    }
  });

  test("touch: a tap sends, a cancelled touch (scrolling) does not", async () => {
    const { page } = await open({ power: "on" });
    try {
      const touch = (types) =>
        key(page, "down").evaluate((el, list) => {
          const init = { bubbles: true, composed: true, pointerId: 9, pointerType: "touch", isPrimary: true };
          for (const type of list) el.dispatchEvent(new PointerEvent(type, { ...init, button: 0 }));
        }, types);
      await touch(["pointerdown", "pointerup"]);
      await touch(["pointerdown", "pointercancel"]);
      await wait(page, 600);
      assert.deepEqual(await calls(page), [
        { domain: "button", service: "press", data: { entity_id: KEY("down") } },
      ]);
    } finally {
      await page.close();
    }
  });

  test("leaving the key before release sends nothing", async () => {
    const { page } = await open({ power: "on" });
    try {
      const box = await key(page, "left").boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x + box.width / 2, box.y - 150, { steps: 4 });
      await wait(page, 700);
      await page.mouse.up();
      assert.deepEqual(await calls(page), []);
      assert.equal(await page.locator("valerion-card .held").count(), 0);
    } finally {
      await page.close();
    }
  });

  test("holding an arrow repeats it until release", async () => {
    const { page } = await open({ power: "on" });
    try {
      await holdMouse(page, key(page, "up"), 1100);
      const count = (await calls(page)).length;
      assert.ok(count >= 3 && count <= 6, `${count} presses in 1.1 s`);
      assert.ok((await calls(page)).every((call) => call.data.entity_id === KEY("up")));
      await wait(page, 500);
      assert.equal((await calls(page)).length, count, "kept sending after release");
      const haptics = (await events(page)).filter((ev) => ev.type === "haptic");
      assert.equal(haptics.length, 1, "one haptic per press, not per repeat");
    } finally {
      await page.close();
    }
  });

  test("holding OK sends it once, not again and again", async () => {
    const { page } = await open({ power: "on" });
    try {
      await holdMouse(page, key(page, "ok"), 1100);
      await wait(page, 300);
      assert.deepEqual(await calls(page), [
        { domain: "button", service: "press", data: { entity_id: KEY("ok") } },
      ]);
    } finally {
      await page.close();
    }
  });

  test("a repeat waits for the previous call to return", async () => {
    const { page } = await open({ power: "on" });
    try {
      await gateCalls(page);
      const box = await key(page, "right").boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await wait(page, 1200);
      assert.equal((await calls(page)).length, 1, "sent again before the call returned");
      await releaseCalls(page);
      await wait(page, 400);
      assert.equal((await calls(page)).length, 2);
      await wait(page, 600);
      assert.equal((await calls(page)).length, 2, "sent again before the call returned");
      await page.mouse.up();
      await releaseCalls(page);
      await wait(page, 500);
      assert.equal((await calls(page)).length, 2, "sent after release");
    } finally {
      await page.close();
    }
  });

  test("a failed call shows a toast and stops the repeat", async () => {
    const { page } = await open({ power: "on" });
    try {
      await page.evaluate(() => {
        const { hass } = window.card;
        hass.callService = (domain, service, data) => {
          hass.calls.push({ domain, service, data });
          return Promise.reject(new Error("The projector is off."));
        };
      });
      await holdMouse(page, key(page, "down"), 1100);
      assert.equal((await calls(page)).length, 1);
      const toasts = (await events(page)).filter((ev) => ev.type === "hass-notification");
      assert.deepEqual(toasts, [{ type: "hass-notification", detail: { message: "The projector is off." } }]);
    } finally {
      await page.close();
    }
  });

  test("keyboard: Enter sends once, a held Space repeats", async () => {
    const { page } = await open({ power: "on" });
    try {
      await key(page, "home").focus();
      await page.keyboard.press("Enter");
      await wait(page, 100);
      assert.deepEqual(await calls(page), [
        { domain: "button", service: "press", data: { entity_id: KEY("home") } },
      ]);
      await page.evaluate(() => window.card.hass.calls.splice(0));
      await key(page, "down").focus();
      await page.keyboard.down(" ");
      await wait(page, 1100);
      await page.keyboard.up(" ");
      const count = (await calls(page)).length;
      assert.ok(count >= 3 && count <= 6, `${count} presses in 1.1 s`);
      await wait(page, 400);
      assert.equal((await calls(page)).length, count);
    } finally {
      await page.close();
    }
  });

  test("the hold survives a render of the pane", async () => {
    const { page } = await open({ power: "on" });
    try {
      const box = await key(page, "volume_up").boundingBox();
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await wait(page, 600);
      const mark = () =>
        page.evaluate(() => {
          window.card.shadowRoot.querySelector(".pane .tab").dataset.mark = "1";
        });
      await mark();
      await updateHass(page, (hass, fake, id) =>
        fake.withState(hass, id, "on", { ...hass.states[id].attributes, volume_level: 0.4 }), PLAYER);
      const rendered = await page.evaluate(
        () => window.card.shadowRoot.querySelector(".pane .tab").dataset.mark !== "1",
      );
      assert.equal(rendered, true, "the pane was not rendered again");
      assert.equal(await key(page, "volume_up").evaluate((el) => el.classList.contains("held")), true);
      const before = (await calls(page)).length;
      await wait(page, 500);
      assert.ok((await calls(page)).length > before, "stopped repeating after the render");
      await page.mouse.up();
      const count = (await calls(page)).length;
      await wait(page, 400);
      assert.equal((await calls(page)).length, count);
      assert.ok((await calls(page)).every((call) => call.service === "volume_up"));
    } finally {
      await page.close();
    }
  });
});

describe("remote tab: focus", () => {
  test("a held Space and the focus survive a render of the pane", async () => {
    const { page } = await open({ power: "on" });
    try {
      await key(page, "volume_up").focus();
      await page.keyboard.down(" ");
      await wait(page, 500);
      await updateHass(page, (hass, fake, id) =>
        fake.withState(hass, id, "on", { ...hass.states[id].attributes, volume_level: 0.4 }), PLAYER);
      const focused = () =>
        page.evaluate(() => window.card.shadowRoot.activeElement?.dataset.hold ?? null);
      assert.equal(await focused(), "volume_up");
      const before = (await calls(page)).length;
      await wait(page, 500);
      assert.ok((await calls(page)).length > before, "stopped repeating after the render");
      await page.keyboard.up(" ");
      const count = (await calls(page)).length;
      await wait(page, 400);
      assert.equal((await calls(page)).length, count);
    } finally {
      await page.close();
    }
  });

  test("moving the focus away stops a held key", async () => {
    const { page } = await open({ power: "on" });
    try {
      await key(page, "down").focus();
      await page.keyboard.down("Enter");
      await page.evaluate(() => window.card.shadowRoot.querySelector('[data-hold="up"]').focus());
      await wait(page, 800);
      await page.keyboard.up("Enter");
      assert.equal((await calls(page)).length, 1);
    } finally {
      await page.close();
    }
  });
});

describe("remote tab: volume", () => {
  test("minus, plus and mute", async () => {
    const { page } = await open({ power: "on" });
    try {
      await key(page, "volume_down").click();
      await key(page, "volume_up").click();
      await page.locator("valerion-card [data-action=remote-mute]").click();
      assert.deepEqual(await calls(page), [
        { domain: "media_player", service: "volume_down", data: { entity_id: PLAYER } },
        { domain: "media_player", service: "volume_up", data: { entity_id: PLAYER } },
        { domain: "media_player", service: "volume_mute", data: { entity_id: PLAYER, is_volume_muted: true } },
      ]);
      await updateHass(page, (hass, fake, id) =>
        fake.withState(hass, id, "on", { ...hass.states[id].attributes, is_volume_muted: true }), PLAYER);
      assert.equal(await page.locator("valerion-card .rm-vol .rm-v").textContent(), "Muted");
      const mute = page.locator("valerion-card [data-action=remote-mute]");
      assert.equal(await mute.getAttribute("aria-pressed"), "true");
      await mute.click();
      assert.deepEqual((await calls(page)).at(-1).data, { entity_id: PLAYER, is_volume_muted: false });
    } finally {
      await page.close();
    }
  });

  test("the slider sets the volume on release, and with the arrow keys", async () => {
    const { page } = await open({ power: "on" });
    try {
      const slider = page.locator("valerion-card [data-slider]");
      const box = await slider.boundingBox();
      const at = (f) => box.x + 9 + f * (box.width - 18);
      const y = box.y + box.height / 2;
      await page.mouse.move(at(0.2), y);
      await page.mouse.down();
      await page.mouse.move(at(0.5), y, { steps: 5 });
      await page.mouse.move(at(0.75), y, { steps: 5 });
      assert.deepEqual(await calls(page), [], "sent while dragging");
      assert.equal(await page.locator("valerion-card .rm-vol .rm-v").textContent(), "75");
      await page.mouse.up();
      assert.deepEqual(await calls(page), [
        { domain: "media_player", service: "volume_set", data: { entity_id: PLAYER, volume_level: 0.75 } },
      ]);
      // The new value stays until Home Assistant reports it.
      await updateHass(page, (hass, fake) => fake.withState(hass, "light.ceiling", "off"));
      assert.equal(await slider.getAttribute("aria-valuenow"), "75");
      await updateHass(page, (hass, fake, id) =>
        fake.withState(hass, id, "on", { ...hass.states[id].attributes, volume_level: 0.75 }), PLAYER);
      await page.evaluate(() => window.card.hass.calls.splice(0));
      await slider.focus();
      await page.keyboard.press("ArrowRight");
      await page.keyboard.press("End");
      assert.deepEqual(
        (await calls(page)).map((call) => call.data.volume_level),
        [0.76, 1],
      );
    } finally {
      await page.close();
    }
  });
});

describe("remote tab: fits one phone screen", () => {
  const measure = (page) =>
    page.evaluate(() => {
      const pane = window.card.shadowRoot.querySelector(".pane");
      const paneBox = pane.getBoundingClientRect();
      const groups = [...pane.querySelectorAll(".rm-grp")].map((el) => el.getBoundingClientRect());
      return {
        bottom: window.card.getBoundingClientRect().bottom,
        pageHeight: document.scrollingElement.scrollHeight,
        pageWidth: document.scrollingElement.scrollWidth,
        paneHeight: pane.clientHeight,
        paneContent: pane.scrollHeight,
        groupsInside: groups.every((box) => box.bottom <= paneBox.bottom + 0.5 && box.right <= paneBox.right + 0.5),
        groups: groups.length,
      };
    });

  for (const power of ["on", "standby", "off"]) {
    test(`390x844, ${power}: whole card visible, nothing cut off`, async () => {
      const { page } = await open({ power, viewport: PHONE });
      try {
        const box = await measure(page);
        assert.equal(box.groups, 3);
        assert.ok(box.bottom <= PHONE.height, `card ends at ${box.bottom}px`);
        assert.ok(box.pageHeight <= PHONE.height, `page is ${box.pageHeight}px high`);
        assert.ok(box.pageWidth <= PHONE.width, `page is ${box.pageWidth}px wide`);
        assert.ok(box.paneContent <= box.paneHeight, "pane content is cut off");
        assert.ok(box.groupsInside, "a group reaches out of the pane");
      } finally {
        await page.close();
      }
    });
  }

  test("390x844 with six inputs still fits", async () => {
    const { page } = await open({ power: "on", viewport: PHONE });
    try {
      await updateHass(page, (hass, fake, id) => {
        const attributes = hass.states[id].attributes;
        const sources = [...attributes.source_list, "Input 34", "Input 35"];
        return fake.withState(hass, id, "on", { ...attributes, source_list: sources });
      }, PLAYER);
      assert.equal(await page.locator("valerion-card .rm-opt").count(), 6);
      const box = await measure(page);
      assert.ok(box.paneContent <= box.paneHeight, "pane content is cut off");
      assert.ok(box.groupsInside, "a group reaches out of the pane");
      assert.ok(box.pageWidth <= PHONE.width);
    } finally {
      await page.close();
    }
  });

  test("wide: D-pad on the left, inputs and volume on the right", async () => {
    const { page } = await open({ power: "on", viewport: { width: 820, height: 1000 } });
    try {
      await page.evaluate(() => {
        document.getElementById("view").style.maxWidth = "none";
      });
      const boxes = await page.evaluate(() =>
        Object.fromEntries(
          ["rm-in", "rm-pad", "rm-vol"].map((name) => {
            const box = window.card.shadowRoot.querySelector(`.${name}`).getBoundingClientRect();
            return [name, { x: box.x, y: box.y, bottom: box.bottom }];
          }),
        ),
      );
      assert.ok(boxes["rm-pad"].x < boxes["rm-in"].x);
      assert.equal(boxes["rm-in"].x, boxes["rm-vol"].x);
      assert.ok(boxes["rm-vol"].y > boxes["rm-in"].bottom);
      const box = await measure(page);
      assert.ok(box.paneContent <= box.paneHeight, "pane content is cut off");
    } finally {
      await page.close();
    }
  });
});
