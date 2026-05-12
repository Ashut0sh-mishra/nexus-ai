const { chromium } = require("@playwright/test");
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext();
  const page = await ctx.newPage();
  page.on("console", (m) => console.log("[console]", m.type(), m.text()));
  page.on("pageerror", (e) => console.log("[pageerror]", e.message));
  page.on("requestfailed", (r) => console.log("[reqfailed]", r.url(), r.failure()?.errorText));
  const resp = await page.goto("http://localhost:5179/gallery", { waitUntil: "domcontentloaded" });
  console.log("status", resp && resp.status());
  await page.waitForTimeout(2500);
  const root = await page.$eval("#root", (el) => el.innerHTML.length);
  console.log("rootHtmlLen:", root);
  await b.close();
})();
