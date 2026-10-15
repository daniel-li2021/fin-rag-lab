import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const data = JSON.parse(readFileSync(resolve(root, "public/fixtures.json")));
assert.equal(data.scenarios.length, 5);
assert.deepEqual(data.pages, {});
const official = new Set(["www.sec.gov", "www.wellsfargo.com", "www.tesla.com", "ir.tesla.com", "ir.amd.com"]);
for (const [hash, original] of Object.entries(data.originals)) {
  assert.equal(hash, original.sha256);
  assert.equal(new URL(original.url).protocol, "https:");
  assert.ok(official.has(new URL(original.url).hostname));
  assert.ok(!original.file && !original.local_url);
}
function inspect(dir) {
  for (const file of readdirSync(dir, {withFileTypes:true})) {
    const path = resolve(dir,file.name);
    if (file.isDirectory()) { inspect(path); continue; }
    assert.ok(!/\.(?:pdf|png|jpe?g|env|py|sql)$/i.test(file.name), path);
    if (/\.(?:json|css|js|mjs|txt)$/.test(file.name)) {
      const text = readFileSync(path,"utf8");
      assert.ok(!/\/Users\/|\/private\/|localhost|127\.0\.0\.1|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_-]{20,}|-----BEGIN .*PRIVATE KEY-----/i.test(text), path);
    }
  }
}
// pdfjs assets contain library references; only the first-party public artifacts are scanned.
for (const name of readdirSync(resolve(root,"public"))) {
  if (name === "pdfjs") continue;
  const path = resolve(root,"public",name);
  if (name === "fixtures.json") {
    assert.ok(!/\/Users\/|\/private\/|localhost|127\.0\.0\.1|sk-proj-|Bearer\s/i.test(readFileSync(path,"utf8")));
  } else inspect(path);
}
const steps = [...data.scenarios.flatMap(s=>s.steps),data.calculation];
// Run in the repository during development/CI, without requiring originals or a database.
for (const [artifact, hash] of Object.entries(data.artifacts)) {
  const bytes = readFileSync(resolve(root,"..",artifact));
  assert.equal(createHash("sha256").update(bytes).digest("hex"),hash,artifact);
}
for (const step of steps) {
  const raw = readFileSync(resolve(root,"..",step.artifact),"utf8");
  const expected = step.artifact.endsWith(".jsonl") ? raw.trim().split("\n").map(JSON.parse).find(r=>r.case_id===step.case_id).result
    : step.case_id === "reviewed_rerun" ? JSON.parse(raw).reviewed_rerun.result : JSON.parse(raw)[step.case_id];
  assert.deepEqual(step.result,expected,step.case_id);
  for (const c of Object.values(step.result.citations)) assert.ok(data.originals[c.source.source_hash]);
}
assert.equal(data.calculation.result.calculations[0].displayed_result,"+6.61%");
console.log(`Public artifact scan passed; ${steps.length} exact original payloads, five Heroes, official links, no distributed PDFs/pages.`);
