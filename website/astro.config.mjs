import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://ouvill.github.io",
  base: "/nobigoe-font",
  output: "static",
  outDir: "./site-dist",
  trailingSlash: "always",
  build: {
    assets: "_assets",
  },
});
