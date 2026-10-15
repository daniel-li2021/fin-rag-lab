import assert from "node:assert/strict";

// Runs via the documented CUA tab APIs, or the Playwright adapter in scripts/browser-tests.
export async function browserRegression(tab) {
  const p = tab.playwright;
  const nav = (name) =>
    p
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("button", { name, exact: true });
  const observed = [];
  async function verify(label, required) {
    const snapshot = await p.domSnapshot();
    for (const text of required)
      assert.ok(snapshot.includes(text), `${label}: missing ${text}`);
    observed.push(label);
  }
  await tab.goto("http://127.0.0.1:3200/");
  await p
    .getByText("Live private backend", { exact: true })
    .waitFor({ state: "visible" });
  await p
    .getByLabel("Research question", { exact: true })
    .fill(
      "rank GAAP consolidated net income attributable to common for TSLA and WFC in Q2 2025",
    );
  await p
    .getByLabel("Research collection")
    .selectOption({ label: "Q2 2025 originals" });
  await p.getByRole("button", { name: "Run research", exact: true }).click();
  await p
    .getByRole("heading", {
      name: "Common-stockholder net income",
      exact: true,
    })
    .waitFor({ state: "visible" });
  await verify("live ranking", [
    "1,172",
    "5,214",
    "Complete, comparable ranking",
    "Saved execution",
  ]);
  await p.getByLabel("Select citation 2", { exact: true }).click();
  await verify("citation binding", ["Wells Fargo", "Page 58", "5,214"]);
  await p.getByRole("button", { name: "Source page", exact: true }).click();
  await p.getByText("SHA-256 verified · Original physical page 58", {exact:true}).waitFor({state:"visible"});
  await verify("live original navigation", [
    "Physical page 58",
    "Open pinned original",
  ]);
  await p.getByRole("button", { name: "Provenance", exact: true }).click();
  await verify("exact provenance", [
    "source id",
    "version id",
    "build id",
    "sha256",
    "Complete citation and review binding",
  ]);
  await p
    .getByRole("separator", { name: "Resize Evidence Inspector" })
    .press("ArrowLeft");
  await verify("keyboard resize", ["Evidence Inspector"]);
  await p
    .getByRole("button", {
      name: "Run again using current sources",
      exact: true,
    })
    .click();
  await p
    .getByRole("button", { name: "Open parent execution" })
    .waitFor({ state: "visible" });
  await verify("immutable parent-linked rerun", [
    "Original execution",
    "Separate rerun",
    "Answer unchanged",
    "Evidence unchanged",
  ]);
  await nav("History").click();
  await p
    .getByLabel("Search saved history")
    .fill("rank GAAP consolidated net income attributable to common");
  await p.locator(".history-card").first().waitFor({ state: "visible" });
  await verify("server history search", [
    "Saved History",
    "Parent-linked rerun",
  ]);
  await p.locator(".history-card").first().click();
  await p
    .getByRole("heading", {
      name: "Common-stockholder net income",
      exact: true,
    })
    .waitFor({ state: "visible" });
  await verify("history reopen", ["1,172", "5,214"]);
  await nav("History").click();
  await p.getByLabel("Search saved history").fill("");
  await p
    .getByRole("button", { name: "Next", exact: true })
    .waitFor({ state: "visible" });
  await p.getByRole("button", { name: "Next", exact: true }).click();
  await p.locator(".history-card").first().waitFor({ state: "visible" });
  await verify("history pagination", ["Page 2"]);
  await nav("Library").click();
  await p
    .getByLabel("Search source library")
    .fill("Wells Fargo & Company Q2 2025");
  await verify("library search", ["Wells Fargo & Company Q2 2025 10-Q"]);
  await p.getByRole("button", { name: "Inspect", exact: true }).click();
  await p
    .getByRole("button", { name: "Use this pinned version" })
    .waitFor({ state: "visible" });
  await verify("library versions", ["Source Inspector", "Version 1", "sha256"]);
  await p.getByRole("button", { name: "Reviewed cards", exact: true }).click();
  await p
    .getByText("Original bindings and review provenance", { exact: true })
    .first()
    .waitFor({ state: "visible" });
  await verify("reviewed fact cards", [
    "immutable reviewed cards",
    "Original bindings and review provenance",
  ]);
  await p.getByRole("button", { name: "Use this pinned version" }).click();
  await verify("library to pinned research", [
    "Pinned version",
    "1 selected / 18",
  ]);
  await nav("Hero Scenarios").click();
  await p
    .getByRole("main")
    .getByRole("button", { name: /01 Common-equity comparison/ })
    .click();
  await verify("hero 1", ["Preserved development result", "1,172", "5,214"]);
  await nav("Hero Scenarios").click();
  await p
    .getByRole("main")
    .getByRole("button", { name: /02 Recast-aware research/ })
    .click();
  await verify("hero 2 latest", ["1,390", "1,400", "2,173"]);
  await p.getByRole("button", { name: "As reported", exact: true }).click();
  await verify("hero 2 as reported", ["1,129", "1,478", "2,167"]);
  await nav("Hero Scenarios").click();
  await p
    .getByRole("main")
    .getByRole("button", { name: /03 Useful partial answers/ })
    .click();
  await p
    .getByRole("button", { name: "Difference withheld", exact: true })
    .click();
  await verify("hero 3 blocked arithmetic", ["4,313", "withheld"]);
  await nav("Hero Scenarios").click();
  await p
    .getByRole("main")
    .getByRole("button", { name: /04 Period-aware narrative/ })
    .click();
  await verify("hero 4 period citations", [
    "Q1 2025",
    "Q2 2025",
    "Generated · unreviewed",
    "18 candidates",
  ]);
  assert.equal(
    await p.getByLabel("Select citation 3", { exact: true }).count(),
    0,
    "Candidates must not be mislabeled as claim citations",
  );
  await nav("Hero Scenarios").click();
  await p
    .getByRole("main")
    .getByRole("button", { name: /05 Source change/ })
    .click();
  await p
    .getByRole("button", {
      name: "After metadata review · saved rerun",
      exact: true,
    })
    .click();
  await verify("hero 5 preserved transition", [
    "1,129",
    "1,390",
    "Controlled local original-byte transition",
    "Separate rerun",
  ]);
  await nav("Hero Scenarios").click();
  await p
    .getByRole("button", { name: /AMD · Exact revenue-growth receipt/ })
    .click();
  await verify("exact calculation", [
    "+6.61%",
    "5,473,000,000",
    "5,835,000,000",
    "2023-12-31",
    "2024-03-30",
  ]);
  return observed;
}

