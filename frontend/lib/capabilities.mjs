export function capabilities(env = process.env) {
  return Object.fromEntries(
    ["research", "library", "history", "collections", "evidence"].map((name) => [
      name,
      env[`FINRAG_${name.toUpperCase()}_MODE`] === "live" ? "live" : "demo",
    ]),
  );
}

export function featureFor(path) {
  if (path.startsWith("sources/") && path.endsWith("/raw")) return "evidence";
  if (path === "sources" || path.startsWith("sources/")) return "library";
  if (path === "research/collections") return "collections";
  if (path === "research/runs" || /^research\/runs\/[a-f0-9]{64}$/.test(path))
    return "history";
  return "research";
}
