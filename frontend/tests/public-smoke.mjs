import assert from "node:assert/strict";
export async function publicSmoke(tab, base = "http://127.0.0.1:3250") {
  const p = tab.playwright, checks = [];
  const nav = name => p.getByRole("navigation", {name:"Main navigation"}).getByRole("button",{name,exact:true});
  const verify = async (label, terms) => {
    const text = await p.locator("body").innerText();
    for (const term of terms) assert.ok(text.toLowerCase().includes(term.toLowerCase()),`${label}: ${term}`);
    assert.ok(!text.includes("Request could not complete"),label);
    checks.push(label);
  };
  for (const [hero, terms] of [
    ["equity",["1,172","5,214","Common-equity comparison"]],
    ["recast",["1,390","1,400","2,173"]],
    ["partial",["4,313","Useful partial answers"]],
    ["narrative",["Period-aware narrative","Q1 2025","Q2 2025"]],
    ["change",["1,129","1,390","Original execution","Separate rerun"]],
    ["calculation",["+6.61%","Revenue growth, precisely."]],
  ]) {
    await tab.goto(`${base}/?view=research&hero=${hero}`);
    await p.getByText("Saved public demo",{exact:true}).waitFor({state:"visible"});
    await p.getByRole("heading",{name:"Evidence Inspector",exact:true}).count();
    await p.locator(".query-card").waitFor({state:"visible"});
    await verify(hero,terms);
  }
  await p.getByRole("button",{name:"Source page",exact:true}).click();
  await verify("official source policy",["not redistributed","Exact saved excerpts"]);
  await p.getByRole("button",{name:"Provenance",exact:true}).click();
  await verify("provenance",["source id","version id","sha256"]);
  await p.getByRole("separator",{name:"Resize Evidence Inspector"}).press("ArrowLeft");
  await nav("Library").click();
  await p.locator(".source-card").first().waitFor({state:"visible"});
  await verify("library",["Source Library","preserved sources"]);
  await p.locator(".source-card").first().getByRole("button",{name:"Inspect"}).click();
  await p.getByLabel("Source version").waitFor({state:"visible"});
  await p.getByRole("button",{name:"Reviewed cards",exact:true}).click();
  await p.locator(".library-fact").first().waitFor({state:"visible"});
  await verify("reviewed cards",["Original bindings and review provenance"]);
  await nav("History").click();
  await p.getByLabel("Search saved history").fill("Rank");
  await p.locator(".history-card").first().waitFor({state:"visible"});
  await p.locator(".history-card").first().click();
  await p.locator(".query-card").waitFor({state:"visible"});
  await verify("immutable history reopen",["Preserved capture","new reruns require private live access"]);
  assert.equal(await p.getByRole("button",{name:"Run again using current sources"}).isEnabled(),false);
  await nav("Hero Scenarios").click();
  assert.equal(await p.locator(".hero-card").count(),5);
  checks.push("five interactive Hero cards");
  return checks;
}

export async function publicMobileSmoke(tab, base = "http://127.0.0.1:3250") {
  const p = tab.playwright;
  await tab.goto(`${base}/?view=research&hero=equity`);
  await p.locator(".query-card").waitFor({state:"visible"});
  await p.getByRole("button",{name:"Inspect evidence",exact:true}).click();
  await p.getByRole("button",{name:"Select citation 2",exact:true}).click();
  assert.ok((await p.locator(".inspector").innerText()).includes("5,214"));
  await p.getByRole("button",{name:"Return to research",exact:true}).click();
  await p.locator(".mobile-nav").getByRole("button",{name:"History",exact:true}).click();
  await p.locator(".history-card").first().waitFor({state:"visible"});
  return ["mobile evidence selection and return", "mobile history navigation"];
}

