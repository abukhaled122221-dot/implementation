const { test } = require("node:test");
const assert = require("node:assert/strict");
const { makeHarness, register, recommendation } = require("./helpers");
test("agents timeout returns 502 and persists a failed request", async (t) => {
  const h = await makeHarness({ delayMs: 200, timeoutMs: 25 });
  t.after(() => h.close());
  const { cookie } = await register(h, "timeoutuser");
  const response = await h.call(
    "/api/recommend",
    "POST",
    recommendation,
    cookie,
  );
  assert.equal(response.status, 502);
  const row = h.db
    .prepare(
      "SELECT Status,ErrorMessage FROM Quote_Requests ORDER BY RequestId DESC LIMIT 1",
    )
    .get();
  assert.equal(row.Status, "failed");
  assert.equal(row.ErrorMessage, "Agents service timeout");
});

test("recommendation persistence and unknown API route contracts", async (t) => {
  const h = await makeHarness();
  t.after(() => h.close());
  const { cookie } = await register(h, "recommenduser");
  const result = await h.call("/api/recommend", "POST", recommendation, cookie);
  assert.equal(result.status, 200);
  const id = (await result.json()).request_id;
  assert.equal(
    h.db.prepare("SELECT Status FROM Quote_Requests WHERE RequestId=?").get(id)
      .Status,
    "success",
  );
  assert.equal(
    h.db
      .prepare("SELECT count(*) n FROM Retrieved_Quotes WHERE RequestId=?")
      .get(id).n,
    1,
  );
  const unknown = await h.call("/api/nope");
  assert.equal(unknown.status, 404);
  assert.match(unknown.headers.get("content-type"), /application\/json/);
});
