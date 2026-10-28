/**
 * أدوات تحقق مشتركة لمسارات الخادم.
 *
 * التحقق من طلب التوصية هنا هو خط الدفاع الأول قبل الحفظ في قاعدة البيانات
 * (Customer_Profiles / Vehicles). Agent 1 في خدمة Python يعيد التحقق بنفس القواعد،
 * لذلك الرسائل هنا مطابقة لرسائله حتى يرى العميل نفس النص أياً كانت الطبقة.
 */

const ADD_ONS = [
  "agency_repair",
  "roadside_assistance",
  "replacement_car",
  "windshield_cover",
  "gulf_coverage",
];

/** تاريخ حقيقي بصيغة YYYY-MM-DD (يرفض 2026-02-31 مثلاً). */
function validDate(value) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value))
    return false;
  const date = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
  );
}

/** العمر بالسنوات الكاملة حتى اليوم. */
function ageFrom(isoDate, today = new Date()) {
  const birth = new Date(`${isoDate}T00:00:00Z`);
  let age = today.getUTCFullYear() - birth.getUTCFullYear();
  const beforeBirthday =
    today.getUTCMonth() < birth.getUTCMonth() ||
    (today.getUTCMonth() === birth.getUTCMonth() &&
      today.getUTCDate() < birth.getUTCDate());
  if (beforeBirthday) age -= 1;
  return age;
}

/** page / pageSize من الاستعلام (يقبل limit القديم أيضاً)، pageSize بين 1 و 100. */
function pageParams(query, fallback = 20) {
  const requested = Number(query.pageSize ?? query.limit);
  return {
    page: Math.max(1, Number(query.page) || 1),
    pageSize: Number.isFinite(requested)
      ? Math.min(100, Math.max(1, requested))
      : fallback,
  };
}

/** حقل اختياري: إما غير مرسل أو من القيم المسموحة. */
const optionalOneOf = (value, allowed) =>
  value === undefined || allowed.includes(value);

/**
 * يرجع قائمة أخطاء [{field, message}] لطلب التوصية (عقد C1)، أو قائمة فارغة إن كان صالحاً.
 */
function recommendationErrors(body) {
  const nextYear = new Date().getFullYear() + 1;
  const birthOk = validDate(body.birth_date);
  const age = birthOk ? ageFrom(body.birth_date) : null;
  const addOns = body.requested_add_ons ?? [];

  const rules = [
    {
      field: "national_id",
      ok: /^[12]\d{9}$/.test(String(body.national_id ?? "")),
      message: "رقم الهوية/الإقامة يجب أن يكون 10 أرقام ويبدأ بـ 1 أو 2",
    },
    {
      field: "birth_date",
      ok: birthOk && age >= 18 && age <= 90,
      message: birthOk
        ? "عمر السائق يجب أن يكون بين 18 و 90 سنة"
        : "تاريخ الميلاد غير صحيح",
    },
    {
      field: "vehicle_serial",
      ok: /^[A-Za-z0-9]{6,17}$/.test(String(body.vehicle_serial ?? "")),
      message:
        "الرقم التسلسلي للمركبة غير صحيح (6–17 حرفاً إنجليزياً أو رقماً)",
    },
    {
      field: "manufacture_year",
      ok:
        Number.isInteger(body.manufacture_year) &&
        body.manufacture_year >= 1990 &&
        body.manufacture_year <= nextYear,
      message: `سنة الصنع يجب أن تكون بين 1990 و ${nextYear}`,
    },
    {
      field: "vehicle_value",
      ok:
        Number.isFinite(body.vehicle_value) &&
        body.vehicle_value >= 5000 &&
        body.vehicle_value <= 2000000,
      message: "قيمة المركبة يجب أن تكون بين 5,000 و 2,000,000 ريال",
    },
    {
      field: "purpose_of_use",
      ok: ["personal", "commercial", "family"].includes(body.purpose_of_use),
      message: "غرض الاستخدام غير معروف",
    },
    {
      field: "annual_mileage",
      ok: ["low", "medium", "high"].includes(body.annual_mileage),
      message: "فئة الممشى السنوي غير معروفة",
    },
    {
      field: "coverage_type",
      ok: ["TPL", "Comprehensive"].includes(body.coverage_type),
      message: "نوع التغطية يجب أن يكون TPL أو Comprehensive",
    },
    {
      field: "priority",
      ok: ["Budget", "Service", "Digital", "Balanced"].includes(body.priority),
      message: "الأولوية غير معروفة",
    },
    {
      field: "requested_add_ons",
      ok:
        Array.isArray(addOns) && addOns.every((code) => ADD_ONS.includes(code)),
      message: "قائمة الإضافات المطلوبة غير صحيحة",
    },
    {
      field: "city",
      ok: optionalOneOf(body.city, ["riyadh", "jeddah", "eastern", "other"]),
      message: "المدينة غير معروفة",
    },
    {
      field: "gender",
      ok: optionalOneOf(body.gender, ["male", "female"]),
      message: "الجنس غير صحيح",
    },
    {
      field: "has_accidents",
      ok: optionalOneOf(body.has_accidents, ["yes", "no"]),
      message: "قيمة سجل الحوادث غير صحيحة",
    },
    {
      field: "cars_count",
      ok: optionalOneOf(body.cars_count, ["single", "multiple"]),
      message: "قيمة عدد السيارات غير صحيحة",
    },
  ];

  return rules
    .filter((rule) => !rule.ok)
    .map(({ field, message }) => ({ field, message }));
}

module.exports = {
  validDate,
  pageParams,
  recommendationErrors,
  ageFrom,
  ADD_ONS,
};
