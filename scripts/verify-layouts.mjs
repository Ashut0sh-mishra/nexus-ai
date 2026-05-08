#!/usr/bin/env node
/**
 * verify-layouts.mjs — backend ↔ frontend layout-registry parity check.
 *
 * Run locally: `npm run verify:layouts`
 * In CI: same command; non-zero exit fails the build.
 *
 * What it checks:
 *   1. Every canonical layout in the JSON registry has a Python entry in
 *      backend/agent/layouts_registry.py::_INLINE_FALLBACK (in case the
 *      frontend file isn't shipped with the container).
 *   2. Every alias in the JSON has a matching Python alias.
 *   3. Every "exported": true layout has an `elif layout == "..."` branch
 *      in backend/services/export_service.py.
 *   4. Every canonical layout has a renderer registered in
 *      frontend/src/components/SlideRenderer.jsx (the `layouts = { ... }`
 *      object) OR in SlideLayouts.EXTRA_LAYOUTS.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

const errors = [];
const warnings = [];
function fail(msg) { errors.push(msg); }
function warn(msg) { warnings.push(msg); }

// ── Load canonical JSON ────────────────────────────────────────────────────
const REGISTRY_PATH = resolve(ROOT, "frontend/src/design/layouts.registry.json");
const REGISTRY = JSON.parse(readFileSync(REGISTRY_PATH, "utf8"));
const canonical = new Set(REGISTRY.layouts.map((l) => l.name));
const exported = new Set(REGISTRY.layouts.filter((l) => l.exported).map((l) => l.name));
const aliases = REGISTRY.aliases;

// ── Check 1: Python inline fallback parity ─────────────────────────────────
const PY_REGISTRY_PATH = resolve(ROOT, "backend/agent/layouts_registry.py");
const pySrc = readFileSync(PY_REGISTRY_PATH, "utf8");

// Pull the `_INLINE_FALLBACK` block (we just substring-search the names).
canonical.forEach((name) => {
  // Match e.g. ("title", True) or ("metric-spotlight", True)
  const re = new RegExp(`"${name.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}"\\s*,\\s*(True|False)`);
  if (!re.test(pySrc)) {
    fail(`backend/agent/layouts_registry.py inline fallback missing canonical layout "${name}"`);
  }
});

Object.entries(aliases).forEach(([alias, target]) => {
  // Match e.g. "kpi_grid": "kpi"
  const re = new RegExp(`"${alias.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}"\\s*:\\s*"${target}"`);
  if (!re.test(pySrc)) {
    fail(`backend/agent/layouts_registry.py inline fallback missing alias "${alias}" → "${target}"`);
  }
});

// ── Check 2: exporter parity ───────────────────────────────────────────────
const EXPORT_PATH = resolve(ROOT, "backend/services/export_service.py");
const expSrc = readFileSync(EXPORT_PATH, "utf8");
exported.forEach((name) => {
  const re = new RegExp(`layout\\s*==\\s*"${name.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}"`);
  if (!re.test(expSrc)) {
    fail(`backend/services/export_service.py has no \`elif layout == "${name}"\` branch (registry says exported=true)`);
  }
});

// Reverse: any layout the exporter handles should be canonical.
const expHandled = [...expSrc.matchAll(/layout\s*==\s*"([^"]+)"/g)].map((m) => m[1]);
expHandled.forEach((n) => {
  if (!canonical.has(n)) {
    fail(`backend/services/export_service.py renders "${n}" but it isn't in the canonical registry`);
  }
});

// ── Check 3: frontend renderer coverage ────────────────────────────────────
const FE_RENDERER = resolve(ROOT, "frontend/src/components/SlideRenderer.jsx");
const FE_LAYOUTS = resolve(ROOT, "frontend/src/components/SlideLayouts.jsx");
const feRendererSrc = readFileSync(FE_RENDERER, "utf8");
const feLayoutsSrc = readFileSync(FE_LAYOUTS, "utf8");

// SlideRenderer's `layouts = { title: ..., bullets: ... }` object
const rendererKeys = new Set();
const layoutsBlock = feRendererSrc.match(/const\s+layouts\s*=\s*\{([\s\S]*?)\.\.\.EXTRA_LAYOUTS/);
if (layoutsBlock) {
  for (const m of layoutsBlock[1].matchAll(/(?:^|\s)([a-zA-Z0-9_-]+|"[^"]+")\s*:/g)) {
    rendererKeys.add(m[1].replace(/^"|"$/g, ""));
  }
}
// EXTRA_LAYOUTS keys
const extraBlock = feLayoutsSrc.match(/EXTRA_LAYOUTS\s*=\s*\{([\s\S]*?)\};/);
if (extraBlock) {
  for (const m of extraBlock[1].matchAll(/(?:^|\s|,)\s*([a-zA-Z0-9_-]+|"[^"]+")\s*:/g)) {
    rendererKeys.add(m[1].replace(/^"|"$/g, ""));
  }
}
canonical.forEach((name) => {
  if (!rendererKeys.has(name)) {
    fail(`Frontend has no renderer for canonical layout "${name}". Register it in SlideRenderer.layouts or SlideLayouts.EXTRA_LAYOUTS.`);
  }
});

// ── Report ─────────────────────────────────────────────────────────────────
if (warnings.length) {
  console.warn("⚠ verify-layouts warnings:");
  warnings.forEach((w) => console.warn("  - " + w));
}
if (errors.length) {
  console.error("✘ verify-layouts FAILED — backend/frontend drift detected:");
  errors.forEach((e) => console.error("  - " + e));
  process.exit(1);
}
console.log(`✔ verify-layouts OK — ${canonical.size} canonical layouts, ${Object.keys(aliases).length} aliases, ${exported.size} exported.`);
