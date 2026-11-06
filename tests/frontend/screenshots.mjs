// Screenshots of the card on a phone (390x844, 2x), light and dark.
// Usage: node screenshots.mjs <output folder> [power] [tab]

import path from "node:path";

import { chromium } from "playwright";

import { openCard, PHONE, startServer } from "./harness.mjs";

const [outDir = ".", power = "on", tab = "Remote"] = process.argv.slice(2);
const server = await startServer();
const browser = await chromium.launch();
try {
  for (const theme of ["light", "dark"]) {
    const { page } = await openCard(browser, server.url, {
      theme,
      power,
      viewport: PHONE,
      deviceScaleFactor: 2,
    });
    await page.locator("valerion-card [role=tab]", { hasText: tab }).click();
    const file = path.join(outDir, `card-${tab.toLowerCase()}-${power}-${theme}.png`);
    await page.screenshot({ path: file });
    console.log(file);
    await page.close();
  }
} finally {
  await browser.close();
  await server.close();
}
