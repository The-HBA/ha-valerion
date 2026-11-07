// The Picture tab: picture mode, color temperature, aspect ratio and the
// scenes with their editor (a sheet).

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

const CT = "select.visionmaster_pro2_color_temperature";
const AR = "select.visionmaster_pro2_aspect_ratio";
const MODE = "select.visionmaster_pro2_picture_mode";
const HDR = "sensor.visionmaster_pro2_hdr_format";
const VIDEO = "sensor.visionmaster_pro2_video_signal";

/**
 * Open the card on the Picture tab. `prepare(hass)` runs in the page before
 * the tab opens (it is a function body as a string, with `hass` in scope).
 * Toasts are collected in window.toasts.
 */
async function openPicture(options = {}, prepare = "") {
  const opened = await openCard(browser, server.url, options);
  const { page } = opened;
  await page.evaluate((body) => {
    window.toasts = [];
    window.addEventListener("hass-notification", (ev) => window.toasts.push(ev.detail.message));
    new Function("hass", body)(window.card.hass);
  }, prepare);
  await page.locator("valerion-card [role=tab]", { hasText: "Picture" }).click();
  return opened;
}

/** Set one entity's state as Home Assistant does: a new hass object. */
const setState = (page, entityId, value, attributes) =>
  page.evaluate(
    ([id, v, a]) => {
      window.card.hass = window.fake.withState(window.card.hass, id, v, a ?? undefined);
    },
    [entityId, value, attributes ?? null],
  );

const pane = (page) => page.locator("valerion-card .pane");
const pressed = (page, scope) =>
  page.locator(`valerion-card ${scope} .vc-opt[aria-pressed=true]`).evaluateAll((els) => els.map((el) => el.dataset.option));
const wsCalls = (page, type) =>
  page.evaluate((t) => window.card.hass.ws.calls.filter((c) => c.type === t), type);
const toasts = async (page) => {
  await page.waitForFunction(() => window.toasts.length > 0);
  return page.evaluate(() => window.toasts);
};
const sheet = (page) => page.locator("valerion-card dialog.sheet");
const chips = (page) => page.locator("valerion-card .pane .pc-sc .pc-chip").allTextContents();

