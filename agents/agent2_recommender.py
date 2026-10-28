"""
Agent 2 - Recommendation Agent
يقيّم كل عرض حسب معايير موزونة (وفق القسم 3.2.3.2 من التقرير)
S = Σ (w_i × x_i)
"""

# =====================================================================
# Agent 2 – النسخة الكاملة (القسم 3.2.3.2 من التقرير)
# ---------------------------------------------------------------------
# كل ما فوق هذا السطر هو المسودة الأولى كما هي، بدون أي تعديل.
# ما تحته يطبّق خطوات Figure 3.6 التسع:
#   1) استقبال العروض الموحدة + ملف العميل
#   2) استبعاد العروض غير المؤهلة (نوع التغطية / المركبة / الحداثة)
#   3) استخراج المعايير لكل عرض
#   4) تطبيع كل معيار إلى مقياس 0-1
#   5-6) تطبيق الأوزان وحساب  S = Σ (w_i × x_i)
#   7) ترتيب العروض
#   8-9) اختيار الأعلى وإرساله مع تفصيل الدرجات إلى Agent 3
#
# الاستخدام (دالة عادية وليست async، لا تحتاج await):
#   agent2 = RecommendationAgentV2()
#   result = agent2.run_from_agent1_output(agent1_output)   # مباشرة من مخرجات Agent 1
#   result = agent2.run(unified_quote_set, customer_profile, priority="Budget")  # أو يدوياً
#
# ---------------------------------------------------------------------
# العقد مع Agent 1 (agent1_receiver.py) كما يظهر في test_agent1.py:
#
#   Agent 1 يرجع: {"customer_profile", "unified_quote_set", "provider_status"}
#
#   كل عرض في unified_quote_set يحوي بالضبط هذه الحقول:
#     quote_id, provider_id, provider_name
#     premium (float > 0)            deductible (float)
#     coverage_type ("TPL" / "Comprehensive")
#     add_ons  (قائمة من: agency_repair, roadside_assistance, replacement_car,
#               windshield_cover, gulf_coverage)
#     reliability, workshop_network ("واسع جداً" / "متوسط" / "محدود"),
#     digital_score, retrieved_at
#
#   customer_profile يحوي: national_id, birth_date, driver_age, vehicle_serial,
#     manufacture_year, vehicle_age, vehicle_value,
#     purpose_of_use ("personal" / "commercial" / "family"),
#     annual_mileage, coverage_type, requested_add_ons, priority
#   Agent 2 يستخدم منها فقط: coverage_type, driver_age, vehicle_value,
#   vehicle_age, purpose_of_use, requested_add_ons, priority.
#   (الهوية والرقم التسلسلي لا تدخل في أي حساب ولا تظهر في المخرجات.)
#
# حقول اختيارية لا يرسلها Agent 1 حالياً (الكود يعمل بدونها):
#   coverage_scope : قائمة المخاطر المغطاة ["collision", "theft", ...]
#   eligibility    : dict بحدود الشركة (max_vehicle_age, min_vehicle_value,
#                    max_vehicle_value, min_driver_age, max_driver_age, allowed_use)
#
# أي حقل ناقص يأخذ قيمة محايدة 0.5 ويُسجَّل في defaults_used.
# =====================================================================

import math
from datetime import datetime, timezone
from typing import Optional

WORKSHOP_SCORE = {"واسع جداً": 1.0, "متوسط": 0.6, "محدود": 0.3}
NEUTRAL = 0.5  # قيمة محايدة عند غياب البيانات (نفس منطق المسودة)

# ---------------------------------------------------------------------
# 1) المعايير والأوزان
# ---------------------------------------------------------------------
# المسودة كانت ينقصها معياران من التقرير: نطاق التغطية (المعيار 2) والملاءمة
# لملف السائق والمركبة (المعيار 6). لذلك أخذتُ 20% من كل ملف أوزان
# (10% لكل معيار جديد) وضربتُ الأوزان القديمة في 0.8، فبقيت النِّسَب بينها
# كما صمّمتموها. المعيار 8 (الحداثة) ليس له وزن لأنه شرط أهلية (فلتر).
# workshop_network و digital بقيا من المسودة.
# أسماء الأولويات مطابقة لـ PRIORITIES في Agent 1.
CRITERIA = (
    "premium", "coverage_scope", "coverage_value", "deductible", "add_ons",
    "profile_fit", "reliability", "workshop_network", "digital",
)

