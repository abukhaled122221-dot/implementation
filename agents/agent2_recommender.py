"""
Agent 2 - Recommendation Agent
يقيّم كل عرض حسب معايير موزونة (وفق القسم 3.2.3.2 من التقرير)
S = Σ (w_i × x_i)
"""

DEFAULT_WEIGHTS = {
    "premium": 0.30,          # القسط (أقل = أفضل)
    "coverage_value": 0.20,   # نسبة التغطية للسعر
    "deductible": 0.15,       # التحمل (أقل = أفضل)
    "add_ons": 0.10,          # عدد الإضافات
    "reliability": 0.15,      # موثوقية الشركة
    "workshop_network": 0.10, # اتساع شبكة الورش
    "digital": 0.0,           # التجربة الرقمية (تفعل فقط مع أولوية Digital)
}

# أوزان بديلة حسب أولوية العميل (يختارها المستخدم في الواجهة)
PRIORITY_PROFILES = {
    "Budget": {"premium": 0.55, "coverage_value": 0.10, "deductible": 0.15, "add_ons": 0.05, "reliability": 0.10, "workshop_network": 0.05, "digital": 0.0},
    "Service": {"premium": 0.15, "coverage_value": 0.10, "deductible": 0.10, "add_ons": 0.10, "reliability": 0.35, "workshop_network": 0.20, "digital": 0.0},
    "Digital": {"premium": 0.15, "coverage_value": 0.10, "deductible": 0.10, "add_ons": 0.10, "reliability": 0.10, "workshop_network": 0.05, "digital": 0.40},
    "Balanced": DEFAULT_WEIGHTS,
}

WORKSHOP_SCORE = {"واسع جداً": 1.0, "متوسط": 0.6, "محدود": 0.3}


class RecommendationAgent:
    def run(self, unified_quote_set: list[dict], customer_profile: dict, priority: str = "Balanced") -> dict:
        weights = PRIORITY_PROFILES.get(priority, DEFAULT_WEIGHTS)
        if not unified_quote_set:
            return {"selected": None, "ranked": [], "reason": "لا توجد عروض متاحة"}

        premiums = [q["premium"] for q in unified_quote_set]
        min_p, max_p = min(premiums), max(premiums)

        scored = []
        for q in unified_quote_set:
            # تطبيع كل معيار إلى مقياس 0-1
            premium_score = 1 - ((q["premium"] - min_p) / (max_p - min_p) if max_p != min_p else 0)
            deductible_score = 1 - (q["deductible"] / 1500)
            addons_score = min(len(q["add_ons"]) / 3, 1.0)
            coverage_value_score = premium_score  # تبسيط: نربطها بجودة السعر مقابل التغطية
            reliability_score = q["reliability"]
            workshop_score = WORKSHOP_SCORE.get(q["workshop_network"], 0.5)
            digital_score = q.get("digital_score", 0.5)

            total_score = (
                weights["premium"] * premium_score
                + weights["coverage_value"] * coverage_value_score
                + weights["deductible"] * deductible_score
                + weights["add_ons"] * addons_score
                + weights["reliability"] * reliability_score
                + weights["workshop_network"] * workshop_score
                + weights["digital"] * digital_score
            )

            scored.append({
                **q,
                "suitability_score": round(total_score, 4),
                "score_breakdown": {
                    "premium_score": round(premium_score, 2),
                    "deductible_score": round(deductible_score, 2),
                    "addons_score": round(addons_score, 2),
                    "reliability_score": round(reliability_score, 2),
                    "workshop_score": round(workshop_score, 2),
                },
            })

        ranked = sorted(scored, key=lambda x: x["suitability_score"], reverse=True)
        return {"selected": ranked[0], "ranked": ranked}
