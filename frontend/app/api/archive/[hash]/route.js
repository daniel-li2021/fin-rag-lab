import { demoArchive } from "../../../../lib/demo.mjs";
export const dynamic = "force-dynamic";
export async function GET(request, { params }) {
  const { hash } = await params;
  const archive = await demoArchive();
  const original = /^[a-f0-9]{64}$/.test(hash) && archive.originals[hash];
  if (!original?.url) return Response.json({ detail: "Official document link unavailable; exact saved excerpts remain accessible." }, { status: 404 });
  return Response.redirect(original.url, 307);
}
