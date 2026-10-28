const express = require("express");
const { pageParams } = require("../../services/validation");
const { details } = require("../history");
module.exports = (db) => {
  const r = express.Router();
  r.get("/", (req, res) => {
    const { page, pageSize } = pageParams(req.query, 20),
      clauses = [],
      args = [];
    if (["success", "failed"].includes(req.query.status)) {
      clauses.push("q.Status=?");
      args.push(req.query.status);
    }
    if (req.query.from) {
      clauses.push("date(q.Timestamp)>=date(?)");
      args.push(req.query.from);
    }
    if (req.query.to) {
      clauses.push("date(q.Timestamp)<=date(?)");
      args.push(req.query.to);
    }
    const q = String(req.query.q || req.query.search || "").slice(0, 100);
    if (q) {
      clauses.push(
        "(u.UserName LIKE ? OR EXISTS(SELECT 1 FROM Retrieved_Quotes z JOIN Insurance_Providers zp " +
          "USING(ProviderId) WHERE z.RequestId=q.RequestId AND zp.ProviderName LIKE ?))",
      );
      args.push(`%${q}%`, `%${q}%`);
    }
    const where = clauses.length ? `WHERE ${clauses.join(" AND ")}` : "";
    const base =
      " FROM Quote_Requests q JOIN Customer_Profiles c USING(ProfileId) JOIN Users u USING(UserId) ";
    const total = db.prepare(`SELECT count(*) n${base}${where}`).get(...args).n;
    const items = db
      .prepare(
        `SELECT q.RequestId,q.Timestamp,u.UserName,q.CoverageType,q.Priority,` +
          `q.Status,q.ErrorMessage,(SELECT p.ProviderName FROM Retrieved_Quotes x ` +
          `JOIN Insurance_Providers p USING(ProviderId) WHERE x.RequestId=q.RequestId ` +
          `ORDER BY x.Rank LIMIT 1) ProviderName,(SELECT x.PlanName ` +
          `FROM Retrieved_Quotes x WHERE x.RequestId=q.RequestId ORDER BY x.Rank ` +
          `LIMIT 1) PlanName,(SELECT x.Premium FROM Retrieved_Quotes x ` +
          `WHERE x.RequestId=q.RequestId ORDER BY x.Rank LIMIT 1) Premium,` +
          `r.SuitabilityScore,(SELECT count(*) FROM Retrieved_Quotes x ` +
          `WHERE x.RequestId=q.RequestId) QuotesCount${base} ` +
          `LEFT JOIN Recommendations r USING(RequestId) ${where} ` +
          `ORDER BY q.RequestId DESC LIMIT ? OFFSET ?`,
      )
      .all(...args, pageSize, (page - 1) * pageSize);
    res.json({ items, total, page, pageSize });
  });
  r.get("/:id", (req, res) => {
    const user = db
      .prepare(
        "SELECT u.UserId,u.UserName,u.Email FROM Quote_Requests q JOIN Customer_Profiles c " +
          "USING(ProfileId) JOIN Users u USING(UserId) WHERE q.RequestId=?",
      )
      .get(req.params.id);
    if (!user) return res.status(404).json({ error: "غير موجود" });
    res.json({ ...details(db, req.params.id), user });
  });
  return r;
};
