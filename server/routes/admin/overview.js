const express = require("express");
module.exports = (db) => {
  const r = express.Router();
  r.get("/", (req, res) => {
    const users = db
      .prepare(
        "SELECT count(*) total,coalesce(sum(IsActive),0) active FROM Users WHERE IsAdmin=0",
      )
      .get();
    const reqs = db
      .prepare(
        "SELECT count(*) total,sum(date(Timestamp)=date('now')) today,sum(Status='success') " +
          "success,sum(Status='failed') failed,coalesce(100.0*sum(Status='success')/nullif(count(*),0),0) " +
          "successRate FROM Quote_Requests",
      )
      .get();
    const providers = db
      .prepare(
        "SELECT count(*) total,coalesce(sum(IsActive),0) active FROM Insurance_Providers",
      )
      .get();
    const recent = db
      .prepare(
        "SELECT " +
          "q.RequestId,q.Timestamp,u.UserName,q.CoverageType,q.Priority,q.Status,q.ErrorMessage,(SELECT " +
          "p.ProviderName FROM Retrieved_Quotes x JOIN Insurance_Providers p USING(ProviderId) WHERE " +
          "x.RequestId=q.RequestId ORDER BY x.Rank LIMIT 1) ProviderName,(SELECT x.PlanName FROM " +
          "Retrieved_Quotes x WHERE x.RequestId=q.RequestId ORDER BY x.Rank LIMIT 1) PlanName,(SELECT " +
          "x.Premium FROM Retrieved_Quotes x WHERE x.RequestId=q.RequestId ORDER BY x.Rank LIMIT 1) " +
          "Premium,r.SuitabilityScore,(SELECT count(*) FROM Retrieved_Quotes x WHERE " +
          "x.RequestId=q.RequestId) QuotesCount FROM Quote_Requests q JOIN Customer_Profiles c " +
          "USING(ProfileId) JOIN Users u USING(UserId) LEFT JOIN Recommendations r USING(RequestId) ORDER " +
          "BY q.RequestId DESC LIMIT 5",
      )
      .all();
    res.json({
      users: { ...users },
      requests: reqs,
      providers,
      recent,
      requests_today: reqs.today,
      requests_total: reqs.total,
      success_rate: reqs.successRate,
    });
  });
  return r;
};
