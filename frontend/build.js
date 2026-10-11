import { readdir, mkdir, copyFile } from "node:fs/promises";
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

await copyAssets("frontend/svg/decor", "decor", [".svg"]);
await copyAssets("frontend/art", "decor", [".png", ".webp"]);
