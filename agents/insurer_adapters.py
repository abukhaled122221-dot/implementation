"""
محوّلات شركات التأمين (Adapters).

كل شركة لها صيغة طلب وصيغة رد مختلفة، وكل Adapter فيه دالتان:
    build_payload(profile)      -> صيغة الطلب التي تفهمها الشركة   (الخطوة 3 في Agent 1)
    normalize(raw_json, insurer) -> قائمة عروض بالصيغة الموحدة       (الخطوة 6 في Agent 1)

الصيغة الموحدة لكل عرض (Unified Quote):
    quote_id, provider_id, provider_name, premium (ريال), coverage_type ("TPL"|"Comprehensive"),
    deductible (ريال), add_ons (قائمة رموز معتمدة), reliability, workshop_network,
    digital_score, retrieved_at
"""

from datetime import datetime, timezone

from insurers_config import CANONICAL_ADDONS


class InvalidInsurerResponse(Exception):
    """رد الشركة غير مطابق للشكل المتوقع (حقول ناقصة / بنية خاطئة)."""


# ----------------------------------------------------------------------------- أدوات مساعدة
_COVERAGE_MAP = {
    "tpl": "TPL",
    "third_party": "TPL",
    "third-party": "TPL",
    "thirdparty": "TPL",
    "ضد الغير": "TPL",
    "comp": "Comprehensive",
    "comprehensive": "Comprehensive",
    "شامل": "Comprehensive",
    "تأمين شامل": "Comprehensive",
}


def normalize_coverage(value) -> str | None:
    """يوحّد أسماء أنواع التغطية المختلفة إلى TPL / Comprehensive (أو None لو غير معروف)."""
    if value is None:
        return None
    k = str(value).strip().lower()
    return _COVERAGE_MAP.get(k) or _COVERAGE_MAP.get(k.replace(" ", "_"))


def _to_number(value) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    n = float(value)
    if n != n or n in (float("inf"), float("-inf")):
        raise ValueError("not finite")
    return n


