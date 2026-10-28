const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"),
  path = require("node:path"),
  http = require("node:http");
const tmp = fs.mkdtempSync(
  path.join(
    "C:/Users/Hessah/AppData/Local/hermes/profiles/mimo-v2-6-pro/cache/scratch/thiqa",
    "test-",
  ),
);
process.env.THIQA_DB_PATH = path.join(tmp, "test.db");
process.env.AGENTS_SERVICE_URL = "http://127.0.0.1:3189";
const agent = http.createServer((req, res) => {
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    res.setHeader("content-type", "application/json");
    if (req.url === "/providers/test") {
      res.end(
        JSON.stringify({
          provider_id: "tawuniya",
          ok: true,
          latency_ms: 5,
          offers_count: 1,
        }),
      );
      return;
    }
    if (req.url !== "/recommend") {
      res.statusCode = 404;
      return res.end("{}");
    }
    const input = JSON.parse(body || "{}");
    if (input.priority === "Service") {
      res.statusCode = 422;
      return res.end(
        JSON.stringify({
          error: "invalid",
          errors: [{ field: "priority", message: "invalid" }],
        }),
      );
    }
    if (input.priority === "Digital") {
      res.statusCode = 503;
      return res.end(
        JSON.stringify({ error: "providers unavailable", provider_status: [] }),
      );
    }
    res.end(
      JSON.stringify({
        recommended_package: {},
        all_offers_ranked: [
          {
            quote_id: "stub-1",
            provider_id: "tawuniya",
            provider_name: "Stub Provider",
            plan_name: "Gold Plan",
            premium: 1200,
            coverage_type: "TPL",
            deductible: 500,
            add_ons: ["roadside_assistance"],
            suitability_score: 0.91,
            rank: 1,
          },
        ],
        explanation: {
          main_reasons: "Stub reason",
          strengths: ["Strong"],
          criteria_explanations: ["Price"],
          comparison: "Comparison",
        },
        provider_status: [],
      }),
    );
  });
});
const { app, db } = require("../server");
let server, base;
before(async () => {
  await new Promise((r) => agent.listen(3189, r));
  server = app.listen(0);
  await new Promise((r) => server.once("listening", r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(async () => {
  server.close();
  agent.close();
  db.close();
  fs.rmSync(tmp, { recursive: true, force: true });
});
async function call(url, method = "GET", body, cookie) {
  return fetch(base + url, {
    method,
    headers: {
      ...(body ? { "content-type": "application/json" } : {}),
      ...(cookie ? { cookie } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
async function register(username = "tester") {
  const r = await call("/api/auth/register", "POST", {
    username,
    email: `${username}@example.com`,
    password: "Passw0rd1",
    confirm_password: "Passw0rd1",
  });
  return { r, cookie: r.headers.get("set-cookie")?.split(";")[0] };
}
const payload = (priority) => ({
  national_id: "1098765432",
  birth_date: "1995-06-15",
  vehicle_serial: "ABC123456",
  manufacture_year: 2022,
  vehicle_value: 75000,
  purpose_of_use: "personal",
  annual_mileage: "medium",
  coverage_type: "TPL",
  priority,
  requested_add_ons: ["roadside_assistance"],
});
test("register creates customer session, me and logout work", async () => {
  const { r, cookie } = await register();
  assert.equal(r.status, 201);
  assert.equal(
    (await call("/api/auth/me", "GET", undefined, cookie)).status,
    200,
  );
  assert.equal(
    (await call("/api/auth/logout", "POST", {}, cookie)).status,
    200,
  );
  assert.equal(
    (await call("/api/auth/me", "GET", undefined, cookie)).status,
    401,
  );
});
test("registration validates username, password, and confirmation", async () => {
  assert.equal(
    (
      await call("/api/auth/register", "POST", {
        username: "x",
        email: "bad",
        password: "password",
        confirm_password: "not-the-same",
      })
    ).status,
    422,
  );
});
test("registration returns field errors, aliases confirmation, and reports duplicate fields", async () => {
  const invalid = await call("/api/auth/register", "POST", {
    username: "x",
    email: "bad",
    password: "weak",
    confirmPassword: "different",
  });
  assert.equal(invalid.status, 422);
  assert.deepEqual(
    (await invalid.json()).errors.map((x) => x.field),
    ["username", "email", "password", "confirm_password"],
  );
  const valid = await call("/api/auth/register", "POST", {
    username: "dupuser",
    email: "dup@example.com",
    password: "Passw0rd1",
    confirmPassword: "Passw0rd1",
  });
  assert.equal(valid.status, 201);
  const duplicateName = await call("/api/auth/register", "POST", {
    username: "dupuser",
    email: "else@example.com",
    password: "Passw0rd1",
    confirm_password: "Passw0rd1",
  });
  assert.equal(duplicateName.status, 409);
  assert.equal((await duplicateName.json()).errors[0].field, "username");
  const duplicateEmail = await call("/api/auth/register", "POST", {
    username: "another",
    email: "dup@example.com",
    password: "Passw0rd1",
    confirm_password: "Passw0rd1",
  });
  assert.equal(duplicateEmail.status, 409);
  assert.equal((await duplicateEmail.json()).errors[0].field, "email");
});
test("customer login accepts email and is rate limited", async () => {
  await register("rateuser");
  for (let i = 0; i < 5; i++)
    assert.equal(
      (
        await call("/api/auth/login", "POST", {
          identifier: "rateuser@example.com",
          password: "wrong",
        })
      ).status,
      401,
    );
  assert.equal(
    (
      await call("/api/auth/login", "POST", {
        identifier: "rateuser@example.com",
        password: "wrong",
      })
    ).status,
    429,
  );
});
test("protected recommend and admin APIs reject unauthenticated requests", async () => {
  assert.equal((await call("/api/recommend", "POST", {})).status, 401);
  assert.equal((await call("/api/admin/overview")).status, 401);
});
test("malformed JSON returns JSON 400", async () => {
  const r = await fetch(base + "/api/auth/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: "{",
  });
  assert.equal(r.status, 400);
  assert.match(r.headers.get("content-type"), /application\/json/);
});
test("customer and admin authentication components stay separate", async () => {
  const { cookie } = await register("normal");
  assert.equal(
    (await call("/api/admin/overview", "GET", undefined, cookie)).status,
    401,
  );
  assert.equal(
    (
      await call("/api/admin/login", "POST", {
        identifier: "normal",
        password: "Passw0rd1",
      })
    ).status,
    401,
  );
});
test("expired and invalid sessions are rejected", async () => {
  const { cookie } = await register("expire");
  const token = cookie.split("=")[1];
  db.prepare("UPDATE Sessions SET ExpiresAt=0 WHERE TokenHash=?").run(
    require("crypto").createHash("sha256").update(token).digest("hex"),
  );
  assert.equal(
    (await call("/api/auth/me", "GET", undefined, cookie)).status,
    401,
  );
  assert.equal(
    (await call("/api/auth/me", "GET", undefined, "thiqa_sid=not-a-token"))
      .status,
    401,
  );
});
test("recommendation success persists multiple relational records; failure is logged", async () => {
  const { cookie } = await register("persist");
  let r = await call("/api/recommend", "POST", payload("Budget"), cookie);
  assert.equal(r.status, 200);
  let data = await r.json();
  assert.ok(data.request_id);
  assert.equal(
    db
      .prepare("select count(*) n from Retrieved_Quotes where RequestId=?")
      .get(data.request_id).n,
    1,
  );
  assert.equal(
    db
      .prepare("select Status from Quote_Requests where RequestId=?")
      .get(data.request_id).Status,
    "success",
  );
  r = await call("/api/recommend", "POST", payload("Service"), cookie);
  assert.equal(r.status, 422);
  assert.equal(
    db
      .prepare(
        "select Status from Quote_Requests order by RequestId desc limit 1",
      )
      .get().Status,
    "failed",
  );
  r = await call("/api/recommend", "POST", payload("Digital"), cookie);
  assert.equal(r.status, 503);
  assert.equal(
    db
      .prepare(
        "select Status from Quote_Requests order by RequestId desc limit 1",
      )
      .get().Status,
    "failed",
  );
});
test("history is isolated by customer", async () => {
  const a = await register("owner");
  const b = await register("other");
  await call("/api/recommend", "POST", payload("Budget"), a.cookie);
  assert.equal(
    (await (await call("/api/history", "GET", undefined, a.cookie)).json())
      .items.length,
    1,
  );
  assert.equal(
    (await (await call("/api/history", "GET", undefined, b.cookie)).json())
      .items.length,
    0,
  );
});
test("admin CRUD protects secrets and test-connection proxy", async () => {
  const bcrypt = require("bcryptjs");
  db.prepare(
    "INSERT INTO Users(UserName,Email,PasswordHash,IsAdmin) VALUES(?,?,?,1)",
  ).run("admin", "admin@example.com", await bcrypt.hash("Passw0rd1", 10));
  let login = await call("/api/admin/login", "POST", {
      identifier: "admin",
      password: "Passw0rd1",
    }),
    cookie = login.headers.get("set-cookie").split(";")[0];
  assert.equal(login.status, 200);
  assert.equal(
    (await call("/api/admin/overview", "GET", undefined, cookie)).status,
    200,
  );
  const settings = await (
    await call("/api/admin/api-settings", "GET", undefined, cookie)
  ).json();
  assert.ok(settings.items.every((x) => !("AuthKey" in x)));
  assert.equal(
    (
      await call(
        "/api/admin/api-settings/tawuniya",
        "PUT",
        {
          endpoint: "http://127.0.0.1:8001/tawuniya/quotes",
          auth_key: "very-secret-4321",
          auth_scheme: "x-api-key",
          adapter: "tawuniya",
          timeout: 5,
        },
        cookie,
      )
    ).status,
    200,
  );
  const after = await (
    await call("/api/admin/api-settings", "GET", undefined, cookie)
  ).json();
  assert.equal(
    after.items.find((x) => x.ProviderId === "tawuniya").AuthKeyLast4,
    "4321",
  );
  assert.ok(
    after.items.every((x) => !JSON.stringify(x).includes("very-secret")),
  );
  assert.equal(
    (
      await call(
        "/api/admin/providers",
        "POST",
        {
          provider_id: "testco",
          name: "Test Co",
          reliability: 0.7,
          workshop_network: "متوسط",
          digital_score: 0.8,
        },
        cookie,
      )
    ).status,
    201,
  );
  assert.equal(
    (
      await call(
        "/api/admin/providers/testco",
        "PATCH",
        { active: false },
        cookie,
      )
    ).status,
    200,
  );
  assert.equal(
    (await call("/api/admin/providers/tawuniya/test", "POST", {}, cookie))
      .status,
    200,
  );
});
test("legacy migration preserves all users and is idempotent on an old-shaped database", () => {
  const { DatabaseSync } = require("node:sqlite"),
    legacy = path.join(tmp, "legacy.db");
  let x = new DatabaseSync(legacy);
  x.exec(
    "CREATE TABLE Users(UserId INTEGER PRIMARY KEY,UserName TEXT,Email TEXT,PasswordHash TEXT,IsAdmin " +
      "INTEGER,IsCompanyEmployee INTEGER,ProviderId INTEGER,NationalId TEXT,CreatedAt TEXT); CREATE " +
      "TABLE Insurance_Providers(ProviderId INTEGER PRIMARY KEY,ProviderName TEXT,LogoUrl TEXT,Website " +
      "TEXT); CREATE TABLE API_Settings(SettingId INTEGER PRIMARY KEY,ProviderId INTEGER,Endpoint " +
      "TEXT,AuthKey TEXT,Protocol TEXT,Timeout INTEGER); CREATE TABLE Quote_Requests(RequestId INTEGER " +
      "PRIMARY KEY,ProfileId INTEGER,VehicleId INTEGER,CoverageType TEXT,RequestedAddOns TEXT,Timestamp " +
      "TEXT); CREATE TABLE Company_Offers(OfferId INTEGER PRIMARY KEY,ProviderId INTEGER,OfferName " +
      "TEXT,FOREIGN KEY(ProviderId) REFERENCES Insurance_Providers(ProviderId)); INSERT INTO Users " +
      "VALUES(1,'legacy','legacy@example.com','$2a$10$preserved',0,0,4,'1098765432','2020-01-01'); " +
      "INSERT INTO Insurance_Providers VALUES(4,'old','', ''); INSERT INTO Company_Offers " +
      "VALUES(1,4,'legacy offer');",
  );
  x.close();
  const previous = process.env.THIQA_DB_PATH;
  process.env.THIQA_DB_PATH = legacy;
  let migrated = require("../db/connection").openDb();
  assert.equal(migrated.prepare("SELECT count(*) n FROM Users").get().n, 1);
  assert.equal(
    migrated.prepare("SELECT PasswordHash FROM Users").get().PasswordHash,
    "$2a$10$preserved",
  );
  assert.deepEqual(
    migrated
      .prepare("PRAGMA table_info(Users)")
      .all()
      .map((r) => r.name),
    [
      "UserId",
      "UserName",
      "Email",
      "PasswordHash",
      "IsAdmin",
      "CreatedAt",
      "IsActive",
      "LastLoginAt",
    ],
  );
  assert.equal(
    migrated.prepare("SELECT count(*) n FROM Insurance_Providers").get().n,
    5,
  );
  assert.equal(
    migrated.prepare("SELECT count(*) n FROM Company_Offers").get().n,
    1,
  );
  migrated.close();
  migrated = require("../db/connection").openDb();
  assert.equal(migrated.prepare("SELECT count(*) n FROM Users").get().n, 1);
  migrated.close();
  process.env.THIQA_DB_PATH = previous;
});
