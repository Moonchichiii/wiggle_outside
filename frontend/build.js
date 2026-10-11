import { createHash } from "node:crypto";
import { copyFile, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const staticRoot = join(root, "src", "wiggle_outside", "web", "static");

async function copyAssets(source, destination, extensions) {
  const from = join(root, source);
  const to = join(staticRoot, destination);
  await mkdir(to, { recursive: true });
  const names = (await readdir(from)).filter((name) =>
    extensions.some((extension) => name.endsWith(extension)),
  );
  await Promise.all(names.map((name) => copyFile(join(from, name), join(to, name))));
  console.log(`Copied ${names.length} assets to static/${destination}`);
}

// Content-hashed copies with their SRI digests, named in manifest.json for the server
// (web/routes/assets.py). The hashed names are immutable, so they carry a one-year
// cache and a stale browser copy can never be served against a new integrity value.
const HASHED = /^(app|location|print)\.[0-9a-f]{8}\.(css|js)$/;

async function hashed(sourcePath, logicalName) {
  const body = await readFile(sourcePath);
  const digest = createHash("sha256").update(body).digest("hex").slice(0, 8);
  const integrity = `sha384-${createHash("sha384").update(body).digest("base64")}`;
  const dot = logicalName.lastIndexOf(".");
  const fileName = `${logicalName.slice(0, dot)}.${digest}${logicalName.slice(dot)}`;
  await writeFile(join(staticRoot, fileName), body);
  return { url: `/static/${fileName}`, integrity };
}

async function writeManifest() {
  await mkdir(staticRoot, { recursive: true });
  for (const name of await readdir(staticRoot)) {
    if (HASHED.test(name)) {
      await rm(join(staticRoot, name));
    }
  }
  const manifest = {
    // build:css has already written the plain app.css; the page links the hashed copy.
    "app.css": await hashed(join(staticRoot, "app.css"), "app.css"),
  };
  const scripts = join(root, "frontend", "js");
  for (const name of (await readdir(scripts)).filter((n) => n.endsWith(".js")).sort()) {
    manifest[name] = await hashed(join(scripts, name), name);
  }
  await writeFile(join(staticRoot, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Wrote manifest.json with ${Object.keys(manifest).length} assets`);
}

await copyAssets("frontend/svg/decor", "decor", [".svg"]);
await copyAssets("frontend/art", "decor", [".png", ".webp"]);
// TC-011: the tab icons, exported once from the approved sun artwork (docs/design-kit/board/
// sun.png); the .ico is served at /favicon.ico, the touch icon from the static root.
await copyFile(join(root, "frontend", "art", "favicon.ico"), join(staticRoot, "favicon.ico"));
await copyFile(
  join(root, "frontend", "art", "apple-touch-icon.png"),
  join(staticRoot, "apple-touch-icon.png"),
);
await writeManifest();