export async function publicUXSmoke(tab, base = "http://127.0.0.1:3250") {
  const p = tab.playwright, checks = [];
  const nav = name => p.getByRole("navigation", {name:"Main navigation"}).getByRole("button",{name,exact:true});
  await tab.goto(`${base}/?view=history`);
  await p.locator(".history-card").first().click();
  await p.locator(".query-card").waitFor({state:"visible"});
  const original = await p.locator(".query-card").innerText();
  await p.locator(".new-question").click();
  assert.equal(await p.locator(".query-card").count(), 0, "new research must clear the reopened answer");
  assert.equal(await p.getByRole("button",{name:"Export exact result JSON"}).count(),0);
  assert.equal(await p.locator(".starter-stories button").count(),5);
  await p.getByText("How to use this workspace",{exact:true}).click();
  assert.ok((await p.locator(".workflow-guide").innerText()).includes("Check the evidence"));
  await tab.back();
  await p.locator(".query-card").waitFor({state:"visible"});
  assert.equal(await p.locator(".query-card").innerText(),original);
  await tab.forward();
  await p.locator(".starter-stories").waitFor({state:"visible"});
  assert.equal(await p.locator(".query-card").count(),0);
  checks.push("history to fresh start, exact Back reopen and clean Forward");

  await p.locator(".starter-stories").getByRole("button",{name:/Source change/}).click();
  assert.ok((await p.locator(".scenario-pagination").innerText()).includes("Step 1 of 3"));
  assert.equal(await p.getByRole("button",{name:"Previous step",exact:true}).isEnabled(),false);
  await p.getByRole("button",{name:"Next step",exact:true}).click();
  assert.ok((await p.locator(".scenario-pagination").innerText()).includes("Step 2 of 3"));
  assert.ok((await p.locator(".query-card").innerText()).includes("latest reviewed"));
  await p.getByRole("button",{name:"Next step",exact:true}).click();
  assert.ok((await p.locator(".scenario-pagination").innerText()).includes("Step 3 of 3"));
  assert.equal(await p.getByRole("button",{name:"Next step",exact:true}).isEnabled(),false);
  await p.getByRole("button",{name:"Previous step",exact:true}).click();
  assert.ok((await p.locator(".scenario-pagination").innerText()).includes("Step 2 of 3"));
  checks.push("guided source-change steps preserve original and rerun navigation");

  await nav("Library").click();
  await p.getByLabel("Search source library").fill("no-such-source-ux-check");
  await p.getByRole("button",{name:"Clear source search",exact:true}).click();
  assert.ok(await p.locator(".source-card").count() > 0);
  await nav("History").click();
  await p.getByLabel("Search saved history").fill("no-such-history-ux-check");
  await p.getByRole("button",{name:"Clear history search",exact:true}).click();
  await p.locator(".history-card").first().waitFor({state:"visible"});
  checks.push("library and history empty searches recover in one action");
  return checks;
}

export async function publicMobileUXSmoke(tab, base = "http://127.0.0.1:3250") {
  const p = tab.playwright;
  await tab.goto(`${base}/?view=research&hero=equity`);
  await p.locator(".query-card").waitFor({state:"visible"});
  await p.getByRole("button",{name:"Inspect citation 2",exact:true}).click();
  assert.equal(await p.locator(".mobile-evidence-button").getAttribute("aria-expanded"),"true");
  assert.equal(await p.evaluate(() => document.activeElement?.getAttribute("aria-label")),"Return to research");
  await p.getByRole("button",{name:"Return to research",exact:true}).press("Escape");
  await p.locator(".query-card").waitFor({state:"visible"});
  assert.equal(await p.evaluate(() => document.activeElement?.getAttribute("aria-label")),"Inspect citation 2");
  await p.getByRole("button",{name:"Inspect evidence",exact:true}).click();
  await p.getByRole("button",{name:"Return to research",exact:true}).click();
  assert.equal(await p.evaluate(() => document.activeElement?.textContent?.trim()),"Inspect evidence");
  await p.locator(".mobile-nav").getByRole("button",{name:"Hero Scenarios",exact:true}).click();
  await p.locator(".hero-card").filter({hasText:"Source change"}).click();
  await p.getByRole("button",{name:"Next step",exact:true}).click();
  assert.ok((await p.locator(".scenario-pagination").innerText()).includes("Step 2 of 3"));
  assert.equal(await p.evaluate(() => document.documentElement.scrollWidth > innerWidth),false);
  return ["mobile evidence Escape and return restore triggering focus", "mobile scenario navigation has no horizontal overflow"];
}
