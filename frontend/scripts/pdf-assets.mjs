import { cp, mkdir } from "node:fs/promises";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
await mkdir(resolve(root, "public/pdfjs"), { recursive: true });
for (const name of ["cmaps", "standard_fonts", "wasm"])
  await cp(
    resolve(root, "node_modules/pdfjs-dist", name),
    resolve(root, "public/pdfjs", name),
    { recursive: true },
  );
await cp(
  resolve(root, "node_modules/pdfjs-dist/build/pdf.worker.min.mjs"),
  resolve(root, "public/pdfjs/pdf.worker.min.mjs"),
);
