"""
اختبارات Agent 2 بشكل مستقل (لا تحتاج تشغيل أي سيرفر ولا شبكة):
    cd agents && python -m pytest tests -v

Agent 2 دالة حسابية بحتة، فنغذّيه بعروض مبنية بنفس شكل مخرجات Agent 1 بالضبط
(نفس مفاتيح UNIFIED_KEYS المختبرة في test_agent1.py) ونتحقق من الفلترة والتقييم والترتيب.

آخر قسم (TestIntegrationWithAgent1) يشغّل Agent 1 الحقيقي فوق Mock Insurance API ثم يمرر
مخرجاته إلى Agent 2. هو يتخطى نفسه تلقائياً إذا لم تكن وحدات Agent 1 قابلة للاستيراد.
"""

import asyncio
import copy
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import agent2_recommender as a2
from agent2_recommender import (
    CRITERIA,
    FULL_PRIORITY_PROFILES,
    RecommendationAgentV2,
    _validate_weights,
)

# نفس القيم المعرّفة في Agent 1 (agent1_receiver.PRIORITIES / insurers_config.CANONICAL_ADDONS)
PRIORITIES = ("Budget", "Service", "Digital", "Balanced")
CANONICAL_ADDONS = ("agency_repair", "roadside_assistance", "replacement_car", "windshield_cover", "gulf_coverage")

# نفس UNIFIED_KEYS في test_agent1.py
UNIFIED_KEYS = {
    "quote_id", "provider_id", "provider_name", "premium", "coverage_type", "deductible",
    "add_ons", "reliability", "workshop_network", "digital_score", "retrieved_at",
}

RESULT_KEYS = {"selected", "ranked", "rejected", "weights", "priority", "provider_status", "reason"}

# اسم المعيار في الأوزان -> اسم حقله في score_breakdown
BREAKDOWN_KEY = {
    "premium": "premium_score",
    "coverage_scope": "coverage_scope_score",
    "coverage_value": "coverage_value_score",
    "deductible": "deductible_score",
    "add_ons": "addons_score",
    "profile_fit": "profile_fit_score",
    "reliability": "reliability_score",
    "workshop_network": "workshop_score",
    "digital": "digital_score",
}


# ============================================================ أدوات مساعدة
def iso_now(seconds_ago=0):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def make_quote(provider_id="p1", **over):
    """عرض بنفس شكل عروض Agent 1 (UNIFIED_KEYS بالضبط)."""
    q = {
        "quote_id": f"{provider_id}-Q1",
        "provider_id": provider_id,
        "provider_name": provider_id.title(),
        "premium": 480.0,
        "coverage_type": "TPL",
        "deductible": 1000.0,
        "add_ons": [],
        "reliability": 0.8,
        "workshop_network": "متوسط",
        "digital_score": 0.5,
        "retrieved_at": iso_now(),
    }
    q.update(over)
    return q


def make_profile(**over):
    """customer_profile بنفس شكل مخرجات validate_customer_data في Agent 1.
    القيم الافتراضية لا تفعّل أي قاعدة من قواعد معيار الملاءمة (عمر 40 / قيمة 60 ألف / مركبة عمرها 7)،
    فتبقى بقية المعايير معزولة في الاختبارات."""
    p = {
        "national_id": "1098765432",
        "birth_date": "1986-01-01",
        "driver_age": 40,
        "vehicle_serial": "123456789",
        "manufacture_year": 2019,
        "vehicle_age": 7,
        "vehicle_value": 60000.0,
        "purpose_of_use": "personal",
        "annual_mileage": "medium",
        "coverage_type": "TPL",
        "requested_add_ons": [],
        "priority": "Balanced",
    }
    p.update(over)
    return p


def run(quotes, profile=None, priority=None, agent=None):
    profile = make_profile() if profile is None else profile
    return (agent or RecommendationAgentV2()).run(quotes, profile, priority)


def by_provider(result):
    return {q["provider_id"]: q for q in result["ranked"]}


def part(result, provider_id, key):
    return by_provider(result)[provider_id]["score_breakdown"][key]


def report_quotes():
    """السيناريو الموصوف في التقرير (Figure 3.16): الأقساط من التقرير (483 / 507 / 469 / 428)،
    أما بقية الخصائص فتقديرية لتحاكي القصة المكتوبة (تعاونية: أوسع شبكة ورش وأعلى موثوقية)."""
    return [
        make_quote("tawuniya", provider_name="Tawuniya", premium=483.0, deductible=500.0,
                   add_ons=["roadside_assistance", "gulf_coverage"], reliability=0.92, workshop_network="واسع جداً"),
        make_quote("medgulf", provider_name="Medgulf", premium=469.0, deductible=750.0,
                   add_ons=["roadside_assistance"], reliability=0.72, workshop_network="متوسط"),
        make_quote("acig", provider_name="ACIG", premium=428.0, deductible=1000.0,
                   add_ons=[], reliability=0.65, workshop_network="محدود"),
        make_quote("rajhi", provider_name="Takaful Al-Rajhi", premium=507.0, deductible=750.0,
                   add_ons=["roadside_assistance"], reliability=0.85, workshop_network="متوسط"),
    ]


def five_quotes():
    """خمس شركات (المخطط للنظام). الخامسة اسمها مؤقت لأن Agent 2 لا يعتمد على أسماء الشركات."""
    return report_quotes() + [
        make_quote("provider5", provider_name="Provider 5 (placeholder)", premium=495.0, deductible=750.0,
                   add_ons=["windshield_cover"], reliability=0.78, workshop_network="متوسط"),
    ]


