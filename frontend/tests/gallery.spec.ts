import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REGISTRY = JSON.parse(
  readFileSync(resolve(__dirname, "../src/design/layouts.registry.json"), "utf8"),
);
const CANONICAL: string[] = REGISTRY.layouts.map((l: { name: string }) => l.name);
const ALIASES: Record<string, string> = REGISTRY.aliases;

// ─── 1. Gallery renders without console warnings ───────────────────────────
test.describe("Gallery", () => {
  test("loads with zero unsupported-layout warnings", async ({ page }) => {
    const warnings: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "warning" || msg.type() === "warn") {
        const txt = msg.text();
        // Only flag SlideRenderer / design-system warnings.
        if (/SlideRenderer|Unsupported|registry/i.test(txt)) {
          warnings.push(txt);
        }
      }
    });
    await page.goto("/gallery");
    await page.waitForSelector("figure");
    // Give renderers a beat to settle.
    await page.waitForTimeout(500);
    expect(warnings, `Unexpected SlideRenderer warnings:\n${warnings.join("\n")}`).toHaveLength(0);
  });

  // ─── 2. Coverage: every canonical layout has a figure on the gallery page ─
  test("every canonical layout is present on the gallery page", async ({ page }) => {
    await page.goto("/gallery");
    await page.waitForSelector("figure");
    const captions = await page.$$eval("figure figcaption", (els) =>
      els.map((e) => e.textContent || ""),
    );
    const present = captions
      .map((t) => t.match(/layout = "([^"]+)"/)?.[1])
      .filter((x): x is string => !!x);
    const missing = CANONICAL.filter((n) => !present.includes(n));
    expect(missing, `Gallery missing layouts: ${missing.join(", ")}`).toHaveLength(0);
  });

  // ─── 3. Per-layout snapshot — pixel diff catches visual regressions ─────
  for (const layout of CANONICAL) {
    test(`snapshot: ${layout}`, async ({ page }) => {
      await page.goto("/gallery");
      const figure = page.locator(`figure:has(figcaption:text("${layout}"))`);
      await expect(figure).toBeVisible();
      // Stabilize: disable animations.
      await page.addStyleTag({ content: "*, *::before, *::after { animation: none !important; transition: none !important; }" });
      await expect(figure).toHaveScreenshot(`${layout}.png`, {
        maxDiffPixelRatio: 0.02,
      });
    });
  }
});

// ─── 4. Alias resolution smoke test ────────────────────────────────────────
// Verifies that every alias key resolves to a canonical name that has a
// gallery card. Catches the "alias points at a canonical name we forgot to
// register a renderer for" class of bug.
test("every alias targets a renderable canonical layout", async ({ page }) => {
  await page.goto("/gallery");
  await page.waitForSelector("figure");
  const captions = await page.$$eval("figure figcaption", (els) =>
    els.map((e) => (e.textContent || "").match(/"([^"]+)"/)?.[1] || ""),
  );
  const present = new Set(captions);
  const broken = Object.entries(ALIASES).filter(([, target]) => !present.has(target));
  expect(broken, `Aliases pointing at unrendered layouts: ${broken.map(([a, t]) => `${a}→${t}`).join(", ")}`).toHaveLength(0);
});
