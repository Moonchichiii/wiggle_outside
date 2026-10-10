// Copy the decoration assets into the static root so the app can serve them.
// Bun only: no npm, no npx (DESIGN-SPEC section 11). Run via `bun run build:assets`.
//
// The decorations are artwork files, not UI logic: they are referenced from CSS
// backgrounds, so they never enter the DOM, never take focus and never intercept a
// click (the visual-direction brief, and DESIGN-SPEC section 5).

import { readdir, mkdir, copyFile } from "node:fs/promises";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const from = join(root, "frontend", "svg", "decor");
const to = join(root, "src", "wiggle_outside", "web", "static", "decor");

await mkdir(to, { recursive: true });
const names = (await readdir(from)).filter((n) => n.endsWith(".svg"));
await Promise.all(names.map((n) => copyFile(join(from, n), join(to, n))));
console.log(`copied ${names.length} decoration assets to static/decor`);
