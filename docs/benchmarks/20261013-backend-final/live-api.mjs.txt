// Real Next → FastAPI → retained PostgreSQL checks. No ingestion or provider calls.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
const base = process.env.FINRAG_WORKSPACE_URL || "http://127.0.0.1:3200";
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
let checks = 0;
async function get(path) {
  const r = await fetch(base + "/api/backend/" + path);
  assert.equal(r.status, 200, path);
  checks++;
  return r.json();
}
async function post(path, body) {
  const r = await fetch(base + "/api/backend/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: base },
    body: JSON.stringify(body),
  });
  assert.equal(r.status, 200, `${path}: ${await r.clone().text()}`);
  checks++;
  return r.json();
}
const sources = await get("sources"),
  collections = await get("research/collections");
assert.equal(sources.length, 22);
const choose = (name) => collections.find((c) => c.name === name).collection_id;
const ranking = await post("research/questions", {
  question:
    "rank GAAP consolidated net income attributable to common for TSLA and WFC in Q2 2025",
  collection_id: choose("Q2 2025 originals"),
  save: true,
});
assert.equal(ranking.outcome, "answer");
assert.deepEqual(ranking.ranking, ["task-2", "task-1"]);
assert.deepEqual(
  ranking.observations.map((o) => [o.company_id, o.value]),
  [
    ["TSLA", "1172"],
    ["WFC", "5214"],
  ],
);
const original = await get(`research/runs/${ranking.run_id}`);
assert.deepEqual(original.payload, ranking);
const rerun = await post(`research/runs/${ranking.run_id}/rerun`, {});
assert.notEqual(rerun.result.run_id, ranking.run_id);
assert.equal(rerun.result.execution.parent_run_id, ranking.run_id);
assert.deepEqual(
  (await get(`research/runs/${ranking.run_id}`)).payload,
  ranking,
);
assert.equal(rerun.diff.answer_changed, false);
const growth = await post("research/questions", {
  question: "growth GAAP consolidated revenue for AMD in Q1 2024 to Q2 2024",
  collection_id: choose("AMD reviewed history"),
  save: false,
});
assert.equal(growth.calculations[0].displayed_result, "+6.61%");
assert.deepEqual(growth.calculations[0].normalized_operands, [
  "5473000000",
  "5835000000",
]);
assert.equal(growth.observations[0].period.start, "2023-12-31");
const h1 = await get("research/runs?offset=0"),
  h2 = await get("research/runs?offset=100");
assert.equal(h1.length, 100);
assert.equal(h2.length, 100);
assert.ok(!h2.some((r) => h1.some((x) => x.run_id === r.run_id)));
const hs = await get(
  "research/runs?search=" +
    encodeURIComponent(
      "rank GAAP consolidated net income attributable to common",
    ),
);
assert.ok(hs.some((r) => r.run_id === ranking.run_id));
for (const s of sources) {
  const versions = await get(`sources/${s.source_id}/versions`);
  assert.ok(versions.some((v) => v.version_id === s.active_version_id));
}
for (const c of Object.values(ranking.citations)) {
  const s = c.source,
    r = await fetch(
      `${base}/api/backend/sources/${s.source_id}/versions/${s.version_id}/raw`,
    );
  assert.equal(r.status, 200);
  assert.equal(sha(Buffer.from(await r.arrayBuffer())), s.source_hash);
  checks++;
}
const fixtures = JSON.parse(
  await readFile(new URL("../public/fixtures.json", import.meta.url)),
);
for (const [hash] of Object.entries(fixtures.originals)) {
  const r = await fetch(base + "/api/archive/" + hash);
  assert.equal(r.status, 200);
  assert.equal(sha(Buffer.from(await r.arrayBuffer())), hash);
  checks++;
}
const tasks = [
  {
    task_id: "q2",
    company_id: "TSLA",
    query: "operating income headwinds",
    document_period_label: "Q2 2025",
  },
];
const selections = sources
  .filter(
    (s) =>
      s.metadata.company_id === "TSLA" && s.metadata.period_label === "Q2 2025",
  )
  .map((s) => ({ source_id: s.source_id }));
const evidence = await post("research/evidence/runs", {
  question: "Tesla Q2 2025 reported operating-income headwinds",
  tasks,
  selections,
  synthesize: false,
});
assert.ok(evidence.passages.length > 0);
assert.equal(evidence.claims?.length || 0, 0);
assert.deepEqual(
  (await get(`research/runs/${evidence.run_id}`)).payload,
  evidence,
);
const refused = await post("research/questions", {
  question: "What should I buy?",
  collection_id: choose("Q2 2025 originals"),
  save: false,
});
assert.equal(refused.outcome, "clarify");
assert.deepEqual(refused.citations, {});
const forbidden = await fetch(base + "/api/backend/research/questions", {
  method: "POST",
  headers: {
    Origin: "https://foreign.test",
    "Content-Type": "application/json",
  },
  body: "{}",
});
assert.equal(forbidden.status, 403);
checks++;
const alien = await fetch(
  base + "/api/backend/research/runs/" + "0".repeat(64),
);
assert.equal(alien.status, 404);
checks++;
console.log(
  JSON.stringify({
    checks,
    sources: sources.length,
    history_pages: 2,
    ranking_run: ranking.run_id,
    evidence_run: evidence.run_id,
    provider_calls: 0,
  }),
);
