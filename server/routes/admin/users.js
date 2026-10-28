const express = require("express");
const { pageParams } = require("../../services/validation");
const { writeAudit } = require("../../services/audit");
function publicUser(user) {
  return { UserId: user.UserId, UserName: user.UserName };
}
module.exports = (db) => {
  const r = express.Router();
  r.get("/", (req, res) => {
    const q = String(req.query.q ?? req.query.search ?? "").slice(0, 100),
      like = `%${q}%`,
      { page, pageSize } = pageParams(req.query, 20);
    const where = "(u.UserName LIKE ? OR u.Email LIKE ?)";
    const total = db
      .prepare(`SELECT count(*) n FROM Users u WHERE ${where}`)
      .get(like, like).n;
    const items = db
      .prepare(
        `SELECT u.UserId,u.UserName,u.Email,u.IsAdmin,u.IsActive,u.CreatedAt,` +
          `u.LastLoginAt,(SELECT count(*) FROM Customer_Profiles c ` +
          `JOIN Quote_Requests q USING(ProfileId) WHERE c.UserId=u.UserId) ` +
          `RequestsCount FROM Users u WHERE ${where} ORDER BY u.UserId DESC ` +
          `LIMIT ? OFFSET ?`,
      )
      .all(like, like, pageSize, (page - 1) * pageSize);
    res.json({ items, total, page, pageSize });
  });
  r.patch("/:id", (req, res) => {
    const active =
      req.body?.IsActive ??
      req.body?.active ??
      (typeof req.body?.is_active === "boolean"
        ? Number(req.body.is_active)
        : undefined);
    if (![0, 1, true, false].includes(active))
      return res.status(400).json({ error: "قيمة الحالة غير صالحة" });
    const target = db
      .prepare("SELECT * FROM Users WHERE UserId=?")
      .get(req.params.id);
    if (!target) return res.status(404).json({ error: "غير موجود" });
    const value = Number(Boolean(active));
    if (target.IsAdmin && !value) {
      const count = db
        .prepare("SELECT count(*) n FROM Users WHERE IsAdmin=1 AND IsActive=1")
        .get().n;
      if (Number(target.UserId) === Number(req.user.UserId) || count <= 1)
        return res
          .status(400)
          .json({ error: "لا يمكن تعطيل الحساب الإداري الحالي أو آخر مدير" });
    }
    db.prepare("UPDATE Users SET IsActive=? WHERE UserId=?").run(
      value,
      req.params.id,
    );
    writeAudit(db, req.user, "user.active", "user", req.params.id, {
      IsActive: value,
    });
    res.json({ ok: true });
  });
  return r;
};
module.exports.publicUser = publicUser;
