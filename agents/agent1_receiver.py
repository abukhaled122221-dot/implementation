"""
Agent 1 - Data Receiver and Retrieval Agent  (القسم 3.2.3.1 في التقرير)

الخطوات الداخلية (كما في Figure 3.4):
    1. استلام بيانات العميل والمركبة
    2. التحقق منها وهيكلتها                      -> validate_customer_data()
    3. بناء طلب API خاص بكل شركة                 -> adapter.build_payload()
    4. إرسال الطلبات بالتوازي لكل الشركات         -> _fetch_all()  (asyncio.gather)
    5. استقبال ردود JSON الحية                    -> _query_insurer()
    6. توحيد العروض في صيغة واحدة                 -> adapter.normalize()
    7. تمرير المجموعة الموحدة إلى Agent 2

لا يتخذ هذا الوكيل أي قرار: يجمع ويتحقق ويوحّد فقط.

معالجة الأخطاء (متطلب Reliability في التقرير):
    فشل شركة واحدة (timeout / 5xx / مفتاح خاطئ / رد تالف) لا يوقف النظام؛ تُسجَّل
    حالتها في provider_status ويكمل الوكيل بباقي الشركات. فقط لو فشلت الكل أو لم
    يرجع أي عرض صالح يُرفع NoOffersAvailable.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date

import httpx

from insurer_adapters import ADAPTERS, InvalidInsurerResponse, normalize_coverage
from insurers_config import CANONICAL_ADDONS, load_insurers_from_db

logger = logging.getLogger("thiqa.agent1")

PURPOSES = ("personal", "commercial", "family")
MILEAGES = ("low", "medium", "high")
PRIORITIES = ("Budget", "Service", "Digital", "Balanced")


# ----------------------------------------------------------------------------- الاستثناءات
class InvalidCustomerData(ValueError):
    """بيانات العميل غير صالحة. errors = [{field, message}, ...]"""

    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("; ".join(e["message"] for e in errors))


class NoOffersAvailable(RuntimeError):
    """لم يرجع أي عرض صالح من أي شركة. provider_status فيه سبب فشل كل شركة."""

    def __init__(self, provider_status: list[dict]):
        self.provider_status = provider_status
        super().__init__("لم نتمكن من الحصول على عروض من أي شركة تأمين حالياً")


# ----------------------------------------------------------------------------- الخطوة 1-2: التحقق
def validate_customer_data(data: dict, today: date | None = None) -> dict:
    """
    يتحقق من بيانات العميل والمركبة ويرجعها بصيغة منظمة.
    يجمع كل الأخطاء دفعة واحدة (لا يتوقف عند أول خطأ).
    """
    today = today or date.today()
    errors: list[dict] = []

    def err(field_name: str, message: str):
        errors.append({"field": field_name, "message": message})

    if not isinstance(data, dict):
        raise InvalidCustomerData([{"field": "_", "message": "صيغة الطلب غير صحيحة"}])

    # --- رقم الهوية / الإقامة: 10 أرقام تبدأ بـ 1 (مواطن) أو 2 (مقيم)
    national_id = str(data.get("national_id", "")).strip()
    if not re.fullmatch(r"[12]\d{9}", national_id):
        err("national_id", "رقم الهوية/الإقامة يجب أن يكون 10 أرقام ويبدأ بـ 1 أو 2")

    # --- تاريخ الميلاد -> العمر
    birth_date, driver_age = None, None
    try:
        birth = date.fromisoformat(str(data.get("birth_date", "")).strip())
        driver_age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        birth_date = birth.isoformat()
        if birth > today or driver_age < 18 or driver_age > 90:
            err("birth_date", "عمر السائق يجب أن يكون بين 18 و 90 سنة")
    except ValueError:
        err("birth_date", "تاريخ الميلاد غير صحيح")

    # --- بيانات المركبة
    serial = str(data.get("vehicle_serial", "")).strip()
    if not re.fullmatch(r"[A-Za-z0-9]{6,17}", serial):
        err("vehicle_serial", "الرقم التسلسلي للمركبة غير صحيح")

    manufacture_year = None
    try:
        manufacture_year = int(data.get("manufacture_year"))
        if not (1990 <= manufacture_year <= today.year + 1):
            err("manufacture_year", f"سنة الصنع يجب أن تكون بين 1990 و {today.year + 1}")
    except (TypeError, ValueError):
        err("manufacture_year", "سنة الصنع غير صحيحة")

    vehicle_value = None
    try:
        vehicle_value = float(data.get("vehicle_value"))
        if not (5_000 <= vehicle_value <= 2_000_000):
            err("vehicle_value", "قيمة المركبة يجب أن تكون بين 5,000 و 2,000,000 ريال")
    except (TypeError, ValueError):
        err("vehicle_value", "قيمة المركبة غير صحيحة")

    purpose = str(data.get("purpose_of_use") or "personal").strip().lower()
    if purpose not in PURPOSES:
        err("purpose_of_use", "غرض الاستخدام غير معروف")

    mileage = str(data.get("annual_mileage") or "medium").strip().lower()
    if mileage not in MILEAGES:
        err("annual_mileage", "فئة الممشى السنوي غير معروفة")

    coverage = normalize_coverage(data.get("coverage_type"))
    if coverage is None:
        err("coverage_type", "نوع التغطية يجب أن يكون TPL أو Comprehensive")

    priority = str(data.get("priority") or "Balanced").strip()
    if priority not in PRIORITIES:
        err("priority", "الأولوية غير معروفة")

    addons_raw = data.get("requested_add_ons") or []
    if not isinstance(addons_raw, list) or any(a not in CANONICAL_ADDONS for a in addons_raw):
        err("requested_add_ons", "قائمة الإضافات المطلوبة غير صحيحة")
        addons_raw = []

    risk_defaults = {"city": "riyadh", "gender": "male", "has_accidents": "no", "cars_count": "single"}
    risk = {}
    valid_risk = {
        "city": {"riyadh", "jeddah", "eastern", "other"},
        "gender": {"male", "female"},
        "has_accidents": {"yes", "no"},
        "cars_count": {"single", "multiple"},
    }
    for key, default in risk_defaults.items():
        value = str(data.get(key) or default).strip().lower()
        if key == "city" and value not in valid_risk[key]:
            value = "other"
        elif value not in valid_risk[key]:
            err(key, f"قيمة {key} غير صحيحة")
        risk[key] = value

    if errors:
        raise InvalidCustomerData(errors)

    return {
        "national_id": national_id,
        "birth_date": birth_date,
        "driver_age": driver_age,
        "vehicle_serial": serial,
        "manufacture_year": manufacture_year,
        "vehicle_age": max(today.year - manufacture_year, 0),
        "vehicle_value": vehicle_value,
        "purpose_of_use": purpose,
        "annual_mileage": mileage,
        "coverage_type": coverage,
        "requested_add_ons": list(addons_raw),
        "priority": priority,
        **risk,
    }


# ----------------------------------------------------------------------------- نتيجة كل شركة
@dataclass
class InsurerResult:
    provider_id: str
    provider_name: str
    ok: bool = False
    quotes: list = field(default_factory=list)
    error_type: str | None = None   # timeout | connection | auth | http_4xx | http_5xx | invalid_response | no_offers | unexpected
    error_message: str | None = None
    attempts: int = 0
    skipped_items: int = 0
    latency_ms: int = 0

    def to_status(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "ok": self.ok,
            "offers_count": len(self.quotes),
            "skipped_items": self.skipped_items,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
        }


def _auth_headers(insurer: dict) -> dict:
    if insurer["auth_scheme"] == "bearer":
        return {"Authorization": f"Bearer {insurer['api_key']}"}
    return {"X-API-Key": insurer["api_key"]}


# ----------------------------------------------------------------------------- الوكيل
class DataReceiverAgent:
    def __init__(
        self,
        insurers: list[dict] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 2,
        retry_backoff: float = 0.3,
    ):
        """
        insurers      : إعدادات الشركات (الافتراضي من insurers_config.load_insurers()).
        transport     : لحقن transport مخصص (يُستخدم في الاختبارات فقط).
        max_attempts  : عدد المحاولات لكل شركة عند الأعطال السريعة (انقطاع اتصال / 5xx / 429). الـ timeout لا يُعاد.
        retry_backoff : الانتظار بين المحاولات بالثواني.
        """
        self._configured_insurers = insurers
        self.insurers = insurers
        self._transport = transport
        self.max_attempts = max(1, max_attempts)
        self.retry_backoff = retry_backoff

    async def run(self, customer_data: dict) -> dict:
        """Keep risk inputs request-scoped to prevent concurrent customers leaking risk."""
        # 1-2. استلام + تحقق + هيكلة
        profile = validate_customer_data(customer_data)

        # 3-6. بناء الطلبات، إرسالها بالتوازي، استقبال الردود، توحيدها
        if self._configured_insurers is None:
            self.insurers = load_insurers_from_db()
        results = await self._fetch_all(profile)
        provider_status = [r.to_status() for r in results]
        quotes = [q for r in results for q in r.quotes]

        failed = [s["provider_id"] for s in provider_status if not s["ok"]]
        if failed:
            logger.warning("Agent1: insurers failed or returned nothing: %s", failed)
        if not quotes:
            raise NoOffersAvailable(provider_status)

        # 7. تمرير المجموعة الموحدة (إلى Agent 2)
        return {
            "customer_profile": profile,
            "unified_quote_set": quotes,
            "provider_status": provider_status,
        }

    # ------------------------------------------------------------------ الخطوة 4
    async def _fetch_all(self, profile: dict) -> list[InsurerResult]:
        async with httpx.AsyncClient(transport=self._transport) as client:
            return list(await asyncio.gather(*(self._query_insurer(client, ins, profile) for ins in self.insurers)))

    # ------------------------------------------------------------------ الخطوات 3 + 5 + 6 لشركة واحدة
    async def _query_insurer(self, client: httpx.AsyncClient, insurer: dict, profile: dict) -> InsurerResult:
        """لا يرفع استثناءً أبداً: أي فشل يتحول إلى InsurerResult(ok=False)."""
        result = InsurerResult(provider_id=insurer["provider_id"], provider_name=insurer["name"])
        started = time.perf_counter()
        try:
            adapter = ADAPTERS[insurer["adapter"]]
            payload = adapter["build_payload"](profile)
            url = insurer["base_url"].rstrip("/") + insurer["path"]
            headers = _auth_headers(insurer)

            for attempt in range(1, self.max_attempts + 1):
                result.attempts = attempt
                retryable = True
                try:
                    resp = await client.post(url, json=payload, headers=headers, timeout=insurer["timeout"])
                except httpx.TimeoutException:
                    # لا نعيد المحاولة بعد timeout: انتظرنا المهلة كاملة أصلاً، والإعادة تضاعف زمن الرد
                    # (التقرير يطلب نتيجة خلال ثوانٍ قليلة). الإعادة فقط للأعطال السريعة (5xx / انقطاع اتصال).
                    result.error_type, result.error_message = "timeout", f"انتهت مهلة الاتصال ({insurer['timeout']}s)"
                    retryable = False
                except httpx.TransportError as e:
                    result.error_type, result.error_message = "connection", f"تعذر الاتصال: {type(e).__name__}"
                else:
                    sc = resp.status_code
                    if sc in (401, 403):
                        result.error_type, result.error_message = "auth", "رفضت الشركة مفتاح المصادقة"
                        retryable = False
                    elif sc == 429 or sc >= 500:
                        result.error_type, result.error_message = "http_5xx", f"خطأ من الشركة (HTTP {sc})"
                    elif sc >= 400:
                        result.error_type, result.error_message = "http_4xx", f"رفضت الشركة الطلب (HTTP {sc})"
                        retryable = False
                    else:
                        # 200: ننتقل لتحليل الرد (لا إعادة محاولة لو كان الرد نفسه تالفاً)
                        try:
                            raw = resp.json()
                        except ValueError:
                            result.error_type, result.error_message = "invalid_response", "الرد ليس JSON صالحاً"
                            break
                        try:
                            quotes, skipped = adapter["normalize"](raw, insurer)
                        except InvalidInsurerResponse as e:
                            result.error_type, result.error_message = "invalid_response", str(e)
                            break
                        result.skipped_items = skipped
                        if not quotes:
                            result.error_type = "no_offers"
                            result.error_message = "لم ترجع الشركة أي عرض صالح"
                            break
                        result.quotes, result.ok = quotes, True
                        result.error_type = result.error_message = None
                        break

                if not retryable or attempt == self.max_attempts:
                    break
                await asyncio.sleep(self.retry_backoff)
        except Exception as e:  # شبكة أمان أخيرة: لا نسمح لشركة واحدة بإسقاط الطلب كله
            logger.exception("Agent1: unexpected error for %s", insurer["provider_id"])
            result.error_type, result.error_message = "unexpected", f"خطأ غير متوقع: {type(e).__name__}"
        finally:
            result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result
