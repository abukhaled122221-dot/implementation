const express = require("express");
const path = require("node:path");
const cookieParser = require("cookie-parser");
const {
  agentsUrl: defaultAgentsUrl,
  agentsTimeoutMs: defaultAgentsTimeoutMs,
  bodyLimit,
} = require("./config");
const authRouter = require("./routes/auth");
const recommendRouter = require("./routes/recommend");
const historyRouter = require("./routes/history");
const adminRouter = require("./routes/admin");
function createApp({
  db,
  agentsUrl = defaultAgentsUrl,
  agentsTimeoutMs = defaultAgentsTimeoutMs,
} = {}) {
  const app = express();
  const failures = new Map();
  const rate = {
    blocked(key) {
      const a = (failures.get(key) || []).filter(
        (t) => Date.now() - t < 900000,
      );
      failures.set(key, a);
      return a.length >= 5;
    },
    fail(key) {
      failures.set(key, [...(failures.get(key) || []), Date.now()]);
    },
    clear(key) {
      failures.delete(key);
    },
  };
  app.disable("x-powered-by");
  app.use((req, res, next) => {
    res.set({
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
      "Content-Security-Policy": "frame-ancestors 'none'",
      "Referrer-Policy": "strict-origin-when-cross-origin",
    });
    next();
  });
  app.use(express.json({ limit: bodyLimit }));
  app.use(cookieParser());
  app.use(express.static(path.join(__dirname, "public")));
  app.get("/api/health", (req, res) =>
    res.json({ status: "ok", service: "thiqa-node-server" }),
  );
  app.get("/api/config", (req, res) =>
    res.json({
      insurerPlatformUrl:
        process.env.INSURER_PLATFORM_URL || "http://127.0.0.1:8001",
    }),
  );
  app.use("/api/auth", authRouter(db, rate));
  app.use(
    "/api/recommend",
    recommendRouter({ db, agentsUrl, agentsTimeoutMs }),
  );
  app.use("/api/history", historyRouter(db));
  app.use("/api/admin", adminRouter({ db, agentsUrl }));
  app.use("/api", (req, res) =>
    res.status(404).json({ error: "المسار غير موجود" }),
  );
  app.use((error, req, res, next) => {
    if (error instanceof SyntaxError && error.status === 400)
      return res.status(400).json({ error: "JSON غير صالح" });
    console.error(error);
    return res.status(500).json({ error: "حدث خطأ داخلي" });
  });
  return app;
}
module.exports = { createApp };
