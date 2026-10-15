import { chromium } from "@playwright/test";
import {
  browserRegression,
  responsiveRegression,
} from "../tests/browser-regression.mjs";
const browser = await chromium.launch({ channel: "chrome" });
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const adapter = new Proxy(page, {
    get: (target, key) =>
      key === "domSnapshot"
        ? () => target.locator("body").ariaSnapshot()
        : typeof target[key] === "function"
          ? target[key].bind(target)
          : target[key],
  });
  const passed = await browserRegression({
    playwright: adapter,
    goto: (url) => page.goto(url),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await responsiveRegression({
    playwright: adapter,
    goto: (url) => page.goto(url),
  });
  console.log(
    JSON.stringify({
      passed: passed.length + mobile.length,
      checks: [...passed, ...mobile],
    }),
  );
} finally {
  await browser.close();
}
