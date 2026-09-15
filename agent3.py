import json
from datetime import datetime

class ExplainerAgent:
    def __init__(self, log_file="recommendation_log.json"):
        self.log_file = log_file

    def _identify_top_criteria(self, breakdown, threshold=0.15):
        """Identify criteria that contributed most to the score.
        We'll look at weighted contributions (weight * normalized score) and pick those above threshold."""
        weighted = {}
        for key in ['premium', 'coverage', 'coverage_to_price', 'deductible', 'addons', 'fit', 'reliability', 'availability']:
            weighted_key = f'weighted_{key}'
            if weighted_key in breakdown:
                weighted[key] = breakdown[weighted_key]
        # Sort by contribution descending
        sorted_items = sorted(weighted.items(), key=lambda x: x[1], reverse=True)
        # Return those with contribution > threshold
        top = [k for k, v in sorted_items if v > threshold]
        return top if top else [sorted_items[0][0]]  # at least return the top one

    def _map_to_plain_language(self, criterion):
        """Map criterion name to plain-language reason."""
        mapping = {
            'premium': 'السعر مناسب (مخفض)',
            'coverage': 'التغطية شاملة ومناسبة',
            'coverage_to_price': 'نسبة التغطية إلى السعر جيدة',
            'deductible': 'مبلغ الخصم منخفض',
            'addons': 'تشمل مزايا إضافية مفيدة',
            'fit': 'ملاءمة جيدة لمركبتك وملفك الشخصي',
            'reliability': 'موثوقية عالية لشركة التأمين',
            'availability': 'التوفر والحداثة (عرض مباشر من الشركة)'
        }
        return mapping.get(criterion, criterion)

    def _generate_explanation(self, recommended_quote, breakdown, all_scored_quotes):
        """Generate explanation in plain language."""
        # Identify why this package won
        top_criteria = self._identify_top_criteria(breakdown)
        reasons_win = [self._map_to_plain_language(c) for c in top_criteria]

        # Find next-best alternative (second highest score)
        sorted_quotes = sorted(all_scored_quotes, key=lambda x: x['score'], reverse=True)
        # The first is the recommended (assuming same ordering)
        # But we need to ensure we exclude the recommended quote itself.
        # We'll match by company or some unique identifier.
        recommended_company = recommended_quote.get('company')
        next_best = None
        for sq in sorted_quotes:
            if sq['quote'].get('company') != recommended_company:
                next_best = sq
                break

        reasons_lose = []
        if next_best:
            # Compare: why the next-best was not chosen
            # We can look at criteria where next-best scored lower
            # For simplicity, we can state that the recommended package scored higher overall.
            # Or we can mention specific criteria where next-best lagged.
            # We'll compute difference in weighted contributions.
            rec_breakdown = breakdown  # we have breakdown for recommended
            next_breakdown = next_best['breakdown']
            # Criteria where next-best weighted contribution is significantly lower
            lose_reasons = []
            for key in ['premium', 'coverage', 'coverage_to_price', 'deductible', 'addons', 'fit', 'reliability', 'availability']:
                wkey = f'weighted_{key}'
                rec_val = rec_breakdown.get(wkey, 0)
                next_val = next_breakdown.get(wkey, 0)
                if rec_val - next_val > 0.05:  # arbitrary threshold
                    lose_reasons.append(self._map_to_plain_language(key))
            if lose_reasons:
                reasons_lose = lose_reasons[:2]  # limit to two
            else:
                reasons_lose = ["النتيجة الإجمالية أعلى للعرض الموصى به"]

        # Build explanation
        explanation = {
            'recommended_option': {
                'company': recommended_quote.get('company'),
                'premium': recommended_quote.get('premium'),
                'coverage_type': recommended_quote.get('coverage_type'),
                'deductible': recommended_quote.get('deductible'),
                'add_ons': recommended_quote.get('add_ons', [])
            },
            'main_reasons': reasons_win,
            'comparison': {
                'vs_next_best': {
                    'company': next_best['quote'].get('company') if next_best else None,
                    'premium': next_best['quote'].get('premium') if next_best else None,
                    'coverage_type': next_best['quote'].get('coverage_type') if next_best else None,
                },
                'reasons_not_chosen': reasons_lose
            },
            'timestamp': datetime.now().isoformat()
        }
        return explanation

    def format_for_display(self, explanation):
        """Format explanation as plain text for display to user."""
        lines = []
        lines.append("=== توصية التأمين ===")
        rec = explanation['recommended_option']
        lines.append(f"الشركة: {rec['company']}")
        lines.append(f"نوع التغطية: {rec['coverage_type']}")
        lines.append(f"السعر السنوي: {rec['premium']} ريال")
        lines.append(f"مبلغ الخصم: {rec['deductible']} ريال")
        lines.append(f"المزايا الإضافية: {', '.join(rec['add_ons']) if rec['add_ons'] else 'لا توجد'}")
        lines.append("")
        lines.append("الأسباب الرئيسية للتوصية:")
        for i, reason in enumerate(explanation['main_reasons'], 1):
            lines.append(f"  {i}. {reason}")
        lines.append("")
        comp = explanation['comparison']
        if comp['vs_next_best']['company']:
            lines.append("مقارنة مع أفضل بديل:")
            lines.append(f"  الشركة: {comp['vs_next_best']['company']}")
            lines.append(f"  السعر: {comp['vs_next_best']['premium']} ريال")
            lines.append(f"  التغطية: {comp['vs_next_best']['coverage_type']}")
            lines.append("  لم يتم الاختيار لأن:")
            for reason in comp['reasons_not_chosen']:
                lines.append(f"    - {reason}")
        else:
            lines.append("لا يوجد بديل مناسب للمقارنة.")
        lines.append("")
        return "\n".join(lines)

    def log_recommendation(self, explanation):
        """Log explanation to a JSON file (simulating database)."""
        try:
            # Read existing logs if file exists
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                logs = []
            logs.append(explanation)
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            print(f"تم تسجيل التوصية في {self.log_file}")
        except Exception as e:
            print(f"فشل تسجيل التوصية: {e}")

    def explain(self, recommended_quote, breakdown, all_scored_quotes):
        """Main interface: generate explanation, format, log, and return display string."""
        explanation = self._generate_explanation(recommended_quote, breakdown, all_scored_quotes)
        display_text = self.format_for_display(explanation)
        self.log_recommendation(explanation)
        return display_text

