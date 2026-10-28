const express = require("express");
const bcrypt = require("bcryptjs");
const { authenticate, issue, hash, ADMIN_COOKIE } = require("../../auth");
const { publicUser } = require("./users");
const overview = require("./overview");
const users = require("./users");
const providers = require("./providers");
const settings = require("./apiSettings");
const logs = require("./logs");
const audit = require("./audit");
module.exports = ({ db, agentsUrl }) => {
  const r = express.Router();
  r.post("/login", async (req, res) => {
    const id = String(
      req.body?.identifier || req.body?.username || req.body?.email || "",
    ).toLowerCase();
    const user = db
      .prepare("SELECT * FROM Users WHERE lower(UserName)=? OR lower(Email)=?")
      .get(id, id);
    if (
      !user?.IsAdmin ||
      !user.IsActive ||
      !(await bcrypt.compare(
        String(req.body?.password || ""),
        user.PasswordHash,
      ))
    )
      return res.status(401).json({
        error: "اسم المستخدم أو كلمة المرور غير صحيحة",
      });
    issue(db, res, user, "admin");
    res.json({ user: publicUser(user) });
  });
  r.post("/logout", (req, res) => {
    const token = req.cookies[ADMIN_COOKIE];
    if (token)
      db.prepare("DELETE FROM Sessions WHERE TokenHash=? AND Kind='admin'").run(
        hash(token),
      );
    res.clearCookie(ADMIN_COOKIE, { path: "/" });
    res.json({ ok: true });
  });
  r.get("/me", authenticate(db, "admin"), (req, res) =>
    res.json({ user: publicUser(req.user) }),
  );
  const guard = authenticate(db, "admin");
  r.use("/overview", guard, overview(db));
  r.use("/users", guard, users(db));
  r.use("/providers", guard, providers({ db, agentsUrl }));
  r.use("/api-settings", guard, settings(db));
  r.use("/logs", guard, logs(db));
  r.use("/audit", guard, audit(db));
  return r;
};
