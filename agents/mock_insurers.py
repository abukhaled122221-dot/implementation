"""
Mock Insurer 'APIs' — يحاكي استجابات شركات التأمين الحقيقية.
لاحقاً، كل دالة هنا ممكن تتحول لاستدعاء requests.get() لـ API حقيقي
بدون ما تتغير بقية الكود (Agent 1 يتعامل مع نفس الشكل الموحد).
"""

import random

# بيانات ثابتة لكل شركة تأمين (تستخدم لحساب سعر واقعي تقريبي)
INSURERS = [
    {"provider_id": "tawuniya", "name": "التعاونية للتأمين", "base_rate": 1.00, "reliability": 0.95, "workshop_network": "واسع جداً", "digital_score": 0.82},
    {"provider_id": "rajhi", "name": "الراجحي تكافل", "base_rate": 1.05, "reliability": 0.90, "workshop_network": "متوسط", "digital_score": 0.96},
    {"provider_id": "medgulf", "name": "ميدغلف للتأمين", "base_rate": 0.97, "reliability": 0.85, "workshop_network": "متوسط", "digital_score": 0.88},
    {"provider_id": "acig", "name": "المجموعة المتحدة للتأمين (ACIG)", "base_rate": 0.89, "reliability": 0.78, "workshop_network": "محدود", "digital_score": 0.78},
]


def _estimate_base_premium(vehicle_value: float, driver_age: int, coverage_type: str) -> float:
    """معادلة تقريبية بسيطة لتسعير القسط الأساسي (وهمية لأغراض العرض فقط)."""
    premium = vehicle_value * 0.02  # نسبة أساسية من قيمة المركبة

    # مخاطرة السائق حسب العمر
    if driver_age < 25:
        premium *= 1.4
    elif driver_age < 35:
        premium *= 1.1
    else:
        premium *= 1.0

    # نوع التغطية
    if coverage_type.lower() in ("comprehensive", "شامل"):
        premium *= 2.2
    else:  # TPL / ضد الغير
        premium *= 1.0

    return max(premium, 300)  # حد أدنى منطقي


def fetch_live_quotes(driver_age: int, vehicle_value: float, coverage_type: str) -> list[dict]:
    """
    يحاكي Agent 1 وهو يستعلم كل شركات التأمين بالتوازي.
    يرجع قائمة عروض بصيغة موحدة (Unified Quote Set) — نفس فكرة التقرير القسم 3.3.
    """
    base = _estimate_base_premium(vehicle_value, driver_age, coverage_type)
    quotes = []

    for insurer in INSURERS:
        variance = random.uniform(0.95, 1.08)
        premium = round(base * insurer["base_rate"] * variance, 2)
        deductible = round(random.choice([500, 750, 1000, 1500]), 2)
        add_ons = random.sample(
            ["agency_repair", "roadside_assistance", "replacement_car", "windshield_cover", "gulf_coverage"],
            k=random.randint(1, 3),
        )

        quotes.append({
            "quote_id": f"{insurer['provider_id']}_{random.randint(1000, 9999)}",
            "provider_id": insurer["provider_id"],
            "provider_name": insurer["name"],
            "premium": premium,
            "coverage_type": coverage_type,
            "deductible": deductible,
            "add_ons": add_ons,
            "reliability": insurer["reliability"],
            "workshop_network": insurer["workshop_network"],
            "digital_score": insurer["digital_score"],
        })

    return quotes
