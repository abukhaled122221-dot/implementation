const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const root =
  "C:/Users/Hessah/AppData/Local/hermes/profiles/mimo-v2-6-pro/cache/scratch/thiqa";
function makeHarness({ delayMs = 0, timeoutMs } = {}) {
  const dir = fs.mkdtempSync(path.join(root, "helper-"));
  process.env.THIQA_DB_PATH = path.join(dir, "db.sqlite");
  const agent = http.createServer((req, res) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      res.setHeader("content-type", "application/json");
      if (req.url === "/recommend" && delayMs)
        return setTimeout(
          () => res.end(JSON.stringify({ all_offers_ranked: [] })),
          delayMs,
        );
      if (req.url === "/recommend")
        return res.end(
          JSON.stringify({
            all_offers_ranked: [
              {
                provider_id: "tawuniya",
                provider_name: "Provider",
                plan_name: "Plan",
                premium: 100,
                coverage_type: "TPL",
                deductible: 0,
                add_ons: ["roadside_assistance"],
                suitability_score: 0.8,
              },
            ],
            explanation: {
              main_reasons: "reason",
              strengths: [],
              criteria_explanations: [],
              comparison: "text",
            },
          }),
        );
      res.end(JSON.stringify({ provider_id: "tawuniya", ok: true }));
    });
  });
  return new Promise((resolve) =>
    agent.listen(0, () => {
      process.env.AGENTS_SERVICE_URL = `http://127.0.0.1:${agent.address().port}`;
      const { openDb } = require("../db/connection");
      const { createApp } = require("../app");
      const db = openDb(),
        server = createApp({
          db,
          agentsUrl: process.env.AGENTS_SERVICE_URL,
          agentsTimeoutMs: timeoutMs,
        }).listen(0, () => {
          const base = `http://127.0.0.1:${server.address().port}`;
          resolve({
            db,
            async call(url, method = "GET", body, cookie) {
              return fetch(base + url, {
                method,
                headers: {
                  ...(body === undefined
                    ? {}
                    : { "content-type": "application/json" }),
                  ...(cookie ? { cookie } : {}),
                },
                body: body === undefined ? undefined : JSON.stringify(body),
              });
            },
            async close() {
              await new Promise((r) => server.close(r));
              await new Promise((r) => agent.close(r));
              db.close();
              fs.rmSync(dir, { recursive: true, force: true });
            },
          });
        });
    }),
  );
}
async function register(h, username = "sample") {
  const r = await h.call("/api/auth/register", "POST", {
    username,
    email: `${username}@example.test`,
    password: "Passw0rd1",
    confirm_password: "Passw0rd1",
  });
  return { response: r, cookie: r.headers.get("set-cookie")?.split(";")[0] };
}
const recommendation = {
  national_id: "1098765432",
  birth_date: "1995-06-15",
  vehicle_serial: "ABC123456",
  manufacture_year: 2022,
  vehicle_value: 75000,
  purpose_of_use: "personal",
  annual_mileage: "medium",
  coverage_type: "TPL",
  priority: "Budget",
  requested_add_ons: ["roadside_assistance"],
};
module.exports = { makeHarness, register, recommendation };
