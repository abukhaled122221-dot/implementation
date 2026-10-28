const { test } = require("node:test");
const assert = require("node:assert/strict");
const bcrypt = require("bcryptjs");
const { makeHarness, register, recommendation } = require("./helpers");
test("admin list filters and settings secrets plus referenced provider delete", async (t) => {
  const h = await makeHarness();
  t.after(() => h.close());
  const { cookie: customer } = await register(h, "admincase");
  const rec = await h.call("/api/recommend", "POST", recommendation, customer);
  const requestId = (await rec.json()).request_id;
  h.db
    .prepare(
      "INSERT INTO Users(UserName,Email,PasswordHash,IsAdmin) VALUES(?,?,?,1)",
    )
    .run("adminx", "adminx@example.test", await bcrypt.hash("Passw0rd1", 4));
  const login = await h.call("/api/admin/login", "POST", {
    identifier: "adminx",
    password: "Passw0rd1",
  });
  const admin = login.headers.get("set-cookie").split(";")[0];
  const users = await (
    await h.call(
      "/api/admin/users?q=admincase&page=1&pageSize=1",
      "GET",
      undefined,
      admin,
    )
  ).json();
  assert.equal(users.total, 1);
  assert.equal(users.items[0].RequestsCount, 1);
  assert.equal(users.pageSize, 1);
  const logs = await (
    await h.call(
      "/api/admin/logs?status=success&q=التعاونية&page=1&pageSize=1",
      "GET",
      undefined,
      admin,
    )
  ).json();
  assert.equal(logs.total, 1);
  assert.equal(logs.items[0].RequestId, requestId);
  assert.equal(logs.items[0].QuotesCount, 1);
  const requestDate = h.db
    .prepare("SELECT date(Timestamp) day FROM Quote_Requests WHERE RequestId=?")
    .get(requestId).day;
  const dateFilter = await (
    await h.call(
      `/api/admin/logs?status=success&q=admincase&from=${requestDate}&to=${requestDate}&page=1&pageSize=20`,
      "GET",
      undefined,
      admin,
    )
  ).json();
  assert.equal(dateFilter.total, 1);
  const failedFilter = await (
    await h.call(
      "/api/admin/logs?status=failed&page=1&pageSize=20",
      "GET",
      undefined,
      admin,
    )
  ).json();
  assert.equal(failedFilter.total, 0);
  const providerList = await (
    await h.call("/api/admin/providers", "GET", undefined, admin)
  ).json();
  assert.ok(
    providerList.items.some(
      (x) => x.ProviderId === "tawuniya" && x.QuotesCount === 1,
    ),
  );
  const details = await (
    await h.call(`/api/admin/logs/${requestId}`, "GET", undefined, admin)
  ).json();
  assert.equal(details.user.UserName, "admincase");
  assert.equal(details.request.RequestId, requestId);
  const updated = await h.call(
    "/api/admin/api-settings/tawuniya",
    "PUT",
    {
      endpoint: "https://example.test/api",
      auth_scheme: "x-api-key",
      adapter: "tawuniya",
      protocol: "REST/JSON",
      timeout: 3,
      auth_key: "secret-9876",
    },
    admin,
  );
  assert.equal(updated.status, 200);
  await h.call(
    "/api/admin/api-settings/tawuniya",
    "PUT",
    {
      endpoint: "https://example.test/next",
      auth_scheme: "x-api-key",
      adapter: "tawuniya",
      protocol: "REST/JSON",
      timeout: 4,
      auth_key: "",
    },
    admin,
  );
  const settings = await (
    await h.call("/api/admin/api-settings", "GET", undefined, admin)
  ).json();
  const setting = settings.items.find((x) => x.ProviderId === "tawuniya");
  assert.equal(setting.Protocol, "REST/JSON");
  assert.equal(setting.AuthKeyLast4, "9876");
  assert.equal(setting.HasAuthKey, 1);
  assert.equal(JSON.stringify(setting).includes("secret"), false);
  const del = await h.call(
    "/api/admin/providers/tawuniya",
    "DELETE",
    undefined,
    admin,
  );
  assert.equal(del.status, 409);
  assert.equal((await del.json()).error !== undefined, true);
  const audit = await (
    await h.call("/api/admin/audit?page=1&pageSize=1", "GET", undefined, admin)
  ).json();
  assert.equal(audit.items.length, 1);
  assert.equal(typeof audit.items[0].Details, "object");
});