describe("picture settings", () => {
  test("groups show the current values", async () => {
    const { page, errors } = await openPicture();
    try {
      assert.deepEqual(await pressed(page, ".pc-mode"), ["HDR Theater"]);
      assert.deepEqual(await pressed(page, ".pc-ct"), ["standard"]);
      assert.deepEqual(await pressed(page, ".pc-ar"), ["ratio_16_9"]);
      assert.equal(await page.locator("valerion-card .pc-badge").textContent(), "HDR10");
      assert.match(await page.locator("valerion-card .pc-sub").textContent(), /^For HDR10 on HDMI 1\./);
      assert.equal(await page.locator("valerion-card .pc-mode .vc-opt").count(), 8);
      assert.equal(await page.locator("valerion-card .pc-ar .vc-opt").count(), 10);
      assert.equal(await page.locator("valerion-card .pc-ar .vc-v").textContent(), "16:9");
      assert.equal(await page.locator("valerion-card .pc-ana .pc-lbl").textContent(), "Anamorphic lens");
      assert.equal(await page.locator("valerion-card .pane .vc-lock").count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("short labels, full option sent", async () => {
    const { page } = await openPicture();
    try {
      const labels = await page.locator("valerion-card .pc-mode .vc-opt").allTextContents();
      assert.deepEqual(labels, ["Vivid", "Standard", "Sports", "Energy Saving", "Game", "Theater", "FILMMAKER MODE", "IMAX Mode"]);
      const vivid = page.locator("valerion-card .pc-mode .vc-opt", { hasText: "Vivid" });
      assert.equal(await vivid.getAttribute("aria-label"), "HDR Vivid");
      await vivid.click();
      await page.locator("valerion-card .pc-ct .vc-opt", { hasText: "Warm 1" }).click();
      const lens = await page.locator("valerion-card .pc-ana .vc-opt").allTextContents();
      assert.deepEqual(lens, ["16:9", "2.39:1", "1.85:1", "2.0:1"]);
      await page.locator("valerion-card .pc-ana .vc-opt", { hasText: "2.39:1" }).click();
      // One selection across both aspect ratio rows.
      assert.deepEqual(await pressed(page, ".pc-ar"), ["anamorphic_2_39_1"]);
      assert.deepEqual(await page.evaluate(() => window.card.hass.calls), [
        { domain: "select", service: "select_option", data: { entity_id: MODE, option: "HDR Vivid" } },
        { domain: "select", service: "select_option", data: { entity_id: CT, option: "warm1" } },
        { domain: "select", service: "select_option", data: { entity_id: AR, option: "anamorphic_2_39_1" } },
      ]);
    } finally {
      await page.close();
    }
  });

  test("a locked setting is hidden and named in the locked line", async () => {
    const { page, errors } = await openPicture();
    try {
      await setState(page, CT, "unavailable");
      assert.equal(await page.locator("valerion-card .pc-ct").count(), 0);
      assert.equal(
        await page.locator("valerion-card .pane .vc-lock").textContent(),
        "Locked for HDR10 in HDR Theater: Color temperature",
      );
      // In 3D the projector locks the aspect ratio.
      await setState(page, VIDEO, "3840×2160p 24 Hz 3D");
      await setState(page, AR, "unavailable");
      assert.equal(await page.locator("valerion-card .pc-ar").count(), 0);
      assert.match(await page.locator("valerion-card .pane .vc-lock").textContent(), /: Color temperature, Aspect ratio$/);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("no signal: a note instead of the aspect ratios", async () => {
    const { page } = await openPicture();
    try {
      await setState(page, HDR, "no_signal");
      assert.equal(await page.locator("valerion-card .pc-ar .vc-opt").count(), 0);
      assert.equal(await page.locator("valerion-card .pc-note").textContent(), "Aspect ratio needs an HDMI signal.");
      assert.equal(await page.locator("valerion-card .pc-badge").count(), 0);
      assert.match(await page.locator("valerion-card .pc-sub").textContent(), /^No signal on HDMI 1\./);
    } finally {
      await page.close();
    }
  });

  for (const power of ["off", "standby"]) {
    test(`${power}: drawn without a selection, buttons disabled`, async () => {
      const { page, errors } = await openPicture({ power });
      try {
        assert.ok((await page.locator("valerion-card .pane .vc-opt").count()) >= 22);
        assert.equal(await page.locator("valerion-card .pane .vc-opt:not([disabled])").count(), 0);
        assert.equal(await page.locator("valerion-card .pane [aria-pressed=true]").count(), 0);
        assert.equal(await page.locator("valerion-card .pc-badge").count(), 0);
        await page.locator("valerion-card .pc-sc .pc-chip").first().waitFor();
        assert.equal(await page.locator("valerion-card .pc-sc [data-action=scene-apply]:not([disabled])").count(), 0);
        assert.equal(await page.locator("valerion-card .pane .vc-lock").count(), 0);
        assert.deepEqual(errors, []);
      } finally {
        await page.close();
      }
    });
  }
});

describe("scenes", () => {
  test("chips come from valerion/scenes/list", async () => {
    const { page, errors } = await openPicture();
    try {
      await page.locator("valerion-card .pc-sc [data-action=scene-apply]").first().waitFor();
      assert.deepEqual(await chips(page), ["Movie night", "Sports", "Daytime", "New"]);
      assert.deepEqual(await wsCalls(page, "valerion/scenes/list"), [
        { type: "valerion/scenes/list", device_id: "device_pro2" },
      ]);
      assert.equal(await page.locator("valerion-card .pc-sc [data-action=scene-edit]").count(), 1);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("a failing list shows no chips and nothing broken", async () => {
    const { page, errors } = await openPicture({}, `hass.ws.handlers["valerion/scenes/list"] = () => { throw { code: "x", message: "x" }; };`);
    try {
      await page.waitForFunction(() => window.card._pcScenes?.failed);
      assert.deepEqual(await chips(page), ["New"]);
      assert.equal(await page.locator("valerion-card .pc-sc [data-action=scene-edit]").count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  for (const [what, prepare, expected] of [
    ["everything applied", "", "Movie night applied."],
    [
      "a setting skipped",
      `hass.ws.handlers["valerion/scenes/apply"] = () => ({ applied: ["picture_mode", "laser_level"], skipped: [{ setting: "gamma", reason: "locked" }, { setting: "laser_level", reason: "refused" }] });`,
      "Movie night applied. Skipped: Gamma (locked for this signal), Laser level (refused by the projector).",
    ],
    [
      "picture mode not offered",
      `hass.ws.handlers["valerion/scenes/apply"] = () => ({ applied: [], skipped: [{ setting: "picture_mode", reason: "not_offered" }, { setting: "laser_level", reason: "picture_mode_not_set" }] });`,
      "Movie night was not applied: HDR Theater is not available for SDR.",
    ],
  ]) {
    test(`apply: toast when ${what}`, async () => {
      const { page, errors } = await openPicture({}, prepare);
      try {
        await setState(page, HDR, "sdr");
        await page.locator("valerion-card .pc-sc .pc-chip", { hasText: "Movie night" }).click();
        assert.deepEqual(await toasts(page), [expected]);
        assert.deepEqual(await wsCalls(page, "valerion/scenes/apply"), [
          { type: "valerion/scenes/apply", device_id: "device_pro2", scene_id: "scene_movie" },
        ]);
        assert.deepEqual(errors, []);
      } finally {
        await page.close();
      }
    });
  }

  test("not an admin: chips only, or a quiet line without scenes", async () => {
    const { page, errors } = await openPicture({}, `hass.user = { id: "guest", name: "Guest", is_admin: false };`);
    try {
      await page.locator("valerion-card .pc-sc [data-action=scene-apply]").first().waitFor();
      assert.deepEqual(await chips(page), ["Movie night", "Sports", "Daytime"]);
      assert.equal(await page.locator("valerion-card [data-action=scene-edit], valerion-card [data-action=scene-new]").count(), 0);
      await page.evaluate(() => {
        window.card.hass.ws.scenes = [];
      });
      await page.locator("valerion-card [role=tab]", { hasText: "Remote" }).click();
      await page.locator("valerion-card [role=tab]", { hasText: "Picture" }).click();
      await page.locator("valerion-card .pc-quiet").waitFor();
      assert.equal(await page.locator("valerion-card .pc-quiet").textContent(), "No scenes yet. An admin can create them here.");
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });
});

describe("scene editor", () => {
  const field = (page, key) => page.locator(`valerion-card #pc-f-${key}`);
  const values = (page) =>
    page.evaluate(() =>
      Object.fromEntries(
        [...window.card.shadowRoot.querySelectorAll(".sheet [data-pc-field]")].map((el) => [el.dataset.pcField, el.value]),
      ),
    );

  test("a new scene starts from the current values and saves them", async () => {
    const { page, errors } = await openPicture();
    try {
      await page.locator("valerion-card [data-action=scene-new]").click();
      assert.equal(await page.evaluate(() => window.card.sheetId), "scene-editor");
      assert.equal(await page.locator("valerion-card .sheet-t").textContent(), "New scene");
      assert.deepEqual(await values(page), {
        name: "",
        picture_mode: "HDR Theater",
        laser_level: "8",
        aspect_ratio: "ratio_16_9",
        gamma: "",
        dynamic_tone_mapping: "low",
        color_temperature: "standard",
        enhanced_black_level: "medium",
        motion_enhancement: "off",
      });
      // Labels as Home Assistant shows them; gamma's read-only values are not offered.
      assert.equal(await field(page, "color_temperature").locator("option:checked").textContent(), "Standard");
      const gamma = await field(page, "gamma").locator("option").allTextContents();
      assert.deepEqual(gamma, ["Don't change", "2.0", "2.2", "2.4", "BT.1886"]);
      await field(page, "name").fill("Late show");
      await field(page, "laser_level").selectOption("3");
      await field(page, "aspect_ratio").selectOption("");
      await page.locator("valerion-card [data-action=scene-save]").click();
      await page.waitForFunction(() => window.card.sheetId === null);
      assert.deepEqual(await wsCalls(page, "valerion/scenes/save"), [
        {
          type: "valerion/scenes/save",
          device_id: "device_pro2",
          name: "Late show",
          settings: {
            picture_mode: "HDR Theater",
            laser_level: 3,
            dynamic_tone_mapping: "low",
            color_temperature: "standard",
            enhanced_black_level: "medium",
            motion_enhancement: "off",
          },
        },
      ]);
      assert.deepEqual(await toasts(page), ["Late show saved."]);
      await page.locator("valerion-card .pc-sc .pc-chip", { hasText: "Late show" }).waitFor();
      assert.deepEqual(await chips(page), ["Movie night", "Sports", "Daytime", "Late show", "New"]);
      assert.equal(await sheet(page).evaluate((el) => el.open), false);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("a new scene while off changes nothing until picked", async () => {
    const { page } = await openPicture({ power: "standby" });
    try {
      await page.locator("valerion-card [data-action=scene-new]").waitFor();
      // The pane is dimmed (no pointer), but the button still works from the keyboard.
      await page.evaluate(() => window.card.shadowRoot.querySelector("[data-action=scene-new]").click());
      const all = await values(page);
      assert.ok(Object.values(all).every((v) => v === ""), JSON.stringify(all));
      await field(page, "name").fill("Bright");
      await page.locator("valerion-card [data-action=scene-save]").click();
      assert.equal(await page.locator("valerion-card .pc-err").textContent(), "Pick at least one setting to change.");
      await field(page, "name").fill(" ");
      await field(page, "laser_level").selectOption("10");
      await page.locator("valerion-card [data-action=scene-save]").click();
      assert.equal(await page.locator("valerion-card .pc-err").textContent(), "Enter a name for the scene.");
      assert.deepEqual(await wsCalls(page, "valerion/scenes/save"), []);
    } finally {
      await page.close();
    }
  });

  test("edit: the first scene, switch, rename keeps the settings", async () => {
    const { page, errors } = await openPicture();
    try {
      await page.locator("valerion-card [data-action=scene-edit]").click();
      assert.equal(await page.locator("valerion-card .sheet-t").textContent(), "Edit scene");
      assert.equal(await page.locator("valerion-card .pc-pick [aria-pressed=true]").textContent(), "Movie night");
      const movie = await values(page);
      assert.equal(movie.name, "Movie night");
      assert.equal(movie.laser_level, "6");
      assert.equal(movie.color_temperature, "warm1");
      assert.equal(movie.motion_enhancement, "");
      await page.locator("valerion-card .pc-pick .pc-chip", { hasText: "Sports" }).click();
      assert.equal(await page.locator("valerion-card .pc-pick [aria-pressed=true]").textContent(), "Sports");
      await field(page, "name").fill("Match day");
      await page.locator("valerion-card [data-action=scene-save]").click();
      await page.waitForFunction(() => window.card.sheetId === null);
      assert.deepEqual(await wsCalls(page, "valerion/scenes/save"), [
        {
          type: "valerion/scenes/save",
          device_id: "device_pro2",
          name: "Match day",
          scene_id: "scene_sports",
          settings: { picture_mode: "HDR Sports", motion_enhancement: "smooth" },
        },
      ]);
      await page.locator("valerion-card .pc-sc .pc-chip", { hasText: "Match day" }).waitFor();
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("a stored picture mode the signal does not offer stays choosable", async () => {
    const { page } = await openPicture(
      {},
      `hass.ws.scenes[0].settings.picture_mode = "Theater";`,
    );
    try {
      await page.locator("valerion-card [data-action=scene-edit]").click();
      const modes = await field(page, "picture_mode").locator("option").allTextContents();
      assert.equal(modes.length, 10);
      assert.equal(modes.at(-1), "Theater");
      assert.equal(await field(page, "picture_mode").inputValue(), "Theater");
    } finally {
      await page.close();
    }
  });

  test("an error reply shows in the sheet", async () => {
    const { page } = await openPicture();
    try {
      await page.locator("valerion-card [data-action=scene-edit]").click();
      await field(page, "name").fill("sports");
      await page.locator("valerion-card [data-action=scene-save]").click();
      await page.locator("valerion-card .pc-err").waitFor();
      assert.equal(
        await page.locator("valerion-card .pc-err").textContent(),
        "Another scene of this projector is already called sports.",
      );
      assert.equal(await page.evaluate(() => window.card.sheetId), "scene-editor");
      assert.equal(await field(page, "name").inputValue(), "sports");
    } finally {
      await page.close();
    }
  });

  test("delete asks once more", async () => {
    const { page, errors } = await openPicture();
    try {
      await page.locator("valerion-card [data-action=scene-edit]").click();
      const del = page.locator("valerion-card [data-action=scene-delete]");
      await del.click();
      assert.equal(await del.textContent(), "Delete Movie night?");
      assert.deepEqual(await wsCalls(page, "valerion/scenes/delete"), []);
      await del.click();
      await page.waitForFunction(() => window.card.sheetId === null);
      assert.deepEqual(await wsCalls(page, "valerion/scenes/delete"), [
        { type: "valerion/scenes/delete", device_id: "device_pro2", scene_id: "scene_movie" },
      ]);
      assert.deepEqual(await toasts(page), ["Movie night deleted."]);
      await page.waitForFunction(() => !window.card.shadowRoot.querySelector(".pc-sc [data-scene=scene_movie]"));
      assert.deepEqual(await chips(page), ["Sports", "Daytime", "New"]);
      // A new scene has no Delete.
      await page.locator("valerion-card [data-action=scene-new]").click();
      assert.equal(await del.count(), 0);
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });

  test("updates while typing keep the text, the focus and the caret", async () => {
    const { page, errors } = await openPicture();
    try {
      await page.locator("valerion-card [data-action=scene-new]").click();
      const name = field(page, "name");
      await name.click();
      await page.keyboard.type("Mov");
      await field(page, "laser_level").selectOption("2");
      await name.focus();
      await page.evaluate(() => {
        window.card.shadowRoot.querySelector("#pc-f-name").dataset.mark = "1";
      });
      // A sensor changes: the sheet asks for its body, the fields stay as they are.
      await setState(page, "sensor.visionmaster_pro2_fan_1", "1900");
      assert.equal(await name.getAttribute("data-mark"), "1");
      await page.keyboard.type("ie");
      assert.equal(await name.inputValue(), "Movie");
      // The signal changes the picture modes: drawn again, from the draft.
      await page.keyboard.press("ArrowLeft");
      await page.keyboard.press("ArrowLeft");
      await setState(page, MODE, "Theater", { options: ["Standard", "Vivid", "Theater"] });
      assert.equal(await name.getAttribute("data-mark"), null);
      assert.equal(await name.inputValue(), "Movie");
      assert.equal(await field(page, "laser_level").inputValue(), "2");
      assert.equal(await page.evaluate(() => window.card.shadowRoot.activeElement?.id), "pc-f-name");
      await page.keyboard.type(" n");
      assert.equal(await name.inputValue(), "Mov nie");
      assert.deepEqual(errors, []);
    } finally {
      await page.close();
    }
  });
});

describe("layout", () => {
  for (const power of ["on", "standby"]) {
    test(`fits the phone with 8 modes, 10 aspect ratios and 3 scenes (${power})`, async () => {
      const { page } = await openPicture({ power, viewport: PHONE });
      try {
        await page.locator("valerion-card .pc-sc [data-action=scene-apply]").nth(2).waitFor();
        const box = await page.evaluate(() => {
          const root = window.card.shadowRoot;
          const p = root.querySelector(".pane");
          const row = root.querySelector(".pc-sc .pc-chips");
          return {
            pane: p.clientHeight,
            content: p.scrollHeight,
            card: window.card.getBoundingClientRect().bottom,
            row: [row.scrollWidth, row.clientWidth],
            cut: [...root.querySelectorAll(".pc-chip > span")].filter((s) => s.scrollWidth > s.clientWidth).length,
          };
        });
        assert.ok(box.content <= box.pane, `content ${box.content} > ${box.pane}`);
        assert.ok(box.card <= PHONE.height, `card ends at ${box.card}`);
        assert.ok(box.row[0] <= box.row[1], `scene row ${box.row[0]} > ${box.row[1]}`);
        assert.equal(box.cut, 0);
      } finally {
        await page.close();
      }
    });
  }

  test("two columns from 600 px wide", async () => {
    const { page } = await openPicture({ viewport: { width: 820, height: 1000 } });
    try {
      await page.addStyleTag({ content: ".view{max-width:none}" });
      const tops = await page.evaluate(() => {
        const root = window.card.shadowRoot;
        const top = (sel) => Math.round(root.querySelector(sel).getBoundingClientRect().top);
        const p = root.querySelector(".pane");
        return { ct: top(".pc-ct"), sc: top(".pc-sc"), mode: top(".pc-mode"), fits: p.scrollHeight <= p.clientHeight };
      });
      assert.equal(tops.ct, tops.sc);
      assert.ok(tops.mode < tops.ct);
      assert.ok(tops.fits);
    } finally {
      await page.close();
    }
  });
});
