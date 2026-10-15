import test from "node:test";
import assert from "node:assert/strict";
import { dataAccess } from "../lib/data-access.mjs";
import { demoArchive } from "../lib/demo.mjs";
import { capabilities } from "../lib/capabilities.mjs";
const get = path => new Request(`http://localhost:3200/api/backend/${path}`);
const forbiddenFetch = () => { throw Error("Demo must not access the network"); };

test("default demo is network independent, including with stale backend credentials", async () => {
  const env = { FINRAG_BACKEND_URL:"https://offline.test", FINRAG_API_TOKEN:"secret" };
  const data = await demoArchive();
  for (const path of ["health","sources","research/collections","research/runs"]) {
    const response = await dataAccess(get(path),path,env,forbiddenFetch);
    assert.equal(response.status,200);
  }
  for (const r of [...data.scenarios.flatMap(s=>s.steps),data.calculation].map(s=>s.result).filter(r=>r.execution)) {
    const path = `research/runs/${r.run_id}`;
    const reopened = await (await dataAccess(get(path),path,env,forbiddenFetch)).json();
    assert.deepEqual(reopened.payload,r);
    assert.equal(reopened.demo,true);
  }
});
test("demo source versions and reviewed cards retain exact identities and money", async () => {
  const data = await demoArchive();
  for (const r of data.scenarios.flatMap(s=>s.steps).map(s=>s.result)) for (const pin of r.manifest) {
    const path = `sources/${pin.source_id}/versions`;
    const versions = await (await dataAccess(get(path),path,{},forbiddenFetch)).json();
    assert.ok(versions.some(v=>v.version_id===pin.version_id && v.sha256===pin.source_hash));
  }
  const path = "research/runs";
  const rows = await (await dataAccess(get(path+"?search=Rank&offset=0"),path,{},forbiddenFetch)).json();
  assert.ok(rows.length);
  assert.ok(rows.every(r=>r.question.toLowerCase().includes("rank")));
  assert.equal((await dataAccess(get(path+"?offset=-1"),path,{},forbiddenFetch)).status,400);
});
test("public writes and owner administration never reach backend", async () => {
  for (const path of ["research/questions","research/evidence/runs","research/runs/"+"a".repeat(64)+"/rerun","sources","research/collections"]) {
    const response = await dataAccess(new Request(get(path),{method:"POST"}),path,{},forbiddenFetch);
    assert.ok([403,404].includes(response.status));
  }
  assert.equal((await dataAccess(get("sources/private/upload"),"sources/private/upload",{},forbiddenFetch)).status,404);
});
test("feature-level activation requires private access before using owner token", async () => {
  const env = {FINRAG_LIBRARY_MODE:"live", FINRAG_WORKSPACE_PASSWORD:"private-password", FINRAG_BACKEND_URL:"https://backend.test", FINRAG_API_TOKEN:"backend-secret"};
  assert.deepEqual(capabilities(env),{research:"demo",library:"live",history:"demo",collections:"demo",evidence:"demo"});
  assert.equal((await dataAccess(get("sources"),"sources",env,forbiddenFetch)).status,401);
  assert.equal((await dataAccess(get("research/runs"),"research/runs",env,forbiddenFetch)).status,200);
  const request = new Request(get("sources"),{headers:{Authorization:"Basic "+Buffer.from("owner:private-password").toString("base64")}});
  const response = await dataAccess(request,"sources",env,async (url,options)=>{
    assert.equal(url.href,"https://backend.test/sources");
    assert.equal(options.headers.Authorization,"Bearer backend-secret");
    return Response.json([]);
  });
  assert.equal(response.status,200);
  assert.equal((await dataAccess(request,"sources",{...env,FINRAG_WORKSPACE_PASSWORD:""},forbiddenFetch)).status,401);
});