# Budget's 65% premium weight preserves the weighted-sum model while ensuring
# meaningful price differences dominate less central preferences.
FULL_PRIORITY_PROFILES = {
    "Balanced": {
        "premium": 0.24, "coverage_scope": 0.10, "coverage_value": 0.16,
        "deductible": 0.12, "add_ons": 0.08, "profile_fit": 0.10,
        "reliability": 0.12, "workshop_network": 0.08, "digital": 0.0,
    },
    "Budget": {
        "premium": 0.65, "coverage_scope": 0.06, "coverage_value": 0.03,
        "deductible": 0.08, "add_ons": 0.03, "profile_fit": 0.06,
        "reliability": 0.05, "workshop_network": 0.04, "digital": 0.0,
    },
    "Service": {
        "premium": 0.12, "coverage_scope": 0.10, "coverage_value": 0.08,
        "deductible": 0.08, "add_ons": 0.08, "profile_fit": 0.10,
        "reliability": 0.28, "workshop_network": 0.16, "digital": 0.0,
    },
    "Digital": {
        "premium": 0.12, "coverage_scope": 0.10, "coverage_value": 0.08,
        "deductible": 0.08, "add_ons": 0.08, "profile_fit": 0.10,
        "reliability": 0.08, "workshop_network": 0.04, "digital": 0.32,
    },
}


def _validate_weights(profiles: dict) -> None:
    """يتأكد أن كل ملف يحوي نفس المعايير ومجموعه = 1 (شرط التقرير)."""
    for name, w in profiles.items():
        if set(w) != set(CRITERIA):
            raise ValueError(f"أوزان '{name}' لا تطابق قائمة المعايير")
        total = sum(w.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"مجموع أوزان '{name}' = {total} وليس 1")


_validate_weights(FULL_PRIORITY_PROFILES)

# ---------------------------------------------------------------------
# 2) ثوابت وقواعد قابلة للتعديل
# ---------------------------------------------------------------------
DEDUCTIBLE_CAP = 1500            # نفس رقم المسودة: تحمّل >= 1500 يعطي صفر
ADD_ONS_FULL_SCORE_COUNT = 3     # نفس المسودة: 3 إضافات = الدرجة الكاملة
REQUESTED_ADDONS_SHARE = 0.7     # لو طلب العميل إضافات: 70% من الدرجة لمطابقتها، 30% للثراء العام
MAX_QUOTE_AGE_SECONDS = 30 * 60  # العرض الأقدم من 30 دقيقة لا يعتبر "حيّاً"

COVERAGE_TYPE_ALIASES = {
    "comprehensive": ("comprehensive", "full", "شامل"),
    "tpl": ("tpl", "third_party", "thirdparty", "ضد_الغير", "طرف_ثالث"),
}

# المخاطر المعتبرة لكل نوع تغطية (تُستخدم فقط إذا أرسل Agent 1 حقل coverage_scope)
RELEVANT_RISKS = {
    "comprehensive": {"collision", "theft", "fire", "natural_events"},
    "tpl": {"third_party_property", "third_party_injury"},
}
# اتساع النوع نفسه عندما لا يحدد العميل نوعاً معيناً
TYPE_BREADTH = {"comprehensive": 1.0, "tpl": 0.4}

# المفاتيح = CANONICAL_ADDONS في Agent 1 (insurers_config). القيم = مرادفات احتياطية.
ADD_ON_ALIASES = {
    "agency_repair": ("agency", "وكالة"),
    "roadside_assistance": ("roadside", "towing", "الطريق", "سحب"),
    "replacement_car": ("replacement", "courtesy", "بديل"),
    "windshield_cover": ("windshield", "windscreen", "glass", "زجاج"),
    "gulf_coverage": ("gulf", "gcc", "geographic", "امتداد", "جغرافي", "الخليج"),
}

# القيم المعتمدة في Agent 1: personal / commercial / family
USE_ALIASES = {
    "commercial": ("commercial", "business", "taxi", "rental", "تجاري", "أجرة", "اجرة"),
    "family": ("family", "عائلي", "عائلة"),
    "personal": ("personal", "private", "شخصي", "خاص"),
}

