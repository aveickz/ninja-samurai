#!/usr/bin/env node
// export_cards.mjs — reads js/cards.js as text, evaluates it, and writes
// simulations/data/cards.json with English-only fields (see simulation.md §3.1).
//
// Usage: node simulations/engine/export_cards.mjs
// (run from any cwd; paths below are resolved relative to this file)

import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const CARDS_JS = path.join(REPO_ROOT, "js", "cards.js");
const OUT_DIR = path.join(REPO_ROOT, "simulations", "data");
const OUT_FILE = path.join(OUT_DIR, "cards.json");

function loadCards() {
  const src = readFileSync(CARDS_JS, "utf8");
  // js/cards.js declares `const CARDS = [...]` and nothing else we need.
  // Evaluate it in a fresh Function scope and hand back the array.
  const fn = new Function(src + ";return CARDS;");
  return fn();
}

function nlToNewline(text) {
  if (text == null) return "";
  return String(text).replace(/\[NL\]/g, "\n");
}

function exportCard(c) {
  return {
    id: c.id,
    name: c.enTitle != null ? c.enTitle : c.title,
    types: Array.isArray(c.types) ? c.types.slice() : [],
    group: c.group != null ? c.group : null,
    qty: typeof c.qty === "number" ? c.qty : 0,
    icons: Array.isArray(c.icons) ? c.icons.slice() : [],
    icons_or: Array.isArray(c.iconsOr) ? c.iconsOr.slice() : null,
    tags: Array.isArray(c.tags) ? c.tags.slice() : [],
    text: nlToNewline(c.enDesc),
    hp: typeof c.hp === "number" ? c.hp : null,
    // js/cards.js has no English subtitle field (only the Russian original) —
    // "English fields only" (§3.1) means we leave it null rather than leak
    // Russian text into an otherwise English-only export.
    subtitle: null,
  };
}

function main() {
  const CARDS = loadCards();
  const out = CARDS.map(exportCard);

  writeFileSync(OUT_FILE, JSON.stringify(out, null, 2) + "\n", "utf8");

  // One-line summary: kinds by group, and deck size (deck-eligible cards,
  // i.e. group not role/character, tags without trash/draft), summed by qty.
  const kindCounts = new Map();
  let deckSize = 0;
  let deckKinds = 0;
  for (const c of out) {
    const g = c.group || "?";
    kindCounts.set(g, (kindCounts.get(g) || 0) + 1);
    const isRoleOrChar = g === "role" || g === "character";
    const tags = c.tags || [];
    const excluded = tags.includes("trash") || tags.includes("draft");
    if (!isRoleOrChar && !excluded) {
      deckSize += c.qty;
      deckKinds += 1;
    }
  }
  const kindsStr = [...kindCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([g, n]) => `${g}:${n}`)
    .join(" ");
  console.log(
    `Exported ${out.length} cards (${kindsStr}) -> ${path.relative(REPO_ROOT, OUT_FILE)}; ` +
      `deck-eligible kinds: ${deckKinds}, deck size (excl. trash/draft): ${deckSize}`
  );
}

main();
