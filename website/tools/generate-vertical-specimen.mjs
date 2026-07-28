import { spawnSync } from "node:child_process";
import { accessSync, mkdirSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const toolsDir = dirname(fileURLToPath(import.meta.url));
const websiteDir = resolve(toolsDir, "..");
const source = resolve(toolsDir, "vertical-specimen.html");
const font = resolve(
  websiteDir,
  "src/assets/fonts/NobigoeMincho-Regular.woff2",
);
const output = resolve(
  process.env.SPECIMEN_OUTPUT ??
    resolve(websiteDir, "public/nobigoe-mincho-vertical-specimen.pdf"),
);

accessSync(source);
accessSync(font);
mkdirSync(dirname(output), { recursive: true });

const candidates = [
  process.env.CHROME_BIN,
  "google-chrome",
  "google-chrome-stable",
  "chromium",
  "chromium-browser",
].filter(Boolean);

const chrome = candidates.find((candidate) => {
  const result = spawnSync(candidate, ["--version"], { stdio: "ignore" });
  return result.status === 0;
});

if (!chrome) {
  throw new Error(
    "Chrome or Chromium was not found. Set CHROME_BIN to its executable path.",
  );
}

const result = spawnSync(
  chrome,
  [
    "--headless",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--run-all-compositor-stages-before-draw",
    "--no-pdf-header-footer",
    `--print-to-pdf=${output}`,
    pathToFileURL(source).href,
  ],
  { stdio: "inherit" },
);

if (result.status !== 0) {
  throw new Error(`PDF generation failed with exit code ${result.status}`);
}

const size = statSync(output).size;
if (size === 0) {
  throw new Error("PDF generation produced an empty file");
}

console.log(`Generated ${output} (${size} bytes)`);
