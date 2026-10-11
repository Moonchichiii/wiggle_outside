// Copy the board artwork into the static root so the app can serve it.
// Bun only: no npm, no npx (DESIGN-SPEC section 11). Run via `bun run build:assets`.
//
// The pictures are cut from the approved concept board (docs/design-kit/board, TC-008):
// the margin decorations, the brand sprig and the card illustrations. They are artwork
// files, not UI logic: decorative <img alt=""> elements inside aria-hidden containers.

import { readdir, mkdir, copyFile } from "node:fs/promises";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const from = join(root, "frontend", "img", "board");
const to = join(root, "src", "wiggle_outside", "web", "static", "board");

await mkdir(to, { recursive: true });
const names = (await readdir(from)).filter((n) => n.endsWith(".png"));
await Promise.all(names.map((n) => copyFile(join(from, n), join(to, n))));
console.log(`copied ${names.length} board assets to static/board`);
