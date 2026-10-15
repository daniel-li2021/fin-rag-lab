const uuid = "[0-9a-fA-F-]{36}";
const run = "[0-9a-f]{64}";
const readPaths = [
  /^health$/,
  /^sources$/,
  new RegExp(`^sources/${uuid}$`),
  new RegExp(`^sources/${uuid}/versions$`),
  new RegExp(`^sources/${uuid}/observations$`),
  new RegExp(`^sources/${uuid}/versions/${uuid}/(?:raw|metadata-reviews)$`),
  /^research\/collections$/,
  /^research\/runs$/,
  new RegExp(`^research/runs/${run}$`),
];
const writePaths = [
  /^research\/(?:questions|evidence|evidence\/runs)$/,
  new RegExp(`^research/runs/${run}/rerun$`),
];

export function allowedPath(method, path) {
  return (
    method === "GET" ? readPaths : method === "POST" ? writePaths : []
  ).some((p) => p.test(path));
}

export async function relay(request, path, env = process.env, fetcher = fetch) {
  const reply = (message, status) =>
    Response.json(
      { detail: message },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  if (!allowedPath(request.method, path))
    return reply("Endpoint not available in the research workspace", 404);
  const origin = request.headers.get("origin");
  // Next's internal URL may use localhost even when the browser uses 127.0.0.1.
  const ownURL = new URL(request.url);
  if (request.headers.has("host")) ownURL.host = request.headers.get("host");
  const ownOrigin = ownURL.origin;
  const trustedOrigins = env.FINRAG_WORKSPACE_ORIGIN
    ? [env.FINRAG_WORKSPACE_ORIGIN]
    : ["http://127.0.0.1:3200", "http://localhost:3200", "http://[::1]:3200"];
  if (!trustedOrigins.includes(ownOrigin))
    return reply("Workspace host is not allowed", 403);
  if (
    (origin && origin !== ownOrigin) ||
    request.headers.get("sec-fetch-site") === "cross-site"
  )
    return reply("Cross-origin access denied", 403);
  if (request.method === "POST" && origin !== ownOrigin)
    return reply("Same-origin request required", 403);
  if (!env.FINRAG_BACKEND_URL || !env.FINRAG_API_TOKEN)
    return reply("Private backend is not configured", 503);
  const upstream = new URL(path, env.FINRAG_BACKEND_URL.replace(/\/?$/, "/"));
  upstream.search = new URL(request.url).search;
  let body;
  if (request.method === "POST") {
    if (!request.headers.get("content-type")?.startsWith("application/json"))
      return reply("JSON body required", 415);
    const reader = request.body?.getReader(),
      chunks = [];
    let size = 0;
    if (reader) {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > 1024 * 1024) {
          await reader.cancel();
          return reply("Request too large", 413);
        }
        chunks.push(value);
      }
    }
    const bytes = new Uint8Array(size);
    let position = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, position);
      position += chunk.length;
    }
    body = new TextDecoder().decode(bytes);
  }
  try {
    const response = await fetcher(upstream, {
      method: request.method,
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(90000)]),
      headers: {
        Authorization: `Bearer ${env.FINRAG_API_TOKEN}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
    });
    if (response.status >= 500)
      return reply(
        "Backend request failed. Your previous result remains available.",
        502,
      );
    if (response.status === 401)
      return reply("Private backend credential rejected", 503);
    const type =
      response.headers.get("content-type") || "application/octet-stream";
    const headers = {
      "Content-Type": type,
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    };
    if (path.endsWith("/raw")) {
      headers["Content-Disposition"] =
        type === "application/pdf"
          ? 'inline; filename="original.pdf"'
          : 'attachment; filename="original"';
      headers["Content-Security-Policy"] =
        type === "application/pdf" ? "frame-ancestors 'self'" : "sandbox";
    }
    return new Response(response.body, { status: response.status, headers });
  } catch {
    return reply(
      "Backend unavailable or request timed out. Retry explicitly; no automatic rerun.",
      502,
    );
  }
}