def agent1_output(quotes=None, profile=None, provider_status=None):
    """شكل ما يرجعه DataReceiverAgent.run()."""
    quotes = five_quotes() if quotes is None else quotes
    if provider_status is None:
        provider_status = [{"provider_id": q["provider_id"], "provider_name": q["provider_name"], "ok": True,
                            "offers_count": 1, "error_type": None} for q in quotes]
    return {
        "customer_profile": make_profile(priority="Budget") if profile is None else profile,
        "unified_quote_set": quotes,
        "provider_status": provider_status,
    }


# ============================================================ 1) الأوزان
class TestWeights:
    @pytest.mark.parametrize("priority", PRIORITIES)
    def test_weights_sum_to_one(self, priority):
        assert sum(FULL_PRIORITY_PROFILES[priority].values()) == pytest.approx(1.0)

    def test_priority_names_match_agent1(self):
        assert set(FULL_PRIORITY_PROFILES) == set(PRIORITIES)

    @pytest.mark.parametrize("priority", PRIORITIES)
    def test_every_profile_covers_all_criteria(self, priority):
        assert set(FULL_PRIORITY_PROFILES[priority]) == set(CRITERIA)

    @pytest.mark.parametrize("priority,top", [
        ("Balanced", "premium"), ("Budget", "premium"), ("Service", "reliability"), ("Digital", "digital"),
    ])
    def test_each_priority_emphasizes_its_criterion(self, priority, top):
        w = FULL_PRIORITY_PROFILES[priority]
        assert max(w, key=w.get) == top

    def test_digital_weight_only_in_digital_priority(self):
        for p in PRIORITIES:
            assert (FULL_PRIORITY_PROFILES[p]["digital"] > 0) == (p == "Digital")

    def test_validator_rejects_wrong_sum(self):
        bad = dict(FULL_PRIORITY_PROFILES["Balanced"], premium=0.9)
        with pytest.raises(ValueError):
            _validate_weights({"Bad": bad})

    def test_validator_rejects_missing_criterion(self):
        bad = {k: v for k, v in FULL_PRIORITY_PROFILES["Balanced"].items() if k != "digital"}
        with pytest.raises(ValueError):
            _validate_weights({"Bad": bad})

    def test_result_reports_the_weights_used(self):
        res = run([make_quote("a")], priority="Budget")
        assert res["weights"] == FULL_PRIORITY_PROFILES["Budget"]
        assert res["priority"] == "Budget"


# ============================================================ 2) الفلترة (الخطوة 2 في Figure 3.6)
FRESH_TIMESTAMPS = {
    "iso_utc_z": lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "iso_with_offset": lambda: datetime.now(timezone(timedelta(hours=3))).isoformat(),
    "epoch_seconds": lambda: time.time(),
    "aware_datetime": lambda: datetime.now(timezone.utc),
    "naive_local_iso": lambda: datetime.now().isoformat(),
    "naive_local_datetime": lambda: datetime.now(),
}


class TestFiltering:
    def test_coverage_type_mismatch_removed(self):
        res = run([make_quote("a"), make_quote("b", coverage_type="Comprehensive")], make_profile(coverage_type="TPL"))
        assert [q["provider_id"] for q in res["ranked"]] == ["a"]
        assert res["rejected"] == [
            {"provider_id": "b", "provider_name": "B", "quote_id": "b-Q1", "reason": "coverage_type_mismatch"}]

    def test_unknown_coverage_type_removed_when_type_requested(self):
        res = run([make_quote("a", coverage_type=None)])
        assert res["selected"] is None and res["rejected"][0]["reason"] == "coverage_type_unknown"

    def test_no_type_filter_when_customer_did_not_request_one(self):
        res = run([make_quote("a"), make_quote("b", coverage_type="Comprehensive")], make_profile(coverage_type=None))
        assert {q["provider_id"] for q in res["ranked"]} == {"a", "b"}

    @pytest.mark.parametrize("premium", [None, 0, -5, "abc", float("nan"), True])
    def test_invalid_premium_removed(self, premium):
        res = run([make_quote("bad", premium=premium), make_quote("ok")])
        assert [q["provider_id"] for q in res["ranked"]] == ["ok"]
        assert res["rejected"][0]["reason"] == "invalid_premium"

    def test_non_dict_quote_removed(self):
        res = run(["garbage", make_quote("ok")])
        assert [q["provider_id"] for q in res["ranked"]] == ["ok"]
        assert res["rejected"][0]["reason"] == "invalid_quote"
        assert res["rejected"][0]["provider_name"] == "unknown"

    def test_stale_quote_removed(self):
        res = run([make_quote("old", retrieved_at=iso_now(3600)), make_quote("new", retrieved_at=iso_now(60))])
        assert [q["provider_id"] for q in res["ranked"]] == ["new"]
        assert res["rejected"][0]["reason"] == "stale_quote"

    @pytest.mark.parametrize("fmt", sorted(FRESH_TIMESTAMPS))
    def test_accepts_common_timestamp_formats(self, fmt):
        res = run([make_quote("a", retrieved_at=FRESH_TIMESTAMPS[fmt]())])
        assert res["selected"] is not None, fmt

    def test_naive_utc_timestamp_with_flag(self):
        """لو كان Agent 1 يرسل وقت UTC بدون منطقة زمنية (utcnow)، نفعّل naive_timestamps_are_utc."""
        ts = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        agent = RecommendationAgentV2(naive_timestamps_are_utc=True)
        assert run([make_quote("a", retrieved_at=ts)], agent=agent)["selected"] is not None

    @pytest.mark.parametrize("value", ["yesterday-ish", {}, [], "2026-13-45T00:00:00"])
    def test_unreadable_timestamp_removed(self, value):
        res = run([make_quote("a", retrieved_at=value)])
        assert res["selected"] is None and res["rejected"][0]["reason"] == "unreadable_retrieved_at"

    def test_missing_timestamp_is_not_rejected(self):
        q = make_quote("a")
        del q["retrieved_at"]
        assert run([q])["selected"] is not None

    def test_age_check_can_be_disabled(self):
        agent = RecommendationAgentV2(max_quote_age_seconds=None)
        assert run([make_quote("a", retrieved_at=iso_now(36000))], agent=agent)["selected"] is not None

    @pytest.mark.parametrize("rules,profile_over,reason", [
        ({"max_vehicle_age": 10}, {"vehicle_age": 12}, "vehicle_too_old"),
        ({"min_vehicle_value": 80000}, {"vehicle_value": 50000.0}, "vehicle_value_too_low"),
        ({"max_vehicle_value": 100000}, {"vehicle_value": 150000.0}, "vehicle_value_too_high"),
        ({"min_driver_age": 21}, {"driver_age": 19}, "driver_too_young"),
        ({"max_driver_age": 70}, {"driver_age": 75}, "driver_too_old"),
        ({"allowed_use": ["personal"]}, {"purpose_of_use": "commercial"}, "use_not_allowed"),
    ])
    def test_insurer_eligibility_rules_when_provided(self, rules, profile_over, reason):
        """Agent 1 لا يرسل eligibility حالياً؛ هذا الخطاف يعمل لو أضافه لاحقاً."""
        res = run([make_quote("a", eligibility=rules)], make_profile(**profile_over))
        assert res["selected"] is None and res["rejected"][0]["reason"] == reason

    def test_eligibility_passes_when_inside_limits(self):
        rules = {"max_vehicle_age": 10, "allowed_use": ["personal", "family"], "min_driver_age": 21}
        res = run([make_quote("a", eligibility=rules)], make_profile(purpose_of_use="family"))
        assert res["selected"] is not None

    def test_all_rejected_returns_no_eligible_offer(self):
        res = run([make_quote("a", coverage_type="Comprehensive"), make_quote("b", premium=-1)])
        assert res["selected"] is None and res["ranked"] == []
        assert "no eligible offer" in res["reason"]
        assert len(res["rejected"]) == 2

    def test_empty_quote_set(self):
        res = run([])
        assert res["selected"] is None and res["ranked"] == [] and res["rejected"] == [] and res["reason"]

    def test_no_offer_results_keep_the_same_shape(self):
        for quotes in ([], None, [make_quote("a", coverage_type="Comprehensive")]):
            assert set(run(quotes)) == RESULT_KEYS

    def test_success_result_shape(self):
        res = run([make_quote("a")])
        assert set(res) == RESULT_KEYS and res["reason"] is None and res["rejected"] == []


