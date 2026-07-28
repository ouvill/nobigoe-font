import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://nobigoe.ouvill.net",
  output: "static",
  outDir: "./site-dist",
  trailingSlash: "always",
  build: {
    assets: "_assets",
  },
});
