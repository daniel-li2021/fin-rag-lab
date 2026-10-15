import { dataAccess } from "../../../../lib/data-access.mjs";
export const dynamic = "force-dynamic";
async function handle(request, { params }) {
  return dataAccess(request, (await params).path.join("/"));
}
export { handle as GET, handle as POST };