# عتبات معيار "الملاءمة لملف السائق والمركبة" (المعيار 6)
FIT_RULES = {
    "young_driver_age": 25,         # أقل منها = سائق أعلى خطورة
    "senior_driver_age": 65,        # أكثر منها (أو تساويها) = أعلى خطورة
    "high_value_vehicle": 100_000,  # ريال
    "low_value_vehicle": 30_000,    # ريال
    "new_vehicle_max_age": 5,       # سنوات
    "old_vehicle_min_age": 10,      # سنوات
}


# ---------------------------------------------------------------------
# 3) دوال مساعدة
# ---------------------------------------------------------------------
def _num(x) -> Optional[float]:
    """يحوّل القيمة إلى رقم صالح أو None (يرفض النص غير الرقمي و NaN و bool)."""
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _norm_key(x) -> str:
    return str(x).strip().lower().replace("-", "_").replace(" ", "_")


def _as_list(x) -> list:
    """None -> [] ، نص -> [نص] ، قائمة/مجموعة -> قائمة، غير ذلك -> []."""
    if x is None:
        return []
    if isinstance(x, str):
        return [x]
    if isinstance(x, (list, tuple, set, frozenset)):
        return list(x)
    return []


def _match_alias(value, aliases: dict) -> Optional[str]:
    if value is None:
        return None
    text = _norm_key(value)
    for canonical, words in aliases.items():
        if any(w in text for w in words):
            return canonical
    return None


def _canon_coverage_type(value) -> Optional[str]:
    return _match_alias(value, COVERAGE_TYPE_ALIASES)


def _canon_use(value) -> Optional[str]:
    return _match_alias(value, USE_ALIASES)


def _classify_add_on(value) -> Optional[str]:
    if value is None:
        return None
    text = _norm_key(value)
    if text in ADD_ON_ALIASES:  # الاسم المعتمد من Agent 1 يُطابَق حرفياً أولاً
        return text
    return _match_alias(value, ADD_ON_ALIASES)


