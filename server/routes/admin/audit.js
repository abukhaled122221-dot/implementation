const express = require("express");
module.exports = (db) => {
  const r = express.Router();
  r.get("/", (req, res) => {
    const { page, pageSize } = require("../../services/validation").pageParams(
      req.query,
      20,
    );
    const items = db
      .prepare(
        "SELECT a.AuditId,a.CreatedAt,u.UserName AdminUserName,a.Action,a.EntityType " +
          "TargetType,a.EntityId TargetId,a.Details FROM Audit_Log a LEFT JOIN Users u ON " +
          "u.UserId=a.AdminUserId ORDER BY a.AuditId DESC LIMIT ? OFFSET ?",
      )
      .all(pageSize, (page - 1) * pageSize)
      .map((x) => ({ ...x, Details: parse(x.Details) }));
    const total = db.prepare("SELECT count(*) n FROM Audit_Log").get().n;
    res.json({ items, total, page, pageSize });
  });
  return r;
};
function parse(x) {
  try {
    return x == null ? null : JSON.parse(x);
  } catch {
    return x;
  }
}