# Example usage (for testing)
if __name__ == "__main__":
    # Mock data similar to what would come from Agent 2
    recommended_quote = {
        "company": "Tawuniya",
        "premium": 483,
        "coverage_type": "TPL",
        "deductible": 500,
        "add_ons": ["roadside_assistance"],
        "coverage_scope": ["third_party"],
        "provider_reliability": 9.0,
        "availability": True
    }
    breakdown = {
        'premium': 0.6,
        'coverage': 0.5,
        'coverage_to_price': 0.7,
        'deductible': 0.5,
        'addons': 0.3,
        'fit': 0.8,
        'reliability': 0.9,
        'availability': 1.0,
        'weighted_premium': 0.12,
        'weighted_coverage': 0.10,
        'weighted_coverage_to_price': 0.105,
        'weighted_deductible': 0.05,
        'weighted_addons': 0.03,
        'weighted_fit': 0.08,
        'weighted_reliability': 0.09,
        'weighted_availability': 0.05
    }
    # Mock all scored quotes (list of dicts with 'quote' and 'score')
    all_scored_quotes = [
        {'quote': recommended_quote, 'score': 0.825},
        {'quote': {
            "company": "Medgulf",
            "premium": 469,
            "coverage_type": "TPL",
            "deductible": 550,
            "add_ons": [],
            "coverage_scope": ["third_party"],
            "provider_reliability": 7.0,
            "availability": True
        }, 'score': 0.78},
        {'quote': {
            "company": "ACIG",
            "premium": 428,
            "coverage_type": "TPL",
            "deductible": 700,
            "add_ons": [],
            "coverage_scope": ["third_party"],
            "provider_reliability": 6.0,
            "availability": True
        }, 'score': 0.72},
        {'quote': {
            "company": "Takaful Al-Rajhi",
            "premium": 507,
            "coverage_type": "TPL",
            "deductible": 600,
            "add_ons": ["roadside_assistance"],
            "coverage_scope": ["third_party"],
            "provider_reliability": 9.5,
            "availability": True
        }, 'score': 0.80}
    ]

    agent3 = ExplainerAgent()
    output = agent3.explain(recommended_quote, breakdown, all_scored_quotes)
    print(output)