def _parse_time(value, naive_is_utc: bool = False) -> Optional[datetime]:
    """يقبل datetime أو epoch (ثوانٍ) أو نص ISO.
    الوقت بدون منطقة زمنية يُعتبر وقت الجهاز المحلي (مثل datetime.now())،
    أو UTC إذا كان naive_is_utc=True (مثل datetime.utcnow())."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc) if naive_is_utc else dt.astimezone()
    return dt


def _exceeds(value, limit) -> bool:
    v, l = _num(value), _num(limit)
    return v is not None and l is not None and v > l


def _below(value, limit) -> bool:
    v, l = _num(value), _num(limit)
    return v is not None and l is not None and v < l


def _identity(q) -> dict:
    """بيانات تعريف العرض بنفس أسماء Agent 1 (تُستخدم في قائمة المرفوضات)."""
    if not isinstance(q, dict):
        return {"provider_id": None, "provider_name": "unknown", "quote_id": None}
    return {
        "provider_id": q.get("provider_id"),
        "provider_name": q.get("provider_name") or q.get("provider_id") or "unknown",
        "quote_id": q.get("quote_id"),
    }


# ---------------------------------------------------------------------
# 4) الوكيل
# ---------------------------------------------------------------------
class RecommendationAgentV2:
    def __init__(self, max_quote_age_seconds: Optional[int] = MAX_QUOTE_AGE_SECONDS,
                 premium_mode: str = "ratio", naive_timestamps_are_utc: bool = False):
        """
        max_quote_age_seconds    : أقصى عمر للعرض (None = بدون فحص العمر).
        premium_mode             :
            "ratio"  -> درجة القسط = أرخص قسط ÷ قسط العرض (تحافظ على التناسب).
            "minmax" -> نفس طريقة المسودة (الأرخص 1 والأغلى 0).
        naive_timestamps_are_utc : اجعلها True إذا كان retrieved_at من Agent 1 نصاً بدون منطقة
                                   زمنية ومأخوذاً بتوقيت UTC (مثل datetime.utcnow()).
        """
        if premium_mode not in ("ratio", "minmax"):
            raise ValueError("premium_mode must be 'ratio' or 'minmax'")
        self.max_quote_age_seconds = max_quote_age_seconds
        self.premium_mode = premium_mode
        self.naive_timestamps_are_utc = naive_timestamps_are_utc

    # ---------------- الدخول المباشر من مخرجات Agent 1 ----------------
    def run_from_agent1_output(self, agent1_output: dict, priority: Optional[str] = None) -> dict:
        """يستقبل ما يرجعه DataReceiverAgent.run() كما هو. الأولوية تؤخذ من
        customer_profile["priority"] إلا إذا مُرّرت صراحة. provider_status يمر كما هو
        (ليعرف Agent 3 / الواجهة أي شركة لم ترجع عرضاً)."""
        out = agent1_output or {}
        return self.run(out.get("unified_quote_set") or [], out.get("customer_profile") or {},
                        priority, provider_status=out.get("provider_status"))

    # ---------------- نقطة الدخول (الخطوات 1 → 9) ----------------
    def run(self, unified_quote_set: list, customer_profile: dict,
            priority: Optional[str] = None, provider_status: Optional[list] = None) -> dict:
        profile = customer_profile or {}
        # الأولوية: المُمرَّرة صراحة، ثم الموجودة في ملف العميل، ثم Balanced
        weights, priority_used = self._resolve_weights(
            priority if priority is not None else profile.get("priority"))
        status = list(provider_status or [])

        if not unified_quote_set:
            return self._no_offer("لا توجد عروض متاحة", [], weights, priority_used, status)

        # الخطوة 2: استبعاد غير المؤهل
        eligible, rejected = self._filter(unified_quote_set, profile)
        if not eligible:
            return self._no_offer("لا توجد عروض مؤهلة (no eligible offer)",
                                  rejected, weights, priority_used, status)

        # الخطوات 3-6: استخراج المعايير، التطبيع، الأوزان، الدرجة
        scored = self._score(eligible, profile, weights)

        # الإضافات التي طلبها العميل صراحةً تُعامَل كمتطلب: العروض الأقل نقصاً في الإضافات
        # المطلوبة تُرتَّب أولاً (التي توفرها كلها، ثم التي ينقصها واحدة، ...)، ثم بالدرجة.
        # معادلة الدرجة S = Σ wᵢxᵢ لا تتغير؛ هذا مفتاح ترتيب أول فقط. السبب: بدونه قد يحصل
        # العميل الذي طلب "إصلاح وكالة" على باقة اقتصادية بدونها لأن وزن معيار الإضافات صغير.
        for s in scored:
            s["missing_requested"] = len(s["entry"]["requested_add_ons_missing"])
            s["entry"]["covers_requested_add_ons"] = s["missing_requested"] == 0

        # الخطوة 7: الترتيب. عند التعادل: الأكثر موثوقية ثم الأرخص (المعيار 7 = كاسر تعادل)
        scored.sort(key=lambda s: (
            s["missing_requested"],
            -s["entry"]["suitability_score"],
            -s["reliability"],
            s["premium"],
        ))
        ranked = []
        for i, s in enumerate(scored, start=1):
            s["entry"]["rank"] = i
            ranked.append(s["entry"])

        # الخطوتان 8-9: الاختيار والإخراج إلى Agent 3
        return {
            "selected": ranked[0],
            "ranked": ranked,
            "rejected": rejected,
            "weights": weights,
            "priority": priority_used,
            "provider_status": status,
            "reason": None,
        }

    # ---------------- الأوزان ----------------
    @staticmethod
    def _resolve_weights(priority) -> tuple:
        key = str(priority).strip().lower()
        for name, w in FULL_PRIORITY_PROFILES.items():
            if name.lower() == key:
                return dict(w), name
        return dict(FULL_PRIORITY_PROFILES["Balanced"]), "Balanced"  # كما في المسودة

    @staticmethod
    def _no_offer(reason, rejected, weights, priority_used, status) -> dict:
        return {"selected": None, "ranked": [], "rejected": rejected, "weights": weights,
                "priority": priority_used, "provider_status": status, "reason": reason}

    # ---------------- الخطوة 2: الفلترة ----------------
    def _filter(self, quotes, profile) -> tuple:
        requested_type = _canon_coverage_type(profile.get("coverage_type"))
        eligible, rejected = [], []
        for q in quotes:
            reason = self._rejection_reason(q, profile, requested_type)
            if reason is None:
                eligible.append(q)
            else:
                rejected.append({**_identity(q), "reason": reason})
        return eligible, rejected

    def _rejection_reason(self, q, profile, requested_type) -> Optional[str]:
        """يرجع كود سبب الرفض أو None إذا كان العرض مؤهلاً."""
        if not isinstance(q, dict):
            return "invalid_quote"
        premium = _num(q.get("premium"))
        if premium is None or premium <= 0:
            return "invalid_premium"

        # المعيار 8: الحداثة. Agent 1 يختم كل عرض بـ retrieved_at لحظة جلبه.
        # (عرض بلا retrieved_at لا يُرفض: لا نستطيع الحكم عليه، وAgent 1 يرسله دائماً.)
        if q.get("retrieved_at") is not None:
            ts = _parse_time(q["retrieved_at"], self.naive_timestamps_are_utc)
            if ts is None:
                return "unreadable_retrieved_at"
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if self.max_quote_age_seconds is not None and age > self.max_quote_age_seconds:
                return "stale_quote"

        # عدم تطابق نوع التغطية مع المطلوب
        if requested_type is not None:
            q_type = _canon_coverage_type(q.get("coverage_type"))
            if q_type is None:
                return "coverage_type_unknown"
            if q_type != requested_type:
                return "coverage_type_mismatch"

        # عدم انطباق العرض على مركبة/سائق العميل (يعمل فقط إذا أرسل Agent 1 حقل eligibility)
        rules = q.get("eligibility")
        if not isinstance(rules, dict):
            rules = {}
        if _exceeds(profile.get("vehicle_age"), rules.get("max_vehicle_age")):
            return "vehicle_too_old"
        if _below(profile.get("vehicle_value"), rules.get("min_vehicle_value")):
            return "vehicle_value_too_low"
        if _exceeds(profile.get("vehicle_value"), rules.get("max_vehicle_value")):
            return "vehicle_value_too_high"
        if _below(profile.get("driver_age"), rules.get("min_driver_age")):
            return "driver_too_young"
        if _exceeds(profile.get("driver_age"), rules.get("max_driver_age")):
            return "driver_too_old"
        allowed = _as_list(rules.get("allowed_use"))
        use = _canon_use(profile.get("purpose_of_use"))
        if allowed and use is not None and use not in {_canon_use(a) for a in allowed}:
            return "use_not_allowed"
        return None

    # ---------------- الخطوات 3-6: التقييم ----------------
    def _score(self, quotes, profile, weights) -> list:
        requested_type = _canon_coverage_type(profile.get("coverage_type"))
        requested_addons = {k for k in (_classify_add_on(a) for a in _as_list(profile.get("requested_add_ons"))) if k}
        premiums = [_num(q["premium"]) for q in quotes]
        min_p = min(premiums)
        max_p = max(premiums)

        rows = []
        for q, premium in zip(quotes, premiums):
            used = []  # الحقول الناقصة التي أخذت قيمة محايدة
            x = {}
            x["premium"] = self._premium_score(premium, min_p, max_p)
            x["deductible"] = self._deductible_score(q, used)
            add_on_keys, x["add_ons"] = self._add_ons_score(q, requested_addons, used)
            x["coverage_scope"] = self._scope_score(q, requested_type)
            x["reliability"] = self._reliability_score(q, used)
            x["workshop_network"] = self._workshop_score(q, used)
            x["digital"] = self._digital_score(q, used)
            x["profile_fit"] = self._fit_score(x, add_on_keys, profile, used)

            # قيمة التغطية مقابل السعر = (الحماية ÷ القسط)، ثم تُقسم على أفضل قيمة.
            # الرخيص الضعيف ينخفض بسبب الحماية، والغالي بلا حاجة ينخفض بسبب القسط.
            protection = max(0.05, 0.6 * x["coverage_scope"] + 0.2 * x["deductible"] + 0.2 * x["add_ons"])
            rows.append({"q": q, "x": x, "used": used, "premium": premium,
                         "add_on_keys": add_on_keys, "value_raw": protection / premium})

        best_value = max(r["value_raw"] for r in rows)
        scored = []
        for r in rows:
            x = r["x"]
            x["coverage_value"] = r["value_raw"] / best_value

            total = sum(weights[c] * x[c] for c in CRITERIA)  # S = Σ (w_i × x_i)
            entry = {
                **r["q"],
                "suitability_score": round(total, 4),
                "score_breakdown": {
                    "premium_score": round(x["premium"], 4),
                    "coverage_scope_score": round(x["coverage_scope"], 4),
                    "coverage_value_score": round(x["coverage_value"], 4),
                    "deductible_score": round(x["deductible"], 4),
                    "addons_score": round(x["add_ons"], 4),
                    "profile_fit_score": round(x["profile_fit"], 4),
                    "reliability_score": round(x["reliability"], 4),
                    "workshop_score": round(x["workshop_network"], 4),
                    "digital_score": round(x["digital"], 4),
                },
                # مساهمة كل معيار في الدرجة النهائية (w_i × x_i) لتستخدمها Agent 3
                "weighted_contributions": {c: round(weights[c] * x[c], 4) for c in CRITERIA},
                # الإضافات التي طلبها العميل: ما وفّره العرض وما ينقصه (لشرح Agent 3)
                "requested_add_ons_matched": sorted(requested_addons & r["add_on_keys"]),
                "requested_add_ons_missing": sorted(requested_addons - r["add_on_keys"]),
                "defaults_used": [c for c in r["used"] if weights[c] > 0],
            }
            scored.append({"entry": entry, "reliability": x["reliability"], "premium": r["premium"]})
        return scored

    # ---------------- تطبيع كل معيار إلى 0-1 ----------------
    def _premium_score(self, premium, min_p, max_p) -> float:
        if self.premium_mode == "minmax":
            return 1.0 if max_p == min_p else 1 - (premium - min_p) / (max_p - min_p)
        return min_p / premium

    @staticmethod
    def _deductible_score(q, used) -> float:
        d = _num(q.get("deductible"))
        if d is None or d < 0:
            used.append("deductible")
            return NEUTRAL
        return _clamp01(1 - d / DEDUCTIBLE_CAP)  # المسودة كانت تعطي قيمة سالبة فوق 1500

    @staticmethod
    def _add_ons_score(q, requested, used) -> tuple:
        if q.get("add_ons") is None:
            used.append("add_ons")
        known, unknown = set(), 0
        for item in _as_list(q.get("add_ons")):
            key = _classify_add_on(item)
            if key:
                known.add(key)  # الإضافة المعروفة تُحسب كاملة ولا تتكرر
            else:
                unknown += 1    # إضافة غير معروفة تُحسب بنصف قيمة
        general = min((len(known) + 0.5 * unknown) / ADD_ONS_FULL_SCORE_COUNT, 1.0)
        if not requested:
            return known, general
        # العميل طلب إضافات محددة: مطابقتها هي الأهم
        matched = len(requested & known) / len(requested)
        return known, REQUESTED_ADDONS_SHARE * matched + (1 - REQUESTED_ADDONS_SHARE) * general

    @staticmethod
    def _scope_score(q, requested_type) -> float:
        """Agent 1 يرسل نوع التغطية فقط (بدون قائمة المخاطر)، فإذا لم يوجد coverage_scope
        يعتمد المعيار على النوع وحده."""
        q_type = _canon_coverage_type(q.get("coverage_type"))
        # مكوّن النوع: مضمون التطابق بعد الفلترة إذا حدد العميل نوعاً
        type_part = 1.0 if requested_type else TYPE_BREADTH.get(q_type, NEUTRAL)
        # مكوّن نطاق المخاطر (اختياري)
        relevant = RELEVANT_RISKS.get(q_type)
        covered = q.get("coverage_scope")
        if relevant and covered is not None:
            risk_part = len({_norm_key(c) for c in _as_list(covered)} & relevant) / len(relevant)
            return 0.5 * type_part + 0.5 * risk_part
        return type_part

    @staticmethod
    def _reliability_score(q, used) -> float:
        r = _num(q.get("reliability"))
        if r is None or r < 0:
            used.append("reliability")
            return NEUTRAL
        if r <= 1:
            return r
        if r <= 5:
            return r / 5
        if r <= 100:
            return r / 100
        return 1.0

    @staticmethod
    def _workshop_score(q, used) -> float:
        w = q.get("workshop_network")
        if isinstance(w, str) and w.strip() in WORKSHOP_SCORE:  # الجدول من المسودة
            return WORKSHOP_SCORE[w.strip()]
        n = _num(w)
        if n is not None and 0 <= n <= 1:
            return n
        used.append("workshop_network")
        return NEUTRAL

    @staticmethod
    def _digital_score(q, used) -> float:
        d = _num(q.get("digital_score"))
        if d is None:
            used.append("digital")
            return NEUTRAL
        return _clamp01(d)

    @staticmethod
    def _fit_score(x, add_on_keys, profile, used) -> float:
        """المعيار 6: مدى ملاءمة العرض لعمر السائق وقيمة المركبة وعمرها والاستخدام.
        كل قاعدة تنطبق فقط إذا توفرت بيانات العميل لها؛ النتيجة متوسط القواعد المنطبقة."""
        R = FIT_RULES
        parts = []

        age = _num(profile.get("driver_age"))
        if age is not None and (age < R["young_driver_age"] or age >= R["senior_driver_age"]):
            # سائق أعلى خطورة: يهمه نطاق التغطية وانخفاض التحمل
            parts.append(0.5 * x["coverage_scope"] + 0.5 * x["deductible"])

        value = _num(profile.get("vehicle_value"))
        if value is not None:
            if value >= R["high_value_vehicle"]:
                parts.append(x["coverage_scope"])  # مركبة غالية: التغطية الواسعة أهم
            elif value <= R["low_value_vehicle"]:
                parts.append(x["premium"])         # مركبة رخيصة: لا داعي لدفع الكثير

        v_age = _num(profile.get("vehicle_age"))
        if v_age is not None:
            if v_age <= R["new_vehicle_max_age"]:
                parts.append(1.0 if "agency_repair" in add_on_keys else 0.4)  # الوكالة تفيد الحديثة
            elif v_age >= R["old_vehicle_min_age"]:
                parts.append(x["premium"])         # قديمة: السعر أهم من الكماليات

        if _canon_use(profile.get("purpose_of_use")) == "commercial":
            needed = {"roadside_assistance", "replacement_car"}
            parts.append(len(needed & add_on_keys) / len(needed))

        if not parts:
            used.append("profile_fit")
            return NEUTRAL
        return _clamp01(sum(parts) / len(parts))


# لو أردتم أن يستخدم باقي المشروع النسخة الكاملة دون تغيير الـ imports،
# فكّوا التعليق عن السطر التالي (سيحلّ محل المسودة عند الاستيراد):
# RecommendationAgent = RecommendationAgentV2


# ---------------------------------------------------------------------
# تشغيل تجريبي: python agent2_recommender.py
# (عروض بنفس شكل مخرجات Agent 1؛ الأقساط من التقرير والباقي تقديري)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    _now = datetime.now(timezone.utc).isoformat()

    def _demo_quote(pid, name, premium, deductible, add_ons, reliability, workshop):
        return {"quote_id": f"{pid}-DEMO", "provider_id": pid, "provider_name": name,
                "premium": float(premium), "coverage_type": "TPL", "deductible": float(deductible),
                "add_ons": add_ons, "reliability": reliability, "workshop_network": workshop,
                "digital_score": 0.5, "retrieved_at": _now}

    demo_output = {
        "customer_profile": {"coverage_type": "TPL", "driver_age": 34, "vehicle_value": 60_000,
                             "vehicle_age": 7, "purpose_of_use": "personal", "requested_add_ons": [],
                             "priority": "Budget"},
        "unified_quote_set": [
            _demo_quote("tawuniya", "Tawuniya", 483, 500, ["roadside_assistance", "gulf_coverage"], 0.92, "واسع جداً"),
            _demo_quote("medgulf", "Medgulf", 469, 750, ["roadside_assistance"], 0.72, "متوسط"),
            _demo_quote("acig", "ACIG", 428, 1000, [], 0.65, "محدود"),
            _demo_quote("rajhi", "Takaful Al-Rajhi", 507, 750, ["roadside_assistance"], 0.85, "متوسط"),
        ],
        "provider_status": [],
    }

    for prio in (None, "Balanced", "Service"):  # None = الأولوية من ملف العميل (Budget)
        out = RecommendationAgentV2().run_from_agent1_output(demo_output, priority=prio)
        print(f"\n[{out['priority']}]")
        for q in out["ranked"]:
            print(f"  #{q['rank']} {q['provider_name']:<18} premium={q['premium']}  score={q['suitability_score']}")