export async function responsiveRegression(tab) {
  const p = tab.playwright,
    passed = [];
  const verify = async (label, required) => {
    const snapshot = await p.domSnapshot();
    for (const text of required)
      assert.ok(snapshot.includes(text), `${label}: missing ${text}`);
    passed.push(label);
  };
  await tab.goto("http://127.0.0.1:3200/?hero=equity");
  await p
    .getByRole("heading", {
      name: "Common-stockholder net income",
      exact: true,
    })
    .waitFor({ state: "visible" });
  await p
    .getByRole("button", { name: "Inspect evidence", exact: true })
    .click();
  await verify("mobile evidence", ["Evidence Inspector", "Page 5"]);
  await p.getByLabel("Select citation 2", { exact: true }).click();
  await verify("mobile citation switch", ["Wells Fargo", "Page 58", "5,214"]);
  await p.getByRole("button", { name: "Source page", exact: true }).click();
  await verify("mobile source page", [
    "Physical page 58",
    "Open pinned original",
  ]);
  await p
    .getByRole("button", { name: "Return to results", exact: true })
    .click();
  await p
    .getByRole("main")
    .getByRole("button", { name: "New research" })
    .click();
  await p
    .getByLabel("Research question", { exact: true })
    .fill("growth GAAP consolidated revenue for AMD in Q1 2024 to Q2 2024");
  await p
    .getByLabel("Research collection")
    .selectOption({ label: "AMD reviewed history" });
  await p.getByRole("button", { name: "Run research", exact: true }).click();
  await p.getByText("+6.61%", { exact: false }).waitFor({ state: "visible" });
  await verify("mobile live calculation", [
    "+6.61%",
    "5,473,000,000",
    "5,835,000,000",
  ]);
  return passed;
}
