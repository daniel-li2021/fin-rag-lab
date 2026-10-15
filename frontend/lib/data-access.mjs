import { capabilities, featureFor } from "./capabilities.mjs";
import { demoArchive, demoResponse } from "./demo.mjs";
import { relay, allowedPath } from "./relay.mjs";
import { createHash, timingSafeEqual } from "node:crypto";

export async function dataAccess(request, path, env = process.env, fetcher = fetch) {
  if (!allowedPath(request.method, path))
    return Response.json({ detail: "Endpoint unavailable" }, { status: 404 });
  const modes = capabilities(env);
  if (path === "health") return Response.json({ capabilities: modes, ready: true });
  if (modes[featureFor(path)] === "demo")
    return demoResponse(request, path, await demoArchive());
  // Feature flags alone never grant visitors access to owner data or paid generation.
  const expected = "Basic " + Buffer.from(
    `${env.FINRAG_WORKSPACE_USER || "owner"}:${env.FINRAG_WORKSPACE_PASSWORD || ""}`,
  ).toString("base64");
  const digest = (s) => createHash("sha256").update(s).digest();
  if (!env.FINRAG_WORKSPACE_PASSWORD || !timingSafeEqual(
    digest(request.headers.get("authorization") || ""), digest(expected),
  )) return Response.json({ detail: "Sign in to the private live workspace. Preserved Heroes remain public." }, {
    status: 401, headers: { "Cache-Control": "no-store", "WWW-Authenticate": 'Basic realm="FinRAG live workspace", charset="UTF-8"' },
  });
  return relay(request, path, env, fetcher);
}
