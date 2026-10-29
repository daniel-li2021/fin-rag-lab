import test from "node:test";
import assert from "node:assert/strict";
import { api } from "../lib/client.mjs";

test("failed run submission is never replayed automatically", async () => {
  let calls = 0;
  const draft = { question: "Original question", selections: [{ source_id: "pinned" }] };
  const controller = new AbortController();
  await assert.rejects(api("research/questions", draft, controller.signal, async (path, options) => {
    calls++;
    assert.equal(path, "/api/backend/research/questions");
    assert.equal(options.method, "POST");
    assert.equal(options.signal, controller.signal);
    assert.deepEqual(JSON.parse(options.body), draft);
    throw TypeError("Failed to fetch");
  }), /Connection interrupted.*draft are retained.*check History before submitting again/);
  assert.equal(calls, 1);
  assert.equal(draft.question, "Original question");
});

test("read failures offer useful messages without raw response content", async () => {
  await assert.rejects(api("sources", undefined, undefined, async () => new Response("<html>proxy error</html>")), /unreadable response/);
  await assert.rejects(api("sources", undefined, undefined, async () => Response.json({}, { status: 401 })), /Private access is required/);
  await assert.rejects(api("sources", undefined, undefined, async () => Response.json({ detail: "Not in the public demonstration archive" }, { status: 404 })), /Not in the public demonstration archive/);
});

test("abandoned reads stay aborted and saved payloads pass through unchanged", async () => {
  const aborted = new DOMException("Aborted", "AbortError");
  await assert.rejects(api("sources", undefined, undefined, async () => { throw aborted; }), error => error === aborted);
  await assert.rejects(api("sources", undefined, undefined, async () => ({ json: async () => { throw aborted; } })), error => error === aborted);
  const payload = { run_id: "original-run", value: "1390.0000", parent_run_id: "original-parent" };
  assert.deepEqual(await api("research/runs/original-run", undefined, undefined, async (_, options) => {
    assert.equal(options.method, "GET");
    assert.equal(options.cache, "no-store");
    return Response.json(payload);
  }), payload);
});