# ============================================================ 3) التقييم (الخطوات 3-6)
class TestScoring:
    # ---------- القسط
    def test_ratio_premium_score_is_proportional(self):
        res = run([make_quote("a", premium=400.0), make_quote("b", premium=500.0)])
        assert part(res, "a", "premium_score") == pytest.approx(1.0)
        assert part(res, "b", "premium_score") == pytest.approx(0.8)

    def test_minmax_premium_mode_matches_draft_behavior(self):
        agent = RecommendationAgentV2(premium_mode="minmax")
        res = run([make_quote("a", premium=400.0), make_quote("b", premium=450.0), make_quote("c", premium=500.0)], agent=agent)
        assert [part(res, p, "premium_score") for p in "abc"] == [1.0, 0.5, 0.0]

    def test_ratio_mode_does_not_blow_up_small_gaps(self):
        """428 مقابل 507 فرق 79 ريال فقط: min-max يعطي الأغلى صفراً، والنسبة تبقي الفرق صغيراً."""
        quotes = [make_quote("cheap", premium=428.0), make_quote("dear", premium=507.0)]
        ratio = run(quotes)
        minmax = run(quotes, agent=RecommendationAgentV2(premium_mode="minmax"))
        assert part(minmax, "dear", "premium_score") == 0.0
        assert part(ratio, "dear", "premium_score") > 0.8

    @pytest.mark.parametrize("mode", ["ratio", "minmax"])
    def test_equal_premiums_no_division_by_zero(self, mode):
        res = run([make_quote("a"), make_quote("b")], agent=RecommendationAgentV2(premium_mode=mode))
        assert part(res, "a", "premium_score") == part(res, "b", "premium_score") == 1.0

    def test_bad_premium_mode_rejected(self):
        with pytest.raises(ValueError):
            RecommendationAgentV2(premium_mode="median")

    # ---------- التحمّل
    @pytest.mark.parametrize("deductible,expected", [(0.0, 1.0), (750.0, 0.5), (1500.0, 0.0), (5000.0, 0.0)])
    def test_deductible_score_never_negative(self, deductible, expected):
        res = run([make_quote("a", deductible=deductible)])
        assert part(res, "a", "deductible_score") == pytest.approx(expected)

    @pytest.mark.parametrize("value", [None, -1.0, "abc"])
    def test_bad_deductible_is_neutral_and_reported(self, value):
        q = by_provider(run([make_quote("a", deductible=value)]))["a"]
        assert q["score_breakdown"]["deductible_score"] == 0.5
        assert "deductible" in q["defaults_used"]

    # ---------- الإضافات
    @pytest.mark.parametrize("addon", CANONICAL_ADDONS)
    def test_each_agent1_addon_name_is_recognized(self, addon):
        """الأسماء المعتمدة في Agent 1 تُحسب كاملة (إضافة واحدة = ثلث الدرجة)."""
        res = run([make_quote("a", add_ons=[addon])])
        assert part(res, "a", "addons_score") == pytest.approx(1 / 3, abs=1e-3)

    def test_addons_score_is_capped_at_one(self):
        three = run([make_quote("a", add_ons=list(CANONICAL_ADDONS[:3]))])
        five = run([make_quote("a", add_ons=list(CANONICAL_ADDONS))])
        assert part(three, "a", "addons_score") == part(five, "a", "addons_score") == 1.0

    def test_unknown_addon_counts_half_and_duplicates_count_once(self):
        unknown = run([make_quote("a", add_ons=["made_up_addon"])])
        dup = run([make_quote("a", add_ons=["agency_repair", "وكالة"])])
        assert part(unknown, "a", "addons_score") == pytest.approx(0.5 / 3, abs=1e-3)
        assert part(dup, "a", "addons_score") == pytest.approx(1 / 3, abs=1e-3)

    @pytest.mark.parametrize("text,canonical", [
        ("مساعدة على الطريق", "roadside_assistance"),
        ("سيارة بديلة", "replacement_car"),
        ("إصلاح بالوكالة", "agency_repair"),
        ("زجاج أمامي", "windshield_cover"),
        ("تغطية دول الخليج", "gulf_coverage"),
    ])
    def test_arabic_addon_names_map_to_canonical(self, text, canonical):
        res = run([make_quote("a", add_ons=[text])], make_profile(requested_add_ons=[canonical]))
        assert res["selected"]["requested_add_ons_matched"] == [canonical]

    def test_requested_addons_dominate_the_addons_score(self):
        profile = make_profile(requested_add_ons=["roadside_assistance"])
        res = run([make_quote("has", add_ons=["roadside_assistance"]), make_quote("lacks", add_ons=["windshield_cover"])], profile)
        assert part(res, "has", "addons_score") > part(res, "lacks", "addons_score")
        assert by_provider(res)["has"]["requested_add_ons_matched"] == ["roadside_assistance"]
        assert by_provider(res)["has"]["requested_add_ons_missing"] == []
        assert by_provider(res)["lacks"]["requested_add_ons_matched"] == []
        assert by_provider(res)["lacks"]["requested_add_ons_missing"] == ["roadside_assistance"]

    def test_all_requested_addons_matched_gives_at_least_seventy_percent(self):
        profile = make_profile(requested_add_ons=["roadside_assistance", "gulf_coverage"])
        res = run([make_quote("a", add_ons=["roadside_assistance", "gulf_coverage"])], profile)
        assert part(res, "a", "addons_score") >= a2.REQUESTED_ADDONS_SHARE

    def test_no_requested_addons_means_empty_lists(self):
        q = run([make_quote("a", add_ons=["agency_repair"])])["selected"]
        assert q["requested_add_ons_matched"] == [] and q["requested_add_ons_missing"] == []

    def test_unknown_requested_addon_is_ignored(self):
        res = run([make_quote("a")], make_profile(requested_add_ons=["flying_car"]))
        assert res["selected"]["requested_add_ons_missing"] == []

    def test_offer_covering_all_requested_addons_ranks_first_even_if_pricier(self):
        # العميل طلب إصلاح وكالة: العرض الذي يوفّرها يتقدم على عرض أرخص بدونها
        profile = make_profile(requested_add_ons=["agency_repair"])
        cheap = make_quote("cheap", premium=300, add_ons=[])
        agency = make_quote("agency", premium=900, add_ons=["agency_repair"])
        res = run([cheap, agency], profile, priority="Budget")
        assert res["selected"]["provider_id"] == "agency"
        assert res["selected"]["covers_requested_add_ons"] is True
        assert by_provider(res)["cheap"]["covers_requested_add_ons"] is False

    def test_requested_addons_unavailable_everywhere_falls_back_to_score(self):
        # لا يوجد عرض يوفّر الإضافة المطلوبة → الترتيب بالدرجة فقط (لا نُفرغ النتائج)
        profile = make_profile(requested_add_ons=["agency_repair"])
        cheap = make_quote("cheap", premium=300, add_ons=[])
        pricey = make_quote("pricey", premium=900, add_ons=[])
        res = run([pricey, cheap], profile, priority="Budget")
        assert res["selected"]["provider_id"] == "cheap"
        assert len(res["ranked"]) == 2

    def test_partial_coverage_of_requested_addons_beats_none(self):
        # لا يوجد عرض يوفّر الإضافتين معاً → العرض الذي يوفّر واحدة يتقدم على الذي لا يوفّر شيئاً
        profile = make_profile(requested_add_ons=["agency_repair", "replacement_car"])
        none = make_quote("none", premium=300, add_ons=[])
        one = make_quote("one", premium=700, add_ons=["agency_repair"])
        res = run([none, one], profile, priority="Budget")
        assert res["selected"]["provider_id"] == "one"
        assert res["selected"]["covers_requested_add_ons"] is False
        assert res["selected"]["requested_add_ons_missing"] == ["replacement_car"]

    # ---------- نطاق التغطية
    def test_scope_is_type_only_when_agent1_sends_no_risk_list(self):
        q = run([make_quote("a")])["selected"]
        assert q["score_breakdown"]["coverage_scope_score"] == 1.0
        assert "coverage_scope" not in q["defaults_used"]

    def test_comprehensive_is_broader_than_tpl_when_no_type_requested(self):
        res = run([make_quote("c", coverage_type="Comprehensive"), make_quote("t")], make_profile(coverage_type=None))
        assert part(res, "c", "coverage_scope_score") == 1.0
        assert part(res, "t", "coverage_scope_score") == pytest.approx(0.4)

    def test_optional_risk_list_refines_scope(self):
        full = ["collision", "theft", "fire", "natural events"]
        res = run([make_quote("full", coverage_type="Comprehensive", coverage_scope=full),
                   make_quote("half", coverage_type="Comprehensive", coverage_scope=["collision", "theft"])],
                  make_profile(coverage_type="Comprehensive"))
        assert part(res, "full", "coverage_scope_score") == pytest.approx(1.0)
        assert part(res, "half", "coverage_scope_score") == pytest.approx(0.75)

    # ---------- الموثوقية / الورش / الرقمي
    @pytest.mark.parametrize("raw,expected", [(0.8, 0.8), (4.0, 0.8), (80, 0.8), (250, 1.0)])
    def test_reliability_scales_are_converted(self, raw, expected):
        res = run([make_quote("a", reliability=raw)])
        assert part(res, "a", "reliability_score") == pytest.approx(expected)

    @pytest.mark.parametrize("value", [None, -1, "high"])
    def test_bad_reliability_is_neutral_and_reported(self, value):
        q = by_provider(run([make_quote("a", reliability=value)]))["a"]
        assert q["score_breakdown"]["reliability_score"] == 0.5 and "reliability" in q["defaults_used"]

    @pytest.mark.parametrize("label,expected", [("واسع جداً", 1.0), ("متوسط", 0.6), ("محدود", 0.3), (0.7, 0.7)])
    def test_workshop_network_labels(self, label, expected):
        res = run([make_quote("a", workshop_network=label)])
        assert part(res, "a", "workshop_score") == pytest.approx(expected)

    @pytest.mark.parametrize("label", ["غير معروف", None, 3])
    def test_unknown_workshop_label_is_neutral_and_reported(self, label):
        q = by_provider(run([make_quote("a", workshop_network=label)]))["a"]
        assert q["score_breakdown"]["workshop_score"] == 0.5 and "workshop_network" in q["defaults_used"]

    def test_digital_score_only_matters_under_digital_priority(self):
        lo, hi = make_quote("lo", digital_score=0.1), make_quote("hi", digital_score=0.9)
        balanced = by_provider(run([lo, hi], priority="Balanced"))
        assert balanced["lo"]["suitability_score"] == balanced["hi"]["suitability_score"]
        digital = by_provider(run([lo, hi], priority="Digital"))
        assert digital["hi"]["suitability_score"] > digital["lo"]["suitability_score"]

    def test_missing_digital_score_reported_only_when_it_counts(self):
        quotes = [make_quote("a", digital_score=None)]
        assert "digital" not in run(quotes, priority="Balanced")["selected"]["defaults_used"]
        assert "digital" in run(quotes, priority="Digital")["selected"]["defaults_used"]

    # ---------- قيمة التغطية مقابل السعر
    def test_same_protection_higher_premium_means_lower_value(self):
        res = run([make_quote("a", premium=400.0), make_quote("b", premium=600.0)])
        assert part(res, "a", "coverage_value_score") == pytest.approx(1.0)
        assert part(res, "b", "coverage_value_score") == pytest.approx(400 / 600, abs=1e-3)

    def test_cheap_but_weak_package_has_lower_value_than_solid_one(self):
        weak = make_quote("weak", premium=300.0, deductible=1500.0, add_ons=[])
        solid = make_quote("solid", premium=330.0, deductible=300.0, add_ons=["roadside_assistance", "windshield_cover", "agency_repair"])
        res = run([weak, solid])
        assert part(res, "weak", "coverage_value_score") < part(res, "solid", "coverage_value_score")
        assert part(res, "solid", "coverage_value_score") == 1.0

    # ---------- الملاءمة لملف السائق والمركبة
    def test_fit_is_neutral_when_no_rule_applies(self):
        q = run([make_quote("a")])["selected"]
        assert q["score_breakdown"]["profile_fit_score"] == 0.5 and "profile_fit" in q["defaults_used"]

    @pytest.mark.parametrize("age,rule_applies", [(20, True), (24, True), (25, False), (40, False), (64, False), (65, True), (70, True)])
    def test_driver_age_rule(self, age, rule_applies):
        q = run([make_quote("a", deductible=200.0)], make_profile(driver_age=age))["selected"]
        assert (q["score_breakdown"]["profile_fit_score"] != 0.5) == rule_applies

    def test_young_driver_prefers_low_deductible(self):
        res = run([make_quote("low", deductible=200.0), make_quote("high", deductible=1400.0)], make_profile(driver_age=20))
        assert part(res, "low", "profile_fit_score") > part(res, "high", "profile_fit_score")

    def test_high_value_vehicle_prefers_broader_cover(self):
        res = run([make_quote("c", coverage_type="Comprehensive"), make_quote("t")],
                  make_profile(coverage_type=None, vehicle_value=150000.0))
        assert part(res, "c", "profile_fit_score") == 1.0
        assert part(res, "t", "profile_fit_score") == pytest.approx(0.4)

    def test_low_value_vehicle_prefers_cheaper_package(self):
        res = run([make_quote("a", premium=400.0), make_quote("b", premium=500.0)], make_profile(vehicle_value=20000.0))
        assert part(res, "a", "profile_fit_score") == pytest.approx(1.0)
        assert part(res, "b", "profile_fit_score") == pytest.approx(0.8)

    def test_new_vehicle_values_agency_repair(self):
        res = run([make_quote("with", add_ons=["agency_repair"]), make_quote("without")], make_profile(vehicle_age=2))
        assert part(res, "with", "profile_fit_score") == 1.0
        assert part(res, "without", "profile_fit_score") == pytest.approx(0.4)

    def test_old_vehicle_prefers_cheaper_package(self):
        res = run([make_quote("a", premium=400.0), make_quote("b", premium=500.0)], make_profile(vehicle_age=12))
        assert part(res, "a", "profile_fit_score") == pytest.approx(1.0)
        assert part(res, "b", "profile_fit_score") == pytest.approx(0.8)

    def test_commercial_use_values_roadside_and_replacement_car(self):
        res = run([make_quote("both", add_ons=["roadside_assistance", "replacement_car"]),
                   make_quote("one", add_ons=["roadside_assistance"]),
                   make_quote("none")], make_profile(purpose_of_use="commercial"))
        assert [part(res, p, "profile_fit_score") for p in ("both", "one", "none")] == [1.0, 0.5, 0.0]

    @pytest.mark.parametrize("purpose", ["personal", "family"])
    def test_personal_and_family_use_add_no_special_rule(self, purpose):
        q = run([make_quote("a")], make_profile(purpose_of_use=purpose))["selected"]
        assert q["score_breakdown"]["profile_fit_score"] == 0.5

    def test_identity_fields_do_not_affect_scores(self):
        a = run([make_quote("a")], make_profile(national_id="1098765432", vehicle_serial="AAA111"))
        b = run([make_quote("a")], make_profile(national_id="2000000001", vehicle_serial="ZZZ999"))
        assert a["selected"]["suitability_score"] == b["selected"]["suitability_score"]

    # ---------- سلامة الحساب
    @pytest.mark.parametrize("priority", PRIORITIES)
    def test_score_equals_weighted_sum_of_breakdown(self, priority):
        """S = Σ (w_i × x_i) كما في التقرير."""
        res = run(five_quotes(), make_profile(driver_age=20), priority)
        for q in res["ranked"]:
            s = sum(res["weights"][c] * q["score_breakdown"][BREAKDOWN_KEY[c]] for c in CRITERIA)
            assert q["suitability_score"] == pytest.approx(s, abs=2e-3)
            assert sum(q["weighted_contributions"].values()) == pytest.approx(q["suitability_score"], abs=2e-3)

    @pytest.mark.parametrize("priority", PRIORITIES)
    def test_scores_stay_between_zero_and_one_even_with_extreme_input(self, priority):
        extreme = [
            make_quote("hi", premium=1.0, deductible=99999.0, reliability=250, digital_score=7, add_ons=["x"] * 20),
            make_quote("lo", premium=1e9, deductible=-5.0, reliability=-1, workshop_network=3, add_ons="windshield_cover"),
        ]
        profile = make_profile(driver_age=18, vehicle_value=1e6, vehicle_age=0, purpose_of_use="commercial")
        for q in run(extreme, profile, priority)["ranked"]:
            assert 0 <= q["suitability_score"] <= 1
            assert all(0 <= v <= 1 for v in q["score_breakdown"].values())

    @pytest.mark.parametrize("priority", PRIORITIES)
    def test_complete_agent1_quote_needs_no_defaults(self, priority):
        """لو وفّر Agent 1 كل الحقول (وانطبقت قاعدة ملاءمة) فلا يوجد أي معيار محايد."""
        for q in run(five_quotes(), make_profile(driver_age=20), priority)["ranked"]:
            assert q["defaults_used"] == [], q["provider_id"]

    def test_minimal_quote_does_not_crash(self):
        res = run([{"premium": 300.0}], make_profile(coverage_type=None))
        q = res["selected"]
        assert 0 <= q["suitability_score"] <= 1
        assert {"deductible", "reliability", "workshop_network", "add_ons", "profile_fit"} <= set(q["defaults_used"])