def _normalize_addons(raw) -> list[str]:
    """يقبل قائمة أو نص مفصول بفواصل، ويُبقي فقط الإضافات المعتمدة."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [x for x in raw.split(",")]
    out = []
    for item in raw:
        code = str(item).strip().lower()
        if code in CANONICAL_ADDONS and code not in out:
            out.append(code)
    return out


def _unify(
    insurer: dict,
    raw_id,
    coverage,
    premium,
    deductible,
    add_ons,
    plan_name=None,
    plan_description=None,
) -> dict:
    """يبني عرضاً موحداً، ويرفع ValueError لو القيم غير منطقية."""
    cov = normalize_coverage(coverage)
    if cov is None:
        raise ValueError(f"unknown coverage type: {coverage!r}")
    premium = _to_number(premium)
    deductible = _to_number(deductible)
    if premium <= 0:
        raise ValueError("premium must be positive")
    if deductible < 0:
        raise ValueError("deductible must be >= 0")
    quote = {
        "quote_id": f"{insurer['provider_id']}_{raw_id}",
        "provider_id": insurer["provider_id"],
        "provider_name": insurer["name"],
        "premium": round(premium, 2),
        "coverage_type": cov,
        "deductible": round(deductible, 2),
        "add_ons": _normalize_addons(add_ons),
        "reliability": insurer["reliability"],
        "workshop_network": insurer["workshop_network"],
        "digital_score": insurer["digital_score"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if plan_name: quote["plan_name"] = str(plan_name)
    if plan_description: quote["plan_description"] = str(plan_description)
    return quote


def _run_items(items, insurer, extract) -> tuple[list[dict], int]:
    """يمرّ على عناصر الرد؛ العنصر التالف يُتجاوز ويُحسب في skipped ولا يوقف الباقي."""
    if not isinstance(items, list):
        raise InvalidInsurerResponse("حقل العروض ليس قائمة")
    quotes, skipped = [], 0
    for item in items:
        try:
            quotes.append(_unify(insurer, *extract(item)))
        except (KeyError, TypeError, ValueError, AttributeError):
            skipped += 1
    return quotes, skipped


def _dig(obj, *keys):
    """وصول آمن لحقول متداخلة؛ يرفع InvalidInsurerResponse لو الحقل غير موجود."""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            raise InvalidInsurerResponse(f"الحقل المتوقع غير موجود: {'.'.join(keys)}")
        cur = cur[k]
    return cur


# ----------------------------------------------------------------------------- التعاونية
def _tawuniya_payload(p: dict) -> dict:
    return {
        "national_id": p["national_id"],
        "birth_date": p["birth_date"],
        "vehicle": {
            "serial": p["vehicle_serial"],
            "manufacture_year": p["manufacture_year"],
            "value": p["vehicle_value"],
        },
        "coverage": "TPL" if p["coverage_type"] == "TPL" else "COMP",
        "usage": p["purpose_of_use"],
        "annual_mileage": p["annual_mileage"],
        **{k: p[k] for k in ("city", "gender", "has_accidents", "cars_count")},
    }


def _tawuniya_normalize(raw: dict, insurer: dict):
    packages = _dig(raw, "packages")
    return _run_items(
        packages, insurer,
        lambda x: (x["package_id"], x["coverage"], x["premium_sar"], x["deductible_sar"], x.get("add_ons"), x.get("plan_name"), x.get("plan_description")),
    )


# ----------------------------------------------------------------------------- الراجحي تكافل
_RAJHI_USE = {"personal": "PRIVATE", "commercial": "COMMERCIAL", "family": "FAMILY"}


def _rajhi_payload(p: dict) -> dict:
    return {
        "customer": {"id_number": p["national_id"], "dob": p["birth_date"]},
        "car": {
            "sequence_no": p["vehicle_serial"],
            "model_year": p["manufacture_year"],
            "market_value": p["vehicle_value"],
        },
        "product": "THIRD_PARTY" if p["coverage_type"] == "TPL" else "COMPREHENSIVE",
        "use": _RAJHI_USE.get(p["purpose_of_use"], "PRIVATE"),
        "risk": {k: p[k] for k in ("city", "gender", "has_accidents", "cars_count")},
        "annual_mileage": p["annual_mileage"],
    }


def _rajhi_normalize(raw: dict, insurer: dict):
    offers = _dig(raw, "data", "offers")

    def extract(x):
        price = x["price"]
        if price.get("currency", "SAR") != "SAR":
            raise ValueError("unsupported currency")
        return (x["id"], x["type"], price["amount"], x["excess"], x.get("extras"), x.get("name"), x.get("description"))

    return _run_items(offers, insurer, extract)


# ----------------------------------------------------------------------------- ميدغلف
def _medgulf_payload(p: dict) -> dict:
    return {
        "idNo": p["national_id"],
        "birthDate": p["birth_date"],
        "chassis": p["vehicle_serial"],
        "year": p["manufacture_year"],
        "value": p["vehicle_value"],
        "plan": "ضد الغير" if p["coverage_type"] == "TPL" else "شامل",
        "purpose": p["purpose_of_use"],
        "mileage": p["annual_mileage"],
        "city": p["city"], "gender": p["gender"],
        "has_accidents": p["has_accidents"], "cars_count": p["cars_count"],
    }


def _medgulf_normalize(raw: dict, insurer: dict):
    result = _dig(raw, "result")
    # ميدغلف ترجع الأرقام كنصوص ("469.00") والإضافات كنص مفصول بفواصل
    return _run_items(
        result, insurer,
        lambda x: (x["ref"], x["plan"], x["annual_cost"], x["deductible"], x.get("options"), x.get("name"), x.get("description")),
    )


# ----------------------------------------------------------------------------- ACIG
def _acig_payload(p: dict) -> dict:
    return {
        "insured_id": p["national_id"],
        "age": p["driver_age"],
        "vehicle_serial": p["vehicle_serial"],
        "manufacture_year": p["manufacture_year"],
        "vehicle_value": p["vehicle_value"],
        "cover_type": "TPL" if p["coverage_type"] == "TPL" else "COMPREHENSIVE",
        "usage": p["purpose_of_use"],
        "annual_mileage": p["annual_mileage"],
        "city": p["city"], "gender": p["gender"],
        "has_accidents": p["has_accidents"], "cars_count": p["cars_count"],
    }


def _acig_normalize(raw: dict, insurer: dict):
    quotes = _dig(raw, "quotes")
    # ACIG ترجع القسط بالهللات (42800 = 428.00 ريال)
    return _run_items(
        quotes, insurer,
        lambda x: (x["quote_ref"], x["product"], _to_number(x["premium_halalas"]) / 100, x["co_pay"], x.get("addons"), x.get("name"), x.get("description")),
    )


ADAPTERS = {
    "tawuniya": {"build_payload": _tawuniya_payload, "normalize": _tawuniya_normalize},
    "rajhi": {"build_payload": _rajhi_payload, "normalize": _rajhi_normalize},
    "medgulf": {"build_payload": _medgulf_payload, "normalize": _medgulf_normalize},
    "acig": {"build_payload": _acig_payload, "normalize": _acig_normalize},
}
