#!/usr/bin/env node
/**
 * verify-layouts.mjs — Phase 1A parity check.
 *
 * Fails (exit 1) if any of the following is true:
 *   1. backend and frontend canonical-layout JSON files have drifted.
 *   2. backend/agent/loop.py reintroduces a hardcoded layout literal.
 *   3. frontend/src/utils/slideParser.js reintroduces a hardcoded layout
 *      literal.
 *   4. either source file no longer imports the canonical registry.
 *
 * Designed to be safe to run from the repo root or from frontend/.
 */

import { readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
// scripts/verify-layouts.mjs lives at <repo>/scripts/, so repo root = parent.
const REPO_ROOT = resolve(__dirname, "..");

const BACKEND_REGISTRY = resolve(
  REPO_ROOT,
  "backend/agent/layouts.registry.json"
);
const FRONTEND_REGISTRY = resolve(
  REPO_ROOT,
  "frontend/src/design/layouts.registry.json"
);
const BACKEND_LOOP = resolve(REPO_ROOT, "backend/agent/loop.py");
const BACKEND_PLANNER = resolve(REPO_ROOT, "backend/agent/planner.py");
const FRONTEND_PARSER = resolve(REPO_ROOT, "frontend/src/utils/slideParser.js");

const failures = [];

function fail(msg) {
  failures.push(msg);
}

// -- Check 1: backend + frontend registry JSON content equality --
let registryNames = [];
try {
  if (!existsSync(BACKEND_REGISTRY)) {
    fail(`missing file: ${BACKEND_REGISTRY}`);
  }
  if (!existsSync(FRONTEND_REGISTRY)) {
    fail(`missing file: ${FRONTEND_REGISTRY}`);
  }
  if (existsSync(BACKEND_REGISTRY) && existsSync(FRONTEND_REGISTRY)) {
    const backend = JSON.parse(readFileSync(BACKEND_REGISTRY, "utf8"));
    const frontend = JSON.parse(readFileSync(FRONTEND_REGISTRY, "utf8"));
    if (JSON.stringify(backend) !== JSON.stringify(frontend)) {
      fail(
        "backend/agent/layouts.registry.json and frontend/src/design/layouts.registry.json have drifted"
      );
    }
    registryNames = (backend.layouts || []).map((l) => l.name);
    if (registryNames.length === 0) {
      fail("registry has zero layouts");
    }
  }
} catch (err) {
  fail(`registry parse error: ${err.message}`);
}

// -- Check 2: backend/agent/loop.py imports registry, no hardcoded literal --
if (existsSync(BACKEND_LOOP)) {
  const src = readFileSync(BACKEND_LOOP, "utf8");
  if (!/from\s+agent\.layouts_registry\s+import/.test(src)) {
    fail("backend/agent/loop.py does not import from agent.layouts_registry");
  }
  // Look for an inline set/frozenset literal listing >=3 canonical layout names.
  const literalPattern =
    /_VALID_LAYOUTS\s*=\s*(?:frozenset\s*\(\s*)?\{([^}]+)\}/;
  const m = src.match(literalPattern);
  if (m) {
    const inside = m[1];
    const hits = registryNames.filter((n) =>
      new RegExp(`["']${n}["']`).test(inside)
    );
    if (hits.length >= 3) {
      fail(
        `backend/agent/loop.py contains a hardcoded _VALID_LAYOUTS literal (${hits.length} canonical names found inline). Source layouts from the registry instead.`
      );
    }
  }
} else {
  fail(`missing file: ${BACKEND_LOOP}`);
}

// -- Check 2b: backend/agent/planner.py imports registry, no hardcoded literal --
if (existsSync(BACKEND_PLANNER)) {
  const src = readFileSync(BACKEND_PLANNER, "utf8");
  if (!/from\s+agent\.layouts_registry\s+import/.test(src)) {
    fail(
      "backend/agent/planner.py does not import from agent.layouts_registry"
    );
  }
  const literalPattern =
    /_VALID_LAYOUTS\s*=\s*(?:frozenset\s*\(\s*)?\{([^}]+)\}/;
  const m = src.match(literalPattern);
  if (m) {
    const inside = m[1];
    const hits = registryNames.filter((n) =>
      new RegExp(`["']${n}["']`).test(inside)
    );
    if (hits.length >= 3) {
      fail(
        `backend/agent/planner.py contains a hardcoded _VALID_LAYOUTS literal (${hits.length} canonical names found inline). Source layouts from the registry instead.`
      );
    }
  }
} else {
  fail(`missing file: ${BACKEND_PLANNER}`);
}

// -- Check 3: frontend/src/utils/slideParser.js imports registry, no inline Set --
if (existsSync(FRONTEND_PARSER)) {
  const src = readFileSync(FRONTEND_PARSER, "utf8");
  if (!/from\s+["']\.\.\/design\/registry(\.js)?["']/.test(src)) {
    fail(
      "frontend/src/utils/slideParser.js does not import from ../design/registry"
    );
  }
  // Look for: const VALID_LAYOUTS = new Set([ "...", "...", ...
  const literalPattern = /VALID_LAYOUTS\s*=\s*new\s+Set\s*\(\s*\[([^\]]*)\]/;
  const m = src.match(literalPattern);
  if (m) {
    const inside = m[1];
    const hits = registryNames.filter((n) =>
      new RegExp(`["']${n}["']`).test(inside)
    );
    if (hits.length >= 3) {
      fail(
        `frontend/src/utils/slideParser.js contains a hardcoded VALID_LAYOUTS Set literal (${hits.length} canonical names found inline). Source layouts from the registry instead.`
      );
    }
  }
} else {
  fail(`missing file: ${FRONTEND_PARSER}`);
}

if (failures.length > 0) {
  console.error("✖ verify-layouts FAIL");
  for (const f of failures) console.error("  - " + f);
  process.exit(1);
}

const exported = (
  JSON.parse(readFileSync(BACKEND_REGISTRY, "utf8")).layouts || []
).filter((l) => l.exported).length;
console.log(
  `✔ verify-layouts OK — ${registryNames.length} canonical layouts, ${exported} exported.`
);
