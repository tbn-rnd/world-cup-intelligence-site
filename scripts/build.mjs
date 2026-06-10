import { build, context } from "esbuild";
import { marked } from "marked";
import { readFile, writeFile } from "node:fs/promises";

const watch = process.argv.includes("--watch");

const opts = {
  entryPoints: ["src/main.ts"],
  bundle: true,
  outfile: "site/assets/app.js",
  format: "esm",
  target: "es2022",
  sourcemap: true,
  minify: !watch,
  logLevel: "info",
};

async function buildGuide() {
  const md = await readFile("site/guide.md", "utf8");
  const template = await readFile("site/assets/guide-template.html", "utf8");
  const html = marked.parse(md, { mangle: false, headerIds: true });
  const out = template.replace("<!-- GUIDE_BODY -->", html);
  await writeFile("site/guide.html", out, "utf8");
  console.log("built site/guide.html");
}

if (watch) {
  const ctx = await context(opts);
  await ctx.watch();
  console.log("watching src/...");
  await buildGuide();
} else {
  await build(opts);
  console.log("built site/assets/app.js");
  await buildGuide();
}
