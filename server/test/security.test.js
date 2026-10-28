const { test } = require("node:test");
const assert = require("node:assert/strict");
const { makeHarness } = require("./helpers");
test("unauthenticated APIs and malformed JSON remain protected", async (t) => {
  const h = await makeHarness();
  t.after(() => h.close());
  assert.equal((await h.call("/api/history")).status, 401);
  assert.equal((await h.call("/api/admin/overview")).status, 401);
  const unknown = await h.call("/api/nope");
  assert.equal(unknown.status, 404);
  assert.ok(unknown.headers.get("content-type").includes("application/json"));
});
