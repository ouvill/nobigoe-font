import { readFileSync } from "node:fs";

import { defineConfig } from "astro/config";

const versionData = JSON.parse(
  readFileSync(
    new URL("../src/nobigoe_font/version.json", import.meta.url),
    "utf8",
  ),
);
if (
  typeof versionData.version !== "string" ||
  !/^[0-9]+\.[0-9]{3}$/.test(versionData.version)
) {
  throw new Error("version.json must contain a version in N.NNN format");
}

export default defineConfig({
  site: "https://nobigoe.ouvill.net",
  output: "static",
  outDir: "./site-dist",
  trailingSlash: "always",
  build: {
    assets: "_assets",
  },
  vite: {
    define: {
      "import.meta.env.PUBLIC_FONT_VERSION": JSON.stringify(
        versionData.version,
      ),
    },
  },
});