# ============================================================ 4) الترتيب والاختيار (الخطوات 7-9)
class TestRanking:
    def test_ranked_descending_with_ranks_and_selected_first(self):
        res = run(five_quotes())
        scores = [q["suitability_score"] for q in res["ranked"]]
        assert scores == sorted(scores, reverse=True)
        assert [q["rank"] for q in res["ranked"]] == [1, 2, 3, 4, 5]
        assert res["selected"] is res["ranked"][0]

    def test_five_insurers_are_all_ranked(self):
        res = run(five_quotes())
        assert {q["provider_id"] for q in res["ranked"]} == {"tawuniya", "medgulf", "acig", "rajhi", "provider5"}

    def test_single_quote_is_selected(self):
        assert run([make_quote("only")])["selected"]["provider_id"] == "only"

    def test_identical_quotes_keep_input_order(self):
        res = run([make_quote("first"), make_quote("second")])
        assert [q["provider_id"] for q in res["ranked"]] == ["first", "second"]

    def test_tie_goes_to_higher_reliability(self, monkeypatch):
        tie = {c: 0.0 for c in CRITERIA}
        tie["deductible"] = 1.0  # الدرجة تعتمد على التحمل وحده، فيتعادل العرضان
        monkeypatch.setitem(a2.FULL_PRIORITY_PROFILES, "Tie", tie)
        res = run([make_quote("low", reliability=0.6), make_quote("high", reliability=0.9)], priority="Tie")
        assert res["ranked"][0]["suitability_score"] == res["ranked"][1]["suitability_score"]
        assert res["selected"]["provider_id"] == "high"

    def test_tie_with_equal_reliability_goes_to_cheaper(self, monkeypatch):
        tie = {c: 0.0 for c in CRITERIA}
        tie["deductible"] = 1.0
        monkeypatch.setitem(a2.FULL_PRIORITY_PROFILES, "Tie", tie)
        res = run([make_quote("dear", premium=500.0), make_quote("cheap", premium=450.0)], priority="Tie")
        assert res["selected"]["provider_id"] == "cheap"

    def test_budget_priority_prefers_the_cheaper_offer(self):
        a = make_quote("a", premium=400.0)
        b = make_quote("b", premium=500.0)
        assert run([b, a], priority="Budget")["selected"]["provider_id"] == "a"

    def test_service_priority_prefers_reliability_and_workshops(self):
        cheap_weak = make_quote("cheap", premium=400.0, reliability=0.5, workshop_network="محدود")
        solid = make_quote("solid", premium=500.0, reliability=0.95, workshop_network="واسع جداً")
        assert run([cheap_weak, solid], priority="Service")["selected"]["provider_id"] == "solid"
        assert run([cheap_weak, solid], priority="Budget")["selected"]["provider_id"] == "cheap"

    def test_digital_priority_prefers_better_digital_experience(self):
        plain, slick = make_quote("plain", digital_score=0.2), make_quote("slick", digital_score=0.9)
        assert run([plain, slick], priority="Digital")["selected"]["provider_id"] == "slick"

    def test_unknown_priority_falls_back_to_balanced(self):
        assert run([make_quote("a")], priority="Cheapest")["priority"] == "Balanced"

    def test_priority_is_case_insensitive(self):
        assert run([make_quote("a")], priority="budget")["priority"] == "Budget"

    def test_priority_defaults_to_the_one_in_customer_profile(self):
        assert run([make_quote("a")], make_profile(priority="Service"))["priority"] == "Service"

    def test_explicit_priority_overrides_profile(self):
        assert run([make_quote("a")], make_profile(priority="Service"), priority="Digital")["priority"] == "Digital"

    def test_priority_defaults_to_balanced_when_nowhere_given(self):
        profile = make_profile()
        del profile["priority"]
        assert run([make_quote("a")], profile)["priority"] == "Balanced"

    @pytest.mark.parametrize("priority", ["Budget", "Balanced", "Service"])
    def test_report_scenario_cheapest_offer_does_not_automatically_win(self, priority):
        """Figure 3.16: تعاونية بـ 483 تفوز رغم أن مدغلف (469) و ACIG (428) أرخص والراجحي (507) أغلى."""
        profile = make_profile(driver_age=31, vehicle_value=85000.0, vehicle_age=5, priority=priority)
        res = run(report_quotes(), profile)
        cheapest = min(report_quotes(), key=lambda q: q["premium"])["provider_id"]
        assert res["selected"]["provider_id"] == "tawuniya"
        assert res["selected"]["provider_id"] != cheapest
        assert len(res["ranked"]) == 4

    def test_report_scenario_expensive_offer_loses_on_value(self):
        profile = make_profile(driver_age=31, vehicle_value=85000.0, vehicle_age=5)
        res = run(report_quotes(), profile)
        assert part(res, "rajhi", "coverage_value_score") < part(res, "tawuniya", "coverage_value_score")


