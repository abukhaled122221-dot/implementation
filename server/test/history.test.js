const { test } = require("node:test");
const assert = require("node:assert/strict");
const { makeHarness, register, recommendation } = require("./helpers");
test("history list pagination and detail parse persisted JSON fields", async (t) => {
  const h = await makeHarness();
  t.after(() => h.close());
  const { cookie } = await register(h, "historyuser");
  const response = await h.call(
    "/api/recommend",
    "POST",
    recommendation,
    cookie,
  );
  assert.equal(response.status, 200);
  const id = (await response.json()).request_id;
  const list = await (
    await h.call("/api/history?page=1&pageSize=1", "GET", undefined, cookie)
  ).json();
  assert.deepEqual(Object.keys(list), ["items", "total", "page", "pageSize"]);
  assert.equal(list.items[0].RequestId, id);
  assert.equal(list.pageSize, 1);
  const clamped = await (
    await h.call("/api/history?pageSize=0", "GET", undefined, cookie)
  ).json();
  assert.equal(clamped.pageSize, 1);
  const detail = await (
    await h.call(`/api/history/${id}`, "GET", undefined, cookie)
  ).json();
  assert.equal(detail.request.RequestId, id);
  assert.equal(typeof detail.request.RequestPayload, "object");
  assert.ok(Array.isArray(detail.quotes[0].AddOns));
  assert.ok(detail.quotes[0].ProviderName);
  assert.ok(detail.recommendation);
  assert.equal(typeof detail.explanation.CriteriaBreakdown, "object");
  const notOwned = await register(h, "notowner");
  assert.equal(
    (await h.call(`/api/history/${id}`, "GET", undefined, notOwned.cookie))
      .status,
    404,
  );
});
