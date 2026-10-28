const crypto = require("node:crypto");
const bcrypt = require("bcryptjs");
const COOKIE = "thiqa_sid",
  ADMIN_COOKIE = "thiqa_admin_sid";
const hash = (s) => crypto.createHash("sha256").update(s).digest("hex");
function issue(db, res, user, kind = "customer") {
  const token = crypto.randomBytes(32).toString("hex"),
    now = Math.floor(Date.now() / 1000),
    max = now + 7 * 86400;
  db.prepare(
    "INSERT INTO Sessions(UserId,TokenHash,CreatedAt,LastSeenAt,ExpiresAt,MaxExpiresAt,Kind) VALUES(?,?,?,?,?,?,?)",
  ).run(user.UserId, hash(token), now, now, now + 28800, max, kind);
  res.cookie(kind === "admin" ? ADMIN_COOKIE : COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.COOKIE_SECURE === "1",
    path: "/",
    maxAge: 7 * 86400000,
  });
}
function authenticate(db, kind = "customer") {
  return (req, res, next) => {
    const token = req.cookies[kind === "admin" ? ADMIN_COOKIE : COOKIE];
    if (!token) return res.status(401).json({ error: "يلزم تسجيل الدخول" });
    const now = Math.floor(Date.now() / 1000);
    const row = db
      .prepare(
        "SELECT " +
          "s.SessionId,s.UserId,s.CreatedAt,s.LastSeenAt,s.ExpiresAt,s.MaxExpiresAt, " +
          "u.UserName,u.Email,u.IsAdmin,u.IsActive " +
          "FROM Sessions s JOIN Users u ON u.UserId=s.UserId WHERE s.TokenHash=? AND s.Kind=?",
      )
      .get(hash(token), kind);
    if (
      !row ||
      row.ExpiresAt <= now ||
      row.MaxExpiresAt <= now ||
      !row.IsActive ||
      (kind === "admin" && !row.IsAdmin) ||
      (kind === "customer" && row.IsAdmin)
    ) {
      db.prepare("DELETE FROM Sessions WHERE TokenHash=?").run(hash(token));
      return res.status(401).json({ error: "جلسة غير صالحة" });
    }
    db.prepare(
      "UPDATE Sessions SET LastSeenAt=?,ExpiresAt=? WHERE SessionId=?",
    ).run(now, Math.min(now + 28800, row.MaxExpiresAt), row.SessionId);
    req.user = row;
    next();
  };
}
function makeAuthRouter(db, rate) {
  const express = require("express"),
    r = express.Router();
  r.post("/register", async (req, res) => {
    const { username, email, password } = req.body || {};
    const confirmPassword =
      req.body?.confirm_password ?? req.body?.confirmPassword;
    const errors = [];
    if (typeof username !== "string" || !/^[A-Za-z0-9_.]{3,30}$/.test(username))
      errors.push({
        field: "username",
        message: "اسم المستخدم 3–30 حرفاً إنجليزياً أو أرقاماً أو _ .",
      });
    if (typeof email !== "string" || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      errors.push({ field: "email", message: "البريد الإلكتروني غير صحيح" });
    if (
      typeof password !== "string" ||
      password.length < 8 ||
      !/[A-Za-z]/.test(password) ||
      !/[0-9]/.test(password)
    )
      errors.push({
        field: "password",
        message: "كلمة المرور 8 أحرف على الأقل وتحتوي حرفاً ورقماً",
      });
    if (password !== confirmPassword)
      errors.push({
        field: "confirm_password",
        message: "كلمتا المرور غير متطابقتين",
      });
    if (errors.length)
      return res
        .status(422)
        .json({ error: "تحقق من البيانات المدخلة", errors });
    try {
      const info = db
        .prepare("INSERT INTO Users(UserName,Email,PasswordHash) VALUES(?,?,?)")
        .run(username, email, await bcrypt.hash(password, 10));
      const user = db
        .prepare(
          "SELECT UserId,UserName,Email,IsAdmin FROM Users WHERE UserId=?",
        )
        .get(info.lastInsertRowid);
      issue(db, res, user);
      return res.status(201).json({ user });
    } catch (e) {
      if (String(e).includes("UNIQUE")) {
        const field = String(e).includes("Users.Email") ? "email" : "username";
        const message =
          field === "email"
            ? "البريد الإلكتروني مسجل مسبقاً"
            : "اسم المستخدم مستخدم مسبقاً";
        return res
          .status(409)
          .json({ error: message, errors: [{ field, message }] });
      }
      throw e;
    }
  });
  r.post("/login", async (req, res) => {
    const ident = String(
        req.body?.identifier || req.body?.username || req.body?.email || "",
      ).toLowerCase(),
      ip = req.ip;
    const key = ip + "|" + ident;
    if (rate.blocked(key))
      return res.status(429).json({ error: "محاولات كثيرة، حاول لاحقاً" });
    const user = db
      .prepare("SELECT * FROM Users WHERE lower(UserName)=? OR lower(Email)=?")
      .get(ident, ident);
    const okay =
      user &&
      user.IsActive &&
      !user.IsAdmin &&
      (await bcrypt.compare(
        String(req.body?.password || ""),
        user.PasswordHash,
      ));
    if (!okay) {
      rate.fail(key);
      return res
        .status(401)
        .json({ error: "اسم المستخدم أو كلمة المرور غير صحيحة" });
    }
    rate.clear(key);
    db.prepare(
      "UPDATE Users SET LastLoginAt=datetime('now') WHERE UserId=?",
    ).run(user.UserId);
    issue(db, res, user);
    res.json({
      user: {
        UserId: user.UserId,
        UserName: user.UserName,
        Email: user.Email,
        IsAdmin: 0,
      },
    });
  });
  r.post("/logout", (req, res) => {
    const t = req.cookies[COOKIE];
    if (t)
      db.prepare("DELETE FROM Sessions WHERE TokenHash=? AND Kind=?").run(
        hash(t),
        "customer",
      );
    res.clearCookie(COOKIE, { path: "/" });
    res.json({ ok: true });
  });
  r.get("/me", authenticate(db), (req, res) =>
    res.json({
      user: {
        UserId: req.user.UserId,
        UserName: req.user.UserName,
        Email: req.user.Email,
      },
    }),
  );
  return r;
}
module.exports = {
  COOKIE,
  ADMIN_COOKIE,
  issue,
  authenticate,
  makeAuthRouter,
  hash,
};
