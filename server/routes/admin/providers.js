const express = require("express");
const { writeAudit } = require("../../services/audit");
const { requestAgents } = require("../../services/agentsClient");
function val(b, snake, pascal, legacy) {
  return b[snake] ?? b[pascal] ?? b[legacy];
}
module.exports = ({ db, agentsUrl }) => {
  const r = express.Router();
  r.get("/", (req, res) => {
    const items = db
      .prepare(
        "SELECT p.*, (SELECT count(*) FROM Retrieved_Quotes q WHERE q.ProviderId=p.ProviderId) " +
          "QuotesCount FROM Insurance_Providers p ORDER BY ProviderName",
      )
      .all();
    res.json({ items });
  });
  r.post("/", (req, res) => {
    const b = req.body || {},
      id = val(b, "provider_id", "ProviderId", "ProviderId"),
      name = val(b, "provider_name", "ProviderName", "name");
    if (
      !/^[a-z0-9_-]{2,40}$/.test(id || "") ||
      typeof name !== "string" ||
      !name.trim()
    )
      return res.status(400).json({ error: "بيانات مزود غير صالحة" });
    db.prepare(
      "INSERT INTO " +
        "Insurance_Providers(ProviderId,ProviderName,Website,LogoUrl,Reliability," +
        "WorkshopNetwork,DigitalScore,IsActive) " +
        "VALUES(?,?,?,?,?,?,?,?)",
    ).run(
      id,
      name.trim(),
      val(b, "website", "Website") || null,
      val(b, "logo_url", "LogoUrl") || null,
      val(b, "reliability", "Reliability") ?? 0.5,
      val(b, "workshop_network", "WorkshopNetwork") || "متوسط",
      val(b, "digital_score", "DigitalScore") ?? 0.5,
      b.active === false || b.is_active === false ? 0 : 1,
    );
    writeAudit(db, req.user, "provider.create", "provider", id, b);
    res.status(201).json({ ok: true });
  });
  r.patch("/:id", (req, res) => {
    const b = req.body || {},
      pick = (s, p, l) => val(b, s, p, l) ?? null,
      active = b.is_active ?? b.active ?? b.IsActive;
    const result = db
      .prepare(
        "UPDATE Insurance_Providers SET " +
          "ProviderName=coalesce(?,ProviderName),Website=coalesce(?,Website)," +
          "LogoUrl=coalesce(?,LogoUrl),Reliability=coalesce(?,Reliability)," +
          "WorkshopNetwork=coalesce(?,WorkshopNetwork),DigitalScore=coalesce(?,DigitalScore)," +
          "IsActive=coalesce(?,IsActive) WHERE ProviderId=?",
      )
      .run(
        pick("provider_name", "ProviderName", "name"),
        pick("website", "Website"),
        pick("logo_url", "LogoUrl"),
        pick("reliability", "Reliability"),
        pick("workshop_network", "WorkshopNetwork"),
        pick("digital_score", "DigitalScore"),
        active === undefined ? null : Number(Boolean(active)),
        req.params.id,
      );
    if (!result.changes) return res.status(404).json({ error: "غير موجود" });
    writeAudit(db, req.user, "provider.update", "provider", req.params.id, b);
    res.json({ ok: true });
  });
  r.delete("/:id", (req, res) => {
    const refs = db
      .prepare("SELECT count(*) n FROM Retrieved_Quotes WHERE ProviderId=?")
      .get(req.params.id).n;
    if (refs)
      return res.status(409).json({ error: "لا يمكن حذف مزود مرتبط بعروض" });
    const changed = db
      .prepare("DELETE FROM Insurance_Providers WHERE ProviderId=?")
      .run(req.params.id).changes;
    if (!changed) return res.status(404).json({ error: "غير موجود" });
    writeAudit(db, req.user, "provider.delete", "provider", req.params.id);
    res.json({ ok: true });
  });
  r.post("/:id/test", async (req, res) => {
    try {
      const { response, data } = await requestAgents(
        agentsUrl,
        "/providers/test",
        { provider_id: req.params.id },
      );
      res.status(response.status).json(data);
    } catch {
      res.status(502).json({ error: "تعذر اختبار الاتصال" });
    }
  });
  return r;
};
