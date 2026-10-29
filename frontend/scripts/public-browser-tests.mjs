import { chromium } from "@playwright/test";
import { publicSmoke, publicMobileSmoke, publicUXSmoke, publicMobileUXSmoke } from "../tests/public-smoke.mjs";
const browser = await chromium.launch({channel:"chrome"});
try {
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const tab = {playwright:page,goto:url=>page.goto(url),back:()=>page.goBack(),forward:()=>page.goForward()};
  const checks = await publicSmoke(tab,process.env.FINRAG_SMOKE_URL);
  checks.push(...await publicUXSmoke(tab,process.env.FINRAG_SMOKE_URL));
  await page.setViewportSize({width:390,height:844});
  checks.push(...await publicMobileSmoke(tab,process.env.FINRAG_SMOKE_URL));
  checks.push(...await publicMobileUXSmoke(tab,process.env.FINRAG_SMOKE_URL));
  console.log(JSON.stringify({passed:checks.length,checks}));
} finally { await browser.close(); }
