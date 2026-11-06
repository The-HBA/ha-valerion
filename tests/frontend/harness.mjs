// Serves the card files and a test page, and opens the card in Chromium.

import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const WWW = path.resolve(HERE, "../../custom_components/valerion/www");

const FILES = {
  "/": path.join(HERE, "page.html"),
  "/fake-hass.js": path.join(HERE, "fake-hass.js"),
  "/valerion_static/valerion-card.js": path.join(WWW, "valerion-card.js"),
  "/valerion_static/valerion-card-editor.js": path.join(WWW, "valerion-card-editor.js"),
  "/panel.html": path.join(HERE, "panel.html"),
  "/valerion_static/valerion-panel.js": path.join(WWW, "valerion-panel.js"),
};

export const PHONE = { width: 390, height: 844 };

/** Start a web server on 127.0.0.1; returns its base URL and a close function. */
export async function startServer() {
  const server = createServer(async (request, response) => {
    const file = FILES[new URL(request.url, "http://127.0.0.1").pathname];
    if (!file) {
      response.writeHead(404).end();
      return;
    }
    const type = file.endsWith(".html") ? "text/html" : "text/javascript";
    response.writeHead(200, { "content-type": `${type}; charset=utf-8` });
    response.end(await readFile(file));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return {
    url: `http://127.0.0.1:${server.address().port}`,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

/**
 * Open a page with the card mounted. Options: theme ("light" or "dark"),
 * power (media player state), viewport, deviceScaleFactor.
 * Script errors on the page are collected in `errors`.
 */
export async function openCard(browser, baseUrl, options = {}) {
  const { theme = "light", power = "on", viewport = PHONE, deviceScaleFactor = 1 } = options;
  // Reduced motion turns transitions off, so styles are final at once.
  const page = await browser.newPage({
    viewport,
    deviceScaleFactor,
    colorScheme: theme,
    reducedMotion: "reduce",
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error));
  await page.goto(`${baseUrl}/?theme=${theme}`);
  await page.waitForFunction(() => window.cardReady);
  await page.evaluate((state) => window.mountCard({ power: state }), power);
  await page.locator("valerion-card .vc-name").waitFor();
  return { page, errors };
}

export const DESKTOP = { width: 1280, height: 800 };

/**
 * Open a page with the sidebar panel mounted, as Home Assistant shows it.
 * Options: theme, power, projectors ("two", "one" or "none"), narrow,
 * viewport, deviceScaleFactor, stored (a device ID already in localStorage).
 * Script errors on the page are collected in `errors`.
 */
export async function openPanel(browser, baseUrl, options = {}) {
  const {
    theme = "light",
    power = "on",
    projectors = "two",
    viewport = PHONE,
    narrow = viewport.width < 870,
    deviceScaleFactor = 1,
    stored = null,
  } = options;
  const page = await browser.newPage({
    viewport,
    deviceScaleFactor,
    colorScheme: theme,
    reducedMotion: "reduce",
  });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error));
  if (stored) {
    await page.addInitScript((id) => localStorage.setItem("valerion-panel-device", id), stored);
  }
  await page.goto(`${baseUrl}/panel.html?theme=${theme}`);
  await page.waitForFunction(() => window.panelReady);
  await page.evaluate((args) => window.mountPanel(args), { power, projectors, narrow });
  await page.waitForFunction(() => window.panel.shadowRoot?.querySelector(".toolbar"));
  if (projectors !== "none") {
    await page.locator("valerion-panel valerion-card .vc-name").waitFor();
  }
  return { page, errors };
}
