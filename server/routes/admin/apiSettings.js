const express = require("express");
const { writeAudit } = require("../../services/audit");
module.exports = (db) => {
  const r = express.Router();
  r.get("/", (req, res) => {
    const items = db
      .prepare(
        "SELECT a.ProviderId,p.ProviderName,a.Endpoint,a.AuthScheme,a.Adapter,a.Protocol,a.Timeout,CASE " +
          "WHEN a.AuthKey IS NULL OR a.AuthKey='' THEN 0 ELSE 1 END HasAuthKey,CASE WHEN a.AuthKey IS NULL " +
          "OR a.AuthKey='' THEN NULL ELSE substr(a.AuthKey,-4) END AuthKeyLast4 FROM API_Settings a JOIN " +
          "Insurance_Providers p USING(ProviderId) ORDER BY p.ProviderName",
      )
      .all();
    res.json({ items });
  });
  r.put("/:providerId", (req, res) => {
    const b = req.body || {};
    let url;
    try {
      url = new URL(b.endpoint);
      if (!["http:", "https:"].includes(url.protocol)) throw Error();
    } catch {
      return res.status(400).json({ error: "رابط endpoint غير صالح" });
    }
    if (
      !["x-api-key", "bearer"].includes(b.auth_scheme) ||
      !["tawuniya", "rajhi", "medgulf", "acig"].includes(b.adapter) ||
      !Number.isInteger(b.timeout) ||
      b.timeout < 1 ||
      b.timeout > 30
    )
      return res.status(400).json({ error: "إعدادات API غير صالحة" });
    if (
      !db
        .prepare("SELECT 1 FROM Insurance_Providers WHERE ProviderId=?")
        .get(req.params.providerId)
    )
      return res.status(404).json({ error: "غير موجود" });
    const protocol = b.protocol || "REST/JSON";
    db.prepare(
      "INSERT INTO API_Settings(ProviderId,Endpoint,AuthKey,AuthScheme,Adapter,Protocol,Timeout) " +
        "VALUES(?,?,?,?,?,?,?) ON CONFLICT(ProviderId) DO UPDATE SET " +
        "Endpoint=excluded.Endpoint,AuthKey=CASE WHEN excluded.AuthKey IS NULL OR excluded.AuthKey='' " +
        "THEN API_Settings.AuthKey ELSE excluded.AuthKey " +
        "END,AuthScheme=excluded.AuthScheme,Adapter=excluded.Adapter," +
        "Protocol=excluded.Protocol,Timeout=excluded.Timeout",
    ).run(
      req.params.providerId,
      b.endpoint,
      b.auth_key || null,
      b.auth_scheme,
      b.adapter,
      protocol,
      b.timeout,
    );
    const { auth_key, ...safe } = b;
    writeAudit(
      db,
      req.user,
      "api-settings.update",
      "provider",
      req.params.providerId,
      { ...safe, protocol },
    );
    res.json({ ok: true });
  });
  return r;
};
