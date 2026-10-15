import { readFile } from "node:fs/promises";
import { join } from "node:path";

let archive;
export function demoArchive() {
  return (archive ||= readFile(join(process.cwd(), "public/fixtures.json"), "utf8")
    .then(JSON.parse));
}

// Adapt preserved envelopes to the existing API contracts; never recompute money.
export function demoResponse(request, path, data) {
  const steps = [...data.scenarios.flatMap((s) => s.steps), data.calculation];
  const results = steps.map((s) => s.result);
  const change = data.scenarios.find((s) => s.id === "change");
  const pins = results.flatMap((r) => r.manifest || []);
  const sources = new Map();
  for (const r of results.filter((r) => r.execution)) for (const item of r.inventory || []) {
    const pin = r.manifest.find((p) => p.source_id === item.source_id);
    if (pin) sources.set(item.source_id, {
      ...item, active_version_id: pin.version_id, active_build_id: pin.build_id,
      demo: true,
    });
  }
  const json = (value, status = 200) => Response.json(value, {
    status, headers: { "Cache-Control": "no-store", "X-FinRAG-Data": "preserved-demo" },
  });
  if (request.method !== "GET") return json({ detail:
    "Live research is private. Open a preserved Hero Scenario; no new execution was created." }, 403);
  if (path === "sources") return json([...sources.values()]);
  if (path === "research/collections") return json([]);
  const runs = results.filter((r) => r.execution);
  if (path === "research/runs") {
    const query = new URL(request.url).searchParams;
    const offset = Number(query.get("offset") || 0);
    if (!Number.isSafeInteger(offset) || offset < 0) return json({detail:"Invalid offset"}, 400);
    const search = (query.get("search") || "").toLowerCase();
    return json(runs.filter((r) => r.request.question.toLowerCase().includes(search))
      .sort((a,b) => b.execution.timestamp.localeCompare(a.execution.timestamp))
      .slice(offset, offset + 100).map((r) => ({
        run_id: r.run_id, question: r.request.question, outcome: r.outcome,
        created_at: r.execution.timestamp, parent_run_id: r.execution.parent_run_id,
        demo: true,
      })));
  }
  const saved = path.match(/^research\/runs\/([a-f0-9]{64})$/);
  if (saved) {
    const payload = runs.find((r) => r.run_id === saved[1]);
    if (payload) return json({ payload, demo: true, source_changes:
      payload.run_id === change.steps[0].result.run_id ? change.changes :
        { potentially_stale: false, changes: [] } });
  }
  const sourcePath = path.match(/^sources\/([a-f0-9-]{36})(?:\/([^/]+))?$/);
  if (sourcePath && sources.has(sourcePath[1])) {
    const id = sourcePath[1];
    if (!sourcePath[2]) return json(sources.get(id));
    if (sourcePath[2] === "versions") {
      const unique = [...new Map(pins.filter((p) => p.source_id === id)
        .map((p) => [p.version_id, p])).values()];
      return json(unique.map((p) => ({
        version_id: p.version_id, active_build_id: p.build_id, sha256: p.source_hash,
        // Captures preserve identity, but not the registry's ordinal/version metadata log.
        number: p.version_id.slice(0, 8), metadata: results.flatMap((r) => r.inventory || [])
          .find((i) => i.source_id === id && i.version_id === p.version_id)?.metadata || {},
        media_type: "application/pdf", demo: true,
        official_url: data.originals[p.source_hash]?.url,
      })));
    }
    if (sourcePath[2] === "observations") {
      const version = new URL(request.url).searchParams.get("version_id");
      return json([...new Map(results.flatMap((r) => r.observations || [])
        .filter((o) => o.source.source_id === id && (!version || o.source.version_id === version))
        .map((o) => [o.observation_id, o])).values()]);
    }
  }
  if (/^sources\/[a-f0-9-]{36}\/versions\/[a-f0-9-]{36}\/metadata-reviews$/.test(path))
    return json([]);
  return json({ detail: "Not in the public demonstration archive" }, 404);
}
