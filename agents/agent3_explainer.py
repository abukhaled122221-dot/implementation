"""
Agent 3 - Explainer Agent
يبني تفسير بلغة بسيطة لماذا تم اختيار العرض الفائز، ولماذا لم تُختر البدائل.
"""

ADDON_LABELS = {
    "agency_repair": "إصلاح لدى الوكالة",
    "roadside_assistance": "مساعدة على الطريق",
    "replacement_car": "سيارة بديلة",
    "windshield_cover": "تغطية الزجاج الأمامي",
    "gulf_coverage": "تغطية دول الخليج",
}


class ExplainerAgent:
    def run(self, selected: dict, ranked: list[dict]) -> dict:
        if not selected:
            return {"main_reasons": "لا توجد عروض لعرض تفسير لها.", "comparison": []}

        strengths = []
        breakdown = selected["score_breakdown"]

        if breakdown["premium_score"] >= 0.6:
            strengths.append("سعر منافس مقارنة بباقي العروض")
        if breakdown["reliability_score"] >= 0.85:
            strengths.append("موثوقية عالية وسجل مطالبات جيد")
        if breakdown["workshop_score"] >= 0.8:
            strengths.append("شبكة ورش إصلاح واسعة")
        if breakdown["addons_score"] >= 0.6:
            addon_names = ", ".join(ADDON_LABELS.get(a, a) for a in selected["add_ons"])
            strengths.append(f"إضافات مفيدة: {addon_names}")

        main_reasons = (
            f"تم اختيار عرض {selected['provider_name']} بقسط {selected['premium']} ريال سنوياً "
            f"لأنه يحقق أفضل توازن بين السعر والتغطية والموثوقية لملفك الحالي."
        )

        comparison = []
        for alt in ranked[1:4]:  # أفضل 3 بدائل بعد الفائز
            diff = round((selected["suitability_score"] - alt["suitability_score"]) * 100, 1)
            comparison.append({
                "provider_name": alt["provider_name"],
                "premium": alt["premium"],
                "why_not_chosen": f"سجل نقاط أقل بنسبة {diff}% مقارنة بالعرض الموصى به.",
            })

        return {
            "main_reasons": main_reasons,
            "strengths": strengths,
            "comparison": comparison,
        }
