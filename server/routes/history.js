const express = require("express");
const { authenticate } = require("../auth");
const { pageParams } = require("../services/validation");
function details(db, requestId) {
  const raw = db
    .prepare("SELECT * FROM Quote_Requests WHERE RequestId=?")
    .get(requestId);
  if (!raw) return null;
  const request = {
    ...raw,
    RequestPayload: parse(raw.RequestPayload, {}),
    ProviderStatus: parse(raw.ProviderStatus, []),
  };
  const quotes = db
    .prepare(
      "SELECT rq.*,p.ProviderName FROM Retrieved_Quotes rq JOIN Insurance_Providers p USING(ProviderId) " +
        "WHERE RequestId=? ORDER BY Rank",
    )
    .all(requestId)
    .map((q) => ({ ...q, AddOns: parse(q.AddOns, []) }));
  const rec =
    db
      .prepare(
        "SELECT RecId,SelectedQuoteId,SuitabilityScore,CreatedAt FROM Recommendations WHERE RequestId=?",
      )
      .get(requestId) || null;
  const explanationRaw =
    rec &&
    db
      .prepare(
        "SELECT MainReasons,CriteriaBreakdown,ComparisonText FROM Explanations WHERE RecId=?",
      )
      .get(rec.RecId);
  const explanation = explanationRaw
    ? {
        MainReasons: parse(
          explanationRaw.MainReasons,
          explanationRaw.MainReasons,
        ),
        CriteriaBreakdown: parse(explanationRaw.CriteriaBreakdown, {}),
        ComparisonText: parse(
          explanationRaw.ComparisonText,
          explanationRaw.ComparisonText,
        ),
      }
    : null;
  return {
    request,
    quotes,
    recommendation: rec && {
      RecId: rec.RecId,
      SelectedQuoteId: rec.SelectedQuoteId,
      SuitabilityScore: rec.SuitabilityScore,
      CreatedAt: rec.CreatedAt,
    },
    explanation,
  };
}
function parse(value, fallback) {
  try {
    return value == null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}
module.exports = (db) => {
  const r = express.Router();
  r.get("/", authenticate(db), (req, res) => {
    const { page, pageSize } = pageParams(req.query, 10);
    const items = db
      .prepare(
        "SELECT q.RequestId,q.Timestamp,q.CoverageType,q.Priority,q.Status,q.ErrorMessage,(SELECT " +
          "p.ProviderName FROM Retrieved_Quotes x JOIN Insurance_Providers p USING(ProviderId) WHERE " +
          "x.RequestId=q.RequestId ORDER BY x.Rank LIMIT 1) ProviderName,(SELECT x.PlanName FROM " +
          "Retrieved_Quotes x WHERE x.RequestId=q.RequestId ORDER BY x.Rank LIMIT 1) PlanName,(SELECT " +
          "x.Premium FROM Retrieved_Quotes x WHERE x.RequestId=q.RequestId ORDER BY x.Rank LIMIT 1) " +
          "Premium,r.SuitabilityScore FROM Quote_Requests q JOIN Customer_Profiles c USING(ProfileId) LEFT " +
          "JOIN Recommendations r USING(RequestId) WHERE c.UserId=? ORDER BY q.RequestId DESC LIMIT ? " +
          "OFFSET ?",
      )
      .all(req.user.UserId, pageSize, (page - 1) * pageSize);
    const total = db
      .prepare(
        "SELECT count(*) n FROM Quote_Requests q JOIN Customer_Profiles c USING(ProfileId) WHERE c.UserId=?",
      )
      .get(req.user.UserId).n;
    res.json({ items, total, page, pageSize });
  });
  r.get("/:id", authenticate(db), (req, res) => {
    const exists = db
      .prepare(
        "SELECT 1 FROM Quote_Requests q JOIN Customer_Profiles c USING(ProfileId) WHERE q.RequestId=? AND c.UserId=?",
      )
      .get(req.params.id, req.user.UserId);
    if (!exists) return res.status(404).json({ error: "غير موجود" });
    res.json(details(db, req.params.id));
  });
  return r;
};
module.exports.details = details;
