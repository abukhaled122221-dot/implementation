"""
Agent 3 - Explainer Agent
يبني تفسير بلغة بسيطة لماذا تم اختيار العرض الفائز، ولماذا لم تُختر البدائل.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

# Mapping of technical criteria to plain language reasons in Arabic
CRITERION_EXPLANATIONS = {
    "premium": {
        "high": "قسط منخفض مقارنة بالعروض الأخرى",
        "low": "قسط أعلى من بعض العروض المنافسة",
        "neutral": "قسط متوسط مقارنة بالعروض الأخرى"
    },
    "coverage_scope": {
        "high": "تغطية شاملة للمخاطر الأساسية",
        "low": "تغطية أساسية قد لا تشمل بعض المخاطر",
        "neutral": "تغطية متوسطة للمخاطر"
    },
    "coverage_value": {
        "high": "قيمة جيدة مقابل السعر المدفوع",
        "low": "قيمة أقل مقابل السعر مقارنة ببعض العروض",
        "neutral": "قيمة متوسطة مقابل السعر"
    },
    "deductible": {
        "high": "تحمل منخفض يقلل التكلفة عند الحوادث",
        "low": "تحمل مرتفع قد يزيد التكلفة عند الحوادث",
        "neutral": "تحمل متوسط"
    },
    "add_ons": {
        "high": "إضافات متنوعة تزيد من قيمة الوثيقة",
        "low": "إضافات أساسية فقط",
        "neutral": "عدد متوسط من الإضافات"
    },
    "profile_fit": {
        "high": "ملائم جداً لملف السائق والمركبة",
        "low": "قد لا يكون الملاءمة مثالية لملفك",
        "neutral": "ملاءمة معقولة لملف السائق والمركبة"
    },
    "reliability": {
        "high": "شركة موثوقة بسجل مطالبات جيد",
        "low": "موثوقية الشركة قد تكون أقل من المنافسين",
        "neutral": "موثوقية متوسطة للشركة"
    },
    "workshop_network": {
        "high": "شبكة ورش إصلاح واسعة ومتنوعة",
        "low": "شبكة ورش إصلاح محدودة",
        "neutral": "شبكة ورش إصلاح متوسطة"
    },
    "digital": {
        "high": "تجربة رقمية متطورة وخدمات إلكترونية",
        "low": "تجربة رقمية أساسية",
        "neutral": "تجربة رقمية متوسطة"
    }
}

# ADDON_LABELS for translating add-on keys to Arabic
ADDON_LABELS = {
    "agency_repair": "إصلاح لدى الوكالة",
    "roadside_assistance": "مساعدة على الطريق",
    "replacement_car": "سيارة بديلة",
    "windshield_cover": "تغطية الزجاج الأمامي",
    "gulf_coverage": "تغطية دول الخليج",
}


class ExplainerAgent:
    def __init__(self, db_path: str = "../database/thiqa.db"):
        default_path = os.path.join(
            os.path.dirname(__file__), "..", "database", "thiqa.db"
        )
        configured_path = os.getenv("THIQA_DB_PATH")
        if db_path == "../database/thiqa.db":
            db_path = configured_path or default_path
        self.db_path = os.path.abspath(db_path)

    def _get_db_connection(self):
        """Create a database connection."""
        return sqlite3.connect(self.db_path)

    def _log_explanation(self, rec_id: int, main_reasons: str, criteria_breakdown: str, comparison_text: str) -> None:
        """Log the explanation to the database."""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO Explanations (RecId, MainReasons, CriteriaBreakdown, ComparisonText)
                VALUES (?, ?, ?, ?)
                """,
                (rec_id, main_reasons, criteria_breakdown, comparison_text)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            # Log error but don't break the flow - explanation is still returned to user
            print(f"Warning: Failed to log explanation to database: {e}")

    def _assess_criterion_level(self, score: float) -> str:
        """Assess if a criterion score is high, low, or neutral."""
        if score >= 0.7:
            return "high"
        elif score <= 0.3:
            return "low"
        else:
            return "neutral"

    def _get_top_criteria(self, weighted_contributions: Dict[str, float], top_n: int = 3) -> List[tuple]:
        """Get the top N criteria by weighted contribution."""
        sorted_items = sorted(weighted_contributions.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:top_n]

    def _get_score_breakdown_key(self, criterion_key: str) -> str:
        """Map criterion key to corresponding score_breakdown key."""
        # Map from weighted_contributions keys to score_breakdown keys
        mapping = {
            "premium": "premium_score",
            "coverage_scope": "coverage_scope_score",
            "coverage_value": "coverage_value_score",
            "deductible": "deductible_score",
            "add_ons": "addons_score",
            "profile_fit": "profile_fit_score",
            "reliability": "reliability_score",
            "workshop_network": "workshop_score",
            "digital": "digital_score"
        }
        return mapping.get(criterion_key, criterion_key + "_score")

    def _generate_criteria_explanations(self, score_breakdown: Dict[str, float], weighted_contributions: Dict[str, float]) -> List[str]:
        """Generate plain language explanations for why the package was chosen."""
        explanations = []

        # Get top contributing criteria
        top_criteria = self._get_top_criteria(weighted_contributions, 3)

        for criterion, contribution in top_criteria:
            # Get the corresponding score_breakdown key
            score_key = self._get_score_breakdown_key(criterion)

            if score_key in score_breakdown:
                score = score_breakdown[score_key]
                level = self._assess_criterion_level(score)

                if criterion in CRITERION_EXPLANATIONS and level in CRITERION_EXPLANATIONS[criterion]:
                    explanations.append(CRITERION_EXPLANATIONS[criterion][level])
                else:
                    # Fallback generic explanation
                    explanations.append(f"{criterion}: مستوى مناسب ({score:.2f})")

        return explanations

    def _generate_comparison_text(self, selected: Dict[str, Any], ranked: List[Dict[str, Any]]) -> str:
        """Generate comparison text with next-best alternatives."""
        if not selected or len(ranked) < 2:
            return "لا توجد بدائل كافية للمقارنة."

        comparison_parts = []
        comparison_parts.append(f"العرض الموصى به: {selected['provider_name']} بقسط {selected['premium']} ريال.")

        # Compare with top 2 alternatives
        for i, alt in enumerate(ranked[1:3], 2):  # ranked[1] and ranked[2] are 2nd and 3rd best
            if alt:
                score_diff = round((selected['suitability_score'] - alt['suitability_score']) * 100, 1)
                cost_diff = alt['premium'] - selected['premium']

                if cost_diff > 0:
                    cost_text = f"أرخص بـ {cost_diff:.0f} ريال"
                elif cost_diff < 0:
                    cost_text = f"أغلى بـ {abs(cost_diff):.0f} ريال"
                else:
                    cost_text = "نفس السعر"

                comparison_parts.append(
                    f"البديل {i}: {alt['provider_name']} بقسط {alt['premium']} ريال "
                    f"(أقل ملاءمة بنسبة {score_diff}%، {cost_text})"
                )

        return " | ".join(comparison_parts)

    def run(self, selected: dict, ranked: list[dict], rec_id: Optional[int] = None) -> dict:
        if not selected:
            return {
                "main_reasons": "لا توجد عروض لعرض تفسير لها.",
                "strengths": [],
                "comparison": [],
                "criteria_explanations": [],
                "comparison_array": []
            }

        # Extract relevant data from selected package
        breakdown = selected.get("score_breakdown", {})
        weighted_contributions = selected.get("weighted_contributions", {})

        # Generate main reasons
        plan = f" ({selected['plan_name']})" if selected.get('plan_name') else ""
        main_reasons = (
            f"تم اختيار عرض {selected['provider_name']}{plan} بقسط {selected['premium']} ريال سنوياً "
            f"لأنه يحقق أفضل توازن بين السعر والتغطية والموثوقية لملفك الحالي."
        )

        # Generate criteria-based explanations (why this package won)
        criteria_explanations = self._generate_criteria_explanations(breakdown, weighted_contributions)
        if selected.get("requested_add_ons_matched"):
            labels = ", ".join(ADDON_LABELS.get(a, a) for a in selected["requested_add_ons_matched"])
            criteria_explanations.append(f"يتضمن الإضافات المطلوبة: {labels}.")
        if selected.get("requested_add_ons_missing"):
            labels = ", ".join(ADDON_LABELS.get(a, a) for a in selected["requested_add_ons_missing"])
            criteria_explanations.append(f"لا يتضمن الإضافات المطلوبة: {labels}.")

        # Generate traditional strengths (keeping backward compatibility)
        strengths = []
        if breakdown.get("premium_score", 0) >= 0.6:
            strengths.append("سعر منافس مقارنة بباقي العروض")
        if breakdown.get("reliability_score", 0) >= 0.85:
            strengths.append("موثوقية عالية وسجل مطالبات جيد")
        if breakdown.get("workshop_score", 0) >= 0.8:
            strengths.append("شبكة ورش إصلاح واسعة")
        if breakdown.get("addons_score", 0) >= 0.6:
            addon_names = ", ".join(ADDON_LABELS.get(a, a) for a in selected.get("add_ons", []))
            strengths.append(f"إضافات مفيدة: {addon_names}")

        # Generate comparison with alternatives
        comparison_text = self._generate_comparison_text(selected, ranked)

        # Prepare data for database logging
        criteria_breakdown_json = json.dumps({
            "score_breakdown": breakdown,
            "weighted_contributions": weighted_contributions,
            "top_criteria": self._get_top_criteria(weighted_contributions, 3)
        }, ensure_ascii=False, indent=2)

        # Log to database if rec_id is provided
        if rec_id is not None:
            self._log_explanation(rec_id, main_reasons, criteria_breakdown_json, comparison_text)

        return {
            "main_reasons": main_reasons,
            "strengths": strengths,
            "criteria_explanations": criteria_explanations,
            "comparison": comparison_text,
            # For backward compatibility with existing UI that expects array format
            "comparison_array": [
                {
                    "provider_name": alt["provider_name"],
                    "premium": alt["premium"],
                    "why_not_chosen": f"سجل نقاط أقل بنسبة {round((selected['suitability_score'] - alt['suitability_score']) * 100, 1)}% مقارنة بالعرض الموصى به."
                }
                for alt in ranked[1:4]  # أفضل 3 بدائل بعد الفائز
            ] if len(ranked) > 1 else []
        }