# ============================================================ 5) العقد مع Agent 1 (الشكل فقط، بدون تشغيله)
class TestAgent1Contract:
    def test_fixtures_have_exactly_the_agent1_keys(self):
        """حماية للاختبارات نفسها: عروضنا التجريبية بنفس مفاتيح Agent 1 بالضبط."""
        for q in five_quotes():
            assert set(q) == UNIFIED_KEYS

    def test_all_agent1_fields_survive_in_the_output(self):
        res = run(five_quotes())
        originals = {q["provider_id"]: q for q in five_quotes()}
        for entry in res["ranked"]:
            for k in UNIFIED_KEYS:
                assert k in entry
            assert entry["provider_name"] == originals[entry["provider_id"]]["provider_name"]
            assert entry["premium"] == originals[entry["provider_id"]]["premium"]

    def test_inputs_are_not_mutated(self):
        quotes, profile = five_quotes(), make_profile(requested_add_ons=["roadside_assistance"])
        before_q, before_p = copy.deepcopy(quotes), copy.deepcopy(profile)
        run(quotes, profile)
        assert quotes == before_q and profile == before_p

    def test_same_input_same_output(self):
        quotes = five_quotes()
        assert run(quotes) == run(quotes)

    def test_run_from_agent1_output_takes_priority_from_profile(self):
        res = RecommendationAgentV2().run_from_agent1_output(agent1_output())
        assert res["priority"] == "Budget" and res["selected"] is not None
        assert len(res["ranked"]) == 5

    def test_explicit_priority_overrides_agent1_profile(self):
        res = RecommendationAgentV2().run_from_agent1_output(agent1_output(), priority="Service")
        assert res["priority"] == "Service"

    def test_provider_status_is_passed_through_for_agent3(self):
        status = [{"provider_id": "acig", "provider_name": "ACIG", "ok": False, "error_type": "timeout"}]
        res = RecommendationAgentV2().run_from_agent1_output(agent1_output(report_quotes()[:3], provider_status=status))
        assert res["provider_status"] == status

    def test_empty_agent1_output_is_handled(self):
        res = RecommendationAgentV2().run_from_agent1_output({})
        assert res["selected"] is None and res["reason"]

    def test_no_personal_data_in_output(self):
        res = RecommendationAgentV2().run_from_agent1_output(agent1_output())
        text = repr(res)
        assert "1098765432" not in text and "123456789" not in text and "1986-01-01" not in text

    @pytest.mark.parametrize("purpose", ["personal", "commercial", "family"])
    def test_every_purpose_value_from_agent1_works(self, purpose):
        res = run(five_quotes(), make_profile(purpose_of_use=purpose))
        assert res["selected"] is not None

    @pytest.mark.parametrize("raw,expected", [
        ("personal", "personal"), ("family", "family"), ("commercial", "commercial"),
        ("شخصي", "personal"), ("عائلي", "family"), ("تجاري", "commercial"),
        ("racing", None), (None, None),
    ])
    def test_purpose_values_are_understood(self, raw, expected):
        """القيم الثلاث المعتمدة في Agent 1 (PURPOSES) تُفهم، وغيرها يُترك دون قاعدة."""
        assert a2._canon_use(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("TPL", "tpl"), ("Comprehensive", "comprehensive"), ("tpl", "tpl"),
        ("ضد الغير", "tpl"), ("شامل", "comprehensive"), ("FLYING", None), (None, None),
    ])
    def test_coverage_type_values_are_understood(self, raw, expected):
        """القيم التي يرجعها normalize_coverage في Agent 1 (TPL / Comprehensive) وما يقابلها بالعربي."""
        assert a2._canon_coverage_type(raw) == expected

    def test_comprehensive_request(self):
        quotes = [make_quote(p, coverage_type="Comprehensive", premium=1500.0 + i * 100) for i, p in enumerate("abc")]
        res = run(quotes, make_profile(coverage_type="Comprehensive"))
        assert {q["coverage_type"] for q in res["ranked"]} == {"Comprehensive"} and len(res["ranked"]) == 3



# ============================================================ 6) تكامل حقيقي: Agent 1 -> Agent 2
@pytest.fixture
def agent1():
    """يشغّل DataReceiverAgent الحقيقي فوق Mock Insurance API (نفس طريقة test_agent1.py).
    يتخطى نفسه إذا لم تكن وحدات Agent 1 متاحة للاستيراد."""
    httpx = pytest.importorskip("httpx")
    mock_api = pytest.importorskip("mock_insurer_api")
    receiver = pytest.importorskip("agent1_receiver")
    config = pytest.importorskip("insurers_config")

    class FlakyTransport(httpx.AsyncBaseTransport):
        def __init__(self, behaviors=None):
            self.inner = httpx.ASGITransport(app=mock_api.app)
            self.behaviors = behaviors or {}

        async def handle_async_request(self, request):
            behavior = self.behaviors.get(request.url.path)
            if behavior:
                r = behavior(request)
                if r is not None:
                    return r
            return await self.inner.handle_async_request(request)

    def customer_request(**over):
        data = {
            "national_id": "1098765432", "birth_date": "1995-06-15", "vehicle_serial": "123456789",
            "manufacture_year": 2021, "vehicle_value": 85000, "purpose_of_use": "personal",
            "annual_mileage": "medium", "coverage_type": "TPL", "priority": "Budget",
        }
        data.update(over)
        return data

    def timeout(request):
        raise httpx.ReadTimeout("timed out", request=request)

    def run_agent1(data=None, failing_index=None):
        insurers = config.load_insurers(base_url="http://mock")
        behaviors = {}
        if failing_index is not None:
            behaviors[insurers[failing_index]["path"]] = timeout
        agent = receiver.DataReceiverAgent(insurers=insurers, transport=FlakyTransport(behaviors), retry_backoff=0)
        return asyncio.run(agent.run(data or customer_request()))

    return SimpleNamespace(run=run_agent1, request=customer_request, config=config, receiver=receiver)


class TestIntegrationWithAgent1:
    def test_agent1_output_is_recommended_end_to_end(self, agent1):
        out1 = agent1.run()
        res = RecommendationAgentV2().run_from_agent1_output(out1)
        providers = {q["provider_id"] for q in out1["unified_quote_set"]}
        assert res["selected"]["provider_id"] in providers
        assert len(res["ranked"]) == len(out1["unified_quote_set"])
        assert res["rejected"] == []  # شكل retrieved_at الحقيقي يمر من فلتر الحداثة

    @pytest.mark.parametrize("priority", PRIORITIES)
    def test_real_quote_formats_need_no_neutral_defaults(self, agent1, priority):
        """يكشف أي اختلاف في شكل reliability / workshop_network / digital_score / deductible / add_ons
        بين Agent 1 وAgent 2: أي حقل لم يُفهم يظهر هنا في defaults_used.
        نستخدم purpose=commercial لأن قاعدته تنطبق دائماً فلا يبقى profile_fit محايداً."""
        out1 = agent1.run(agent1.request(purpose_of_use="commercial"))
        res = RecommendationAgentV2().run_from_agent1_output(out1, priority=priority)
        for q in res["ranked"]:
            assert q["defaults_used"] == [], q["provider_id"]

    def test_one_failed_insurer_still_gets_a_recommendation(self, agent1):
        out1 = agent1.run(failing_index=0)
        failed = [s["provider_id"] for s in out1["provider_status"] if not s["ok"]]
        res = RecommendationAgentV2().run_from_agent1_output(out1)
        assert len(failed) == 1 and res["selected"] is not None
        assert failed[0] not in {q["provider_id"] for q in res["ranked"]}
        assert res["provider_status"] == out1["provider_status"]

    def test_priority_flows_from_the_customer_request(self, agent1):
        res = RecommendationAgentV2().run_from_agent1_output(agent1.run(agent1.request(priority="Service")))
        assert res["priority"] == "Service"

    def test_comprehensive_request_flows_through(self, agent1):
        res = RecommendationAgentV2().run_from_agent1_output(agent1.run(agent1.request(coverage_type="Comprehensive")))
        assert {q["coverage_type"] for q in res["ranked"]} == {"Comprehensive"}

    def test_requested_addons_flow_through(self, agent1):
        out1 = agent1.run(agent1.request(requested_add_ons=["roadside_assistance"]))
        res = RecommendationAgentV2().run_from_agent1_output(out1)
        for q in res["ranked"]:
            if "roadside_assistance" in q["add_ons"]:
                assert q["requested_add_ons_matched"] == ["roadside_assistance"]
            else:
                assert q["requested_add_ons_missing"] == ["roadside_assistance"]

    def test_addon_and_priority_names_match_agent1(self, agent1):
        assert set(a2.ADD_ON_ALIASES) == set(agent1.config.CANONICAL_ADDONS)
        assert set(FULL_PRIORITY_PROFILES) == set(agent1.receiver.PRIORITIES)
