/**
 * البيانات الأولية لقاعدة بيانات ثقة: شركات التأمين الأربع وإعدادات الاتصال بها (عقد C3).
 *
 * القاعدة: لا نستبدل أبداً ما عدّله الأدمن من لوحة التحكم.
 *  - الشركة غير الموجودة تُضاف كاملة.
 *  - الشركة الموجودة تُكمَّل حقولها الفارغة فقط (NULL) — مثلاً بعد ترحيل جدول قديم
 *    لم تكن فيه أعمدة الموثوقية وشبكة الورش والتجربة الرقمية.
 */

const DEFAULT_PROVIDERS = [
  {
    id: "tawuniya",
    name: "التعاونية للتأمين",
    route: "/tawuniya/quotes",
    authScheme: "x-api-key",
    reliability: 0.95,
    workshopNetwork: "واسع جداً",
    digitalScore: 0.82,
  },
  {
    id: "rajhi",
    name: "الراجحي تكافل",
    route: "/rajhi/offers",
    authScheme: "bearer",
    reliability: 0.9,
    workshopNetwork: "متوسط",
    digitalScore: 0.96,
  },
  {
    id: "medgulf",
    name: "ميدغلف للتأمين",
    route: "/medgulf/plans",
    authScheme: "x-api-key",
    reliability: 0.85,
    workshopNetwork: "متوسط",
    digitalScore: 0.88,
  },
  {
    id: "acig",
    name: "المجموعة المتحدة للتأمين (ACIG)",
    route: "/acig/quote",
    authScheme: "x-api-key",
    reliability: 0.78,
    workshopNetwork: "محدود",
    digitalScore: 0.78,
  },
];

/** يضيف الشركات الافتراضية ويكمل الحقول الفارغة، ثم ينظف الجلسات المنتهية. */
function seed(db) {
  const platformUrl = (
    process.env.INSURER_PLATFORM_URL || "http://127.0.0.1:8001"
  ).replace(/\/$/, "");

  const insertProvider = db.prepare(`
    INSERT OR IGNORE INTO Insurance_Providers
      (ProviderId, ProviderName, Website, IsActive, Reliability, WorkshopNetwork, DigitalScore)
    VALUES (?, ?, ?, 1, ?, ?, ?)`);

  const fillMissingProviderFields = db.prepare(`
    UPDATE Insurance_Providers SET
      Website         = COALESCE(Website, ?),
      Reliability     = COALESCE(Reliability, ?),
      WorkshopNetwork = COALESCE(WorkshopNetwork, ?),
      DigitalScore    = COALESCE(DigitalScore, ?)
    WHERE ProviderId = ?`);

  const insertApiSettings = db.prepare(`
    INSERT OR IGNORE INTO API_Settings (ProviderId, Endpoint, AuthKey, AuthScheme, Adapter, Timeout)
    VALUES (?, ?, ?, ?, ?, 5)`);

  for (const p of DEFAULT_PROVIDERS) {
    const website = `${platformUrl}/${p.id}`;
    insertProvider.run(
      p.id,
      p.name,
      website,
      p.reliability,
      p.workshopNetwork,
      p.digitalScore,
    );
    fillMissingProviderFields.run(
      website,
      p.reliability,
      p.workshopNetwork,
      p.digitalScore,
      p.id,
    );
    insertApiSettings.run(
      p.id,
      `${platformUrl}${p.route}`,
      `${p.id}-test-key`,
      p.authScheme,
      p.id,
    );
  }

  // الجلسات المنتهية لا تُستخدم؛ حذفها يبقي جدول Sessions صغيراً مع الوقت.
  const now = Math.floor(Date.now() / 1000);
  db.prepare(
    "DELETE FROM Sessions WHERE ExpiresAt <= ? OR MaxExpiresAt <= ?",
  ).run(now, now);
}

module.exports = { seed, DEFAULT_PROVIDERS };
