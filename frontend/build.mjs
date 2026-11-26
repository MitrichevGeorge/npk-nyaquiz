import * as esbuild from "esbuild";
import fs from "node:fs";
import path from "node:path";

fs.mkdirSync("dist", { recursive: true });

await esbuild.build({
  entryPoints: [
    "src/auth.js",
    "src/dashboard.js",
    "src/host.js",
    "src/broadcast.js",
    "src/participant.js",
  ],
  outdir: "dist",
  bundle: true,
  splitting: true,
  format: "esm",
  minify: true,
  sourcemap: false,
  target: ["es2022"],
});

fs.copyFileSync(path.join("styles", "main.css"), path.join("dist", "main.css"));
