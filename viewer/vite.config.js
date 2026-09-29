import { defineConfig } from "vite";

// The viewer reads the compiled data straight from ../dist (written by tools/build.py):
// dist/graph.json is served at /graph.json and dist/series/* at /series/*.
export default defineConfig({
  publicDir: "../dist",
  // three.js alone is ~600 kB minified; that is expected.
  build: { outDir: "build", emptyOutDir: true, chunkSizeWarningLimit: 1000 },
  server: { port: 5173 },
});
