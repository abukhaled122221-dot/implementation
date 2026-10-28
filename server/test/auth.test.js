const { test } = require("node:test");
const assert = require("node:assert/strict");
const { makeHarness, register } = require("./helpers");
test("auth me response and registration field validation contract", async (t) => {
  const h = await makeHarness();
  t.after(() => h.close());
  const invalid = await h.call("/api/auth/register", "POST", {
    username: "x",
    email: "bad",
    password: "weak",
    confirmPassword: "mismatch",
  });
  assert.equal(invalid.status, 422);
  const payload = await invalid.json();
  assert.equal(payload.error, "تحقق من البيانات المدخلة");
  assert.deepEqual(
    payload.errors.map((x) => x.field),
    ["username", "email", "password", "confirm_password"],
  );
  const { response, cookie } = await register(h, "authuser");
  assert.equal(response.status, 201);
  const me = await (
    await h.call("/api/auth/me", "GET", undefined, cookie)
  ).json();
  assert.deepEqual(Object.keys(me.user), ["UserId", "UserName", "Email"]);
  const duplicate = await h.call("/api/auth/register", "POST", {
    username: "authuser",
    email: "other@example.test",
    password: "Passw0rd1",
    confirm_password: "Passw0rd1",
  });
  assert.equal(duplicate.status, 409);
  assert.equal((await duplicate.json()).errors[0].field, "username");
});
