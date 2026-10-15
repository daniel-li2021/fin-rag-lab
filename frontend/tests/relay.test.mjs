import test from "node:test";
import assert from "node:assert/strict";
import { allowedPath, relay } from "../lib/relay.mjs";
const env = {
  FINRAG_BACKEND_URL: "http://127.0.0.1:8000",
  FINRAG_API_TOKEN: "private-server-credential",
};
const req = (path = "research/questions", origin = "http://localhost:3200") =>
  new Request(`http://localhost:3200/api/backend/${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(origin ? { origin } : {}),
    },
    body: JSON.stringify({ question: "Exact question", save: true }),
  });
test("only product API surfaces are exposed", () => {
  for (const path of [
    "query",
    "sources/../health",
    "sources",
    "sources/a/snapshot",
    "research/observations",
    "https://evil.test",
    "research/questions/extra",
  ])
    assert.equal(allowedPath("POST", path), false, path);
  assert.equal(allowedPath("POST", "research/questions"), true);
  assert.equal(allowedPath("GET", "research/runs"), true);
  assert.equal(allowedPath("DELETE", "research/runs"), false);
});
test("server credential, immutable payload and pagination passthrough", async () => {
  const answer = { value: "1390.00000000000000000001", run_id: "a".repeat(64) };
  let calls = 0;
  const response = await relay(
    req(),
    "research/questions",
    env,
    async (url, opts) => {
      calls++;
      assert.equal(url.href, "http://127.0.0.1:8000/research/questions");
      assert.equal(
        opts.headers.Authorization,
        "Bearer private-server-credential",
      );
      assert.equal(opts.redirect, "error");
      assert.equal(opts.cache, "no-store");
      assert.deepEqual(JSON.parse(opts.body), {
        question: "Exact question",
        save: true,
      });
      return Response.json(answer);
    },
  );
  assert.deepEqual(await response.json(), answer);
  assert.equal(calls, 1);
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  await relay(
    new Request(
      "http://localhost:3200/api/backend/research/runs?offset=100&search=a%25",
    ),
    "research/runs",
    env,
    async (url) => {
      assert.equal(url.search, "?offset=100&search=a%25");
      return Response.json([]);
    },
  );
});
test("cross-site and missing-origin writes fail before backend", async () => {
  for (const origin of ["https://evil.test", null]) {
    let called = false;
    const r = await relay(
      req(undefined, origin),
      "research/questions",
      env,
      () => {
        called = true;
      },
    );
    assert.equal(r.status, 403);
    assert.equal(called, false);
  }
});
test("unavailable, auth and internal failures are sanitized without retries", async () => {
  assert.equal((await relay(req(), "research/questions", {})).status, 503);
  for (const status of [401, 500]) {
    let n = 0;
    const r = await relay(req(), "research/questions", env, async () => {
      n++;
      return new Response("SECRET traceback", { status });
    });
    assert.equal(n, 1);
    assert.equal(await r.text().then((t) => t.includes("SECRET")), false);
  }
  const r = await relay(req(), "research/questions", env, async () => {
    throw Error("secret token");
  });
  assert.equal(r.status, 502);
  assert.equal((await r.text()).includes("secret token"), false);
});
test("original bytes are streamed without rewriting and unsafe formats download", async () => {
  const path = `sources/${"a".repeat(36)}/versions/${"b".repeat(36)}/raw`;
  for (const type of ["application/pdf", "text/html"]) {
    const r = await relay(
      new Request("http://localhost:3200/api/backend/" + path),
      path,
      env,
      async () =>
        new Response("exact bytes", { headers: { "Content-Type": type } }),
    );
    assert.equal(await r.text(), "exact bytes");
    assert.equal(
      r.headers.get("content-security-policy"),
      type === "application/pdf" ? "frame-ancestors 'self'" : "sandbox",
    );
    assert.ok(
      r.headers
        .get("content-disposition")
        .startsWith(type === "application/pdf" ? "inline" : "attachment"),
    );
  }
});
test("browser Host governs origin when Next internally uses localhost", async () => {
  const request = new Request(
    "http://localhost:3200/api/backend/research/questions",
    {
      method: "POST",
      headers: {
        Host: "127.0.0.1:3200",
        Origin: "http://127.0.0.1:3200",
        "Content-Type": "application/json",
      },
      body: "{}",
    },
  );
  const r = await relay(request, "research/questions", env, async () =>
    Response.json({ outcome: "clarify" }),
  );
  assert.equal(r.status, 200);
});
test("host rebinding and oversized bodies fail before backend access", async () => {
  let called = false;
  const hostile = new Request("http://evil.test:3200/api/backend/health", {
    headers: { Host: "evil.test:3200" },
  });
  assert.equal(
    (
      await relay(hostile, "health", env, () => {
        called = true;
      })
    ).status,
    403,
  );
  const large = new Request(
    "http://localhost:3200/api/backend/research/questions",
    {
      method: "POST",
      headers: {
        Origin: "http://localhost:3200",
        "Content-Type": "application/json",
      },
      body: "x".repeat(1024 * 1024 + 1),
    },
  );
  assert.equal(
    (
      await relay(large, "research/questions", env, () => {
        called = true;
      })
    ).status,
    413,
  );
  assert.equal(called, false);
});
