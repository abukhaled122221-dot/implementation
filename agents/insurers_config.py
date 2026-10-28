"""
إعدادات الاتصال بشركات التأمين (Insurance APIs).

تقابل جدول API_Settings في التقرير (القسم 3.6.2):
    Endpoint  -> base_url + path
    AuthKey   -> api_key_for(provider_id)
    Protocol  -> protocol
    Timeout   -> timeout (بالثواني)

الحقول reliability / workshop_network / digital_score هي بيانات تعريفية عن الشركة
(ليست جزءاً من رد الـ API) يحتاجها Agent 2 لاحقاً عند التقييم.

للتحويل إلى APIs حقيقية: غيّر INSURERS_BASE_URL (أو الـ endpoint لكل شركة) ومفاتيح
<PROVIDER>_API_KEY في متغيرات البيئة — ولا يتغير أي كود آخر.
"""

import os
import sqlite3
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "http://127.0.0.1:8001"  # خدمة Mock Insurance API

# الإضافات المعتمدة داخل النظام (الصيغة الموحدة)
CANONICAL_ADDONS = (
    "agency_repair",
    "roadside_assistance",
    "replacement_car",
    "windshield_cover",
    "gulf_coverage",
)

_INSURER_DEFS = [
    {
        "provider_id": "tawuniya",
        "name": "التعاونية للتأمين",
        "adapter": "tawuniya",
        "path": "/tawuniya/quotes",
        "auth_scheme": "x-api-key",
        "protocol": "REST/JSON",
        "reliability": 0.95,
        "workshop_network": "واسع جداً",
        "digital_score": 0.82,
    },
    {
        "provider_id": "rajhi",
        "name": "الراجحي تكافل",
        "adapter": "rajhi",
        "path": "/rajhi/offers",
        "auth_scheme": "bearer",
        "protocol": "REST/JSON",
        "reliability": 0.90,
        "workshop_network": "متوسط",
        "digital_score": 0.96,
    },
    {
        "provider_id": "medgulf",
        "name": "ميدغلف للتأمين",
        "adapter": "medgulf",
        "path": "/medgulf/plans",
        "auth_scheme": "x-api-key",
        "protocol": "REST/JSON",
        "reliability": 0.85,
        "workshop_network": "متوسط",
        "digital_score": 0.88,
    },
    {
        "provider_id": "acig",
        "name": "المجموعة المتحدة للتأمين (ACIG)",
        "adapter": "acig",
        "path": "/acig/quote",
        "auth_scheme": "x-api-key",
        "protocol": "REST/JSON",
        "reliability": 0.78,
        "workshop_network": "محدود",
        "digital_score": 0.78,
    },
]


def api_key_for(provider_id: str) -> str:
    """مفتاح المصادقة لكل شركة (من البيئة، وإلا قيمة تجريبية للتطوير)."""
    return os.getenv(f"{provider_id.upper()}_API_KEY", f"{provider_id}-test-key")


def load_insurers(base_url: str | None = None, timeout: float | None = None) -> list[dict]:
    """يرجع قائمة الشركات المتصل بها مع إعدادات كل واحدة."""
    base = (base_url or os.getenv("INSURERS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    t = timeout if timeout is not None else float(os.getenv("INSURER_TIMEOUT", "5"))
    insurers = []
    for d in _INSURER_DEFS:
        insurers.append({
            **d,
            "base_url": base,
            "timeout": t,
            "api_key": api_key_for(d["provider_id"]),
        })
    return insurers

def load_insurers_from_db(
    base_url: str | None = None,
    timeout: float | None = None,
    include_inactive: bool = False,
) -> list[dict]:
    """Load current provider settings per request so admin edits need no restart."""
    db_path = os.getenv("THIQA_DB_PATH") or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "database", "thiqa.db")
    )
    try:
        uri = "file:" + os.path.abspath(db_path).replace("\\", "/") + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=1)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT p.ProviderId, p.ProviderName, p.IsActive, p.Reliability, p.WorkshopNetwork, p.DigitalScore,
                   a.Endpoint, a.AuthKey, a.AuthScheme, a.Adapter, a.Timeout
            FROM Insurance_Providers p JOIN API_Settings a ON a.ProviderId=p.ProviderId
            ORDER BY p.ProviderId
        """).fetchall()
        conn.close()
        # الرجوع للإعدادات الافتراضية فقط إذا لم تُضبط أي شركة في قاعدة البيانات إطلاقاً.
        # إذا عطّل الأدمن كل الشركات فالنتيجة الصحيحة قائمة فارغة (لا عروض) — لا إعادة تفعيل صامتة.
        if not rows:
            return load_insurers(base_url, timeout)
        if not include_inactive:
            rows = [row for row in rows if row["IsActive"]]

        def number_or(value, default):
            return float(value) if value is not None else default

        providers = []
        for row in rows:
            endpoint = row["Endpoint"]
            parts = urlsplit(endpoint)
            fallback = next((d for d in _INSURER_DEFS if d["provider_id"] == row["ProviderId"]), {})
            providers.append({
                "provider_id": row["ProviderId"], "name": row["ProviderName"],
                "active": bool(row["IsActive"]), "_source": "db",
                "adapter": row["Adapter"], "path": parts.path or fallback.get("path", "/"),
                "base_url": base_url.rstrip("/") if base_url else (f"{parts.scheme}://{parts.netloc}" if parts.scheme else (os.getenv("INSURERS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")),
                "auth_scheme": (row["AuthScheme"] or "x-api-key").lower(),
                "api_key": row["AuthKey"] or api_key_for(row["ProviderId"]),
                "protocol": "REST/JSON", "timeout": timeout if timeout is not None else float(row["Timeout"] or 5),
                "reliability": number_or(row["Reliability"], fallback.get("reliability", 0.5)),
                "workshop_network": row["WorkshopNetwork"] or fallback.get("workshop_network", "متوسط"),
                "digital_score": number_or(row["DigitalScore"], fallback.get("digital_score", 0.5)),
            })
        return providers
    except (sqlite3.Error, OSError):
        return load_insurers(base_url, timeout)


def insurer_defaults() -> list[dict]:
    """Return built-in definitions with current environment endpoint/key defaults."""
    return load_insurers()
