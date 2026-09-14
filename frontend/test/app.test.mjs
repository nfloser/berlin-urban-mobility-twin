import test from "node:test";
import assert from "node:assert/strict";

import { escapeHtml, freshnessLabel, isInsideBerlin, statusTone } from "../src/lib.mjs";

test("Berlin bounding-box helper filters clearly external coordinates", () => {
  assert.equal(isInsideBerlin(52.52, 13.405), true);
  assert.equal(isInsideBerlin(53.55, 9.99), false);
});

test("freshness and status labels expose degraded state rather than hiding it", () => {
  assert.equal(freshnessLabel("unknown"), "Unknown freshness");
  assert.equal(freshnessLabel(undefined), "Not loaded");
  assert.equal(statusTone("degraded"), "warn");
  assert.equal(statusTone("expired"), "bad");
});

test("popup text is escaped", () => {
  assert.equal(escapeHtml('<script>alert("x")</script>'), "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;");
});
