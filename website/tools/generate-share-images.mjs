import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { chromium } from "playwright";

const toolsDirectory = dirname(fileURLToPath(import.meta.url));
const websiteDirectory = resolve(toolsDirectory, "..");
const source = resolve(toolsDirectory, "share-images.html");
const outputDirectory = resolve(websiteDirectory, "public/assets");

const images = [
  ["x-card", "x-introduction.png", 1200, 675],
  ["extension-card", "x-extensible-symbols.png", 1200, 675],
  ["combining-card", "x-combining-marks.png", 1200, 675],
  ["family-card", "x-download.png", 1200, 675],
  ["bilingual-card", "x-japanese-latin.png", 1200, 675],
  ["readme-card", "readme-glyphs.png", 1400, 900],
];

await mkdir(outputDirectory, { recursive: true });

// The headless shell renders this font differently from headed Chromium.
// The "chromium" channel uses full Chromium's matching headless renderer.
const browser = await chromium.launch({ channel: "chromium", headless: true });
try {
  const page = await browser.newPage({
    deviceScaleFactor: 1,
    viewport: { width: 1600, height: 1000 },
  });
  await page.goto(pathToFileURL(source).href);
  await page.evaluate(() => document.fonts.ready);

  for (const [id, filename, expectedWidth, expectedHeight] of images) {
    const artboard = page.locator(`#${id}`);
    const box = await artboard.boundingBox();
    if (
      box === null ||
      box.width !== expectedWidth ||
      box.height !== expectedHeight
    ) {
      throw new Error(
        `${id} must be ${expectedWidth}x${expectedHeight}px; got ${box?.width ?? 0}x${box?.height ?? 0}px`,
      );
    }

    await artboard.screenshot({
      animations: "disabled",
      path: resolve(outputDirectory, filename),
    });
    console.log(`Generated public/assets/${filename}`);
  }
} finally {
  await browser.close();
}
