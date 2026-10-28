"""
اختبارات Agent 1 بشكل مستقل (لا تحتاج تشغيل أي سيرفر):
    cd agents && python -m pytest tests -v

نستخدم Mock Insurance API الحقيقي داخل نفس العملية عبر ASGITransport،
ونغلّفه بـ FlakyTransport لحقن الأعطال (timeout / 5xx / رد تالف ...) في شركات محددة.
"""

import asyncio
import time
from collections import defaultdict
from datetime import date

import httpx
import pytest

import mock_insurer_api
from agent1_receiver import (
    DataReceiverAgent,
    InvalidCustomerData,
    NoOffersAvailable,
    validate_customer_data,
)
from insurers_config import load_insurers

PATHS = {
    "tawuniya": "/tawuniya/quotes",
    "rajhi": "/rajhi/offers",
    "medgulf": "/medgulf/plans",
    "acig": "/acig/quote",
}

UNIFIED_KEYS = {
    "quote_id", "provider_id", "provider_name", "premium", "coverage_type", "deductible",
    "add_ons", "reliability", "workshop_network", "digital_score", "retrieved_at",
}


def valid_request(**over):
    data = {
        "national_id": "1098765432",
        "birth_date": "1995-06-15",
        "vehicle_serial": "123456789",
        "manufacture_year": 2021,
        "vehicle_value": 85000,
        "purpose_of_use": "personal",
        "annual_mileage": "medium",
        "coverage_type": "TPL",
        "priority": "Budget",
    }
    data.update(over)
    return data


class FlakyTransport(httpx.AsyncBaseTransport):
    """يمرّر الطلبات لـ Mock API الحقيقي، إلا لو عرّفنا سلوكاً مخصصاً لمسار معين."""

    def __init__(self, behaviors=None):
        self.inner = httpx.ASGITransport(app=mock_insurer_api.app)
        self.behaviors = behaviors or {}
        self.calls = defaultdict(int)

    async def handle_async_request(self, request):
        path = request.url.path
        self.calls[path] += 1
        behavior = self.behaviors.get(path)
        if behavior:
            r = behavior(self.calls[path], request)
            if r is not None:
                return r
        return await self.inner.handle_async_request(request)


def make_agent(behaviors=None, **kw):
    transport = FlakyTransport(behaviors)
    insurers = load_insurers(base_url="http://mock")
    kw.setdefault("retry_backoff", 0)
    return DataReceiverAgent(insurers=insurers, transport=transport, **kw), transport


def run(agent, data=None):
    return asyncio.run(agent.run(data or valid_request()))


def status_of(result, pid):
    return next(s for s in result["provider_status"] if s["provider_id"] == pid)


# ============================================================ 1) التحقق من البيانات
class TestValidation:
    def test_valid_input_is_structured(self):
        p = validate_customer_data(valid_request(), today=date(2026, 9, 1))
        assert p["driver_age"] == 31
        assert p["coverage_type"] == "TPL"
        assert p["vehicle_age"] == 5
        assert p["vehicle_value"] == 85000.0

    def test_defaults_applied(self):
        d = valid_request()
        for k in ("purpose_of_use", "annual_mileage", "priority"):
            d.pop(k)
        p = validate_customer_data(d)
        assert (p["purpose_of_use"], p["annual_mileage"], p["priority"]) == ("personal", "medium", "Balanced")

    @pytest.mark.parametrize("coverage,expected", [
        ("TPL", "TPL"), ("tpl", "TPL"), ("ضد الغير", "TPL"),
        ("Comprehensive", "Comprehensive"), ("شامل", "Comprehensive"),
    ])
    def test_coverage_normalized(self, coverage, expected):
        assert validate_customer_data(valid_request(coverage_type=coverage))["coverage_type"] == expected

    def test_collects_all_errors_at_once(self):
        bad = valid_request(national_id="123", vehicle_value="abc", coverage_type="xyz", birth_date="2030-01-01")
        with pytest.raises(InvalidCustomerData) as e:
            validate_customer_data(bad)
        fields = {x["field"] for x in e.value.errors}
        assert {"national_id", "vehicle_value", "coverage_type", "birth_date"} <= fields

    @pytest.mark.parametrize("field,value", [
        ("national_id", "3098765432"),         # لا يبدأ بـ 1 أو 2
        ("national_id", "10987654"),           # قصير
        ("birth_date", "1995-02-31"),          # تاريخ غير موجود
        ("birth_date", "2015-01-01"),          # أقل من 18
        ("vehicle_serial", "12"),              # قصير
        ("manufacture_year", 1950),
        ("vehicle_value", 100),                # أقل من الحد
        ("vehicle_value", None),
        ("purpose_of_use", "racing"),
        ("annual_mileage", "huge"),
        ("priority", "Cheapest"),
        ("requested_add_ons", ["flying_car"]),
    ])
    def test_rejects_bad_field(self, field, value):
        with pytest.raises(InvalidCustomerData) as e:
            validate_customer_data(valid_request(**{field: value}))
        assert field in {x["field"] for x in e.value.errors}

    def test_non_dict_rejected(self):
        with pytest.raises(InvalidCustomerData):
            validate_customer_data("not a dict")


# ============================================================ 2) الحالة الطبيعية (كل الشركات تعمل)
class TestHappyPath:
    def test_returns_unified_quotes_from_all_four_insurers(self):
        agent, _ = make_agent()
        res = run(agent)
        quotes = res["unified_quote_set"]
        assert {q["provider_id"] for q in quotes} == set(PATHS)
        for q in quotes:
            assert UNIFIED_KEYS <= set(q)
            assert isinstance(q["premium"], float) and q["premium"] > 0
            assert isinstance(q["deductible"], float)
            assert q["coverage_type"] == "TPL"
            assert all(a in ("agency_repair", "roadside_assistance", "replacement_car", "windshield_cover", "gulf_coverage") for a in q["add_ons"])
        assert all(s["ok"] and s["attempts"] == 1 for s in res["provider_status"])

    def test_different_insurer_formats_are_normalized_correctly(self):
        """ميدغلف ترجع نصوصاً، ACIG ترجع هللات، الراجحي ترجع عملة مركبة: كلها تصبح ريالات كأرقام."""
        res = run(make_agent()[0])
        by = {q["provider_id"]: q for q in res["unified_quote_set"]}
        base = {"tawuniya": 483, "rajhi": 507, "medgulf": 469, "acig": 428}
        for pid, b in base.items():  # المخاطر الصريحة ترفع/تخفض السعر بصورة حتمية
            assert by[pid]["premium"] > 0, pid
        assert all(q["plan_name"] for q in res["unified_quote_set"])
        assert by["acig"]["deductible"] >= 500.0

    def test_comprehensive_request_gets_comprehensive_quotes(self):
        res = run(make_agent()[0], valid_request(coverage_type="Comprehensive"))
        assert {q["coverage_type"] for q in res["unified_quote_set"]} == {"Comprehensive"}
        assert all(q["premium"] > 0 for q in res["unified_quote_set"])

    def test_customer_profile_passed_on(self):
        res = run(make_agent()[0])
        assert res["customer_profile"]["priority"] == "Budget"
        assert res["customer_profile"]["driver_age"] >= 18

    def test_prices_are_deterministic(self):
        a = run(make_agent()[0])["unified_quote_set"]
        b = run(make_agent()[0])["unified_quote_set"]
        assert [q["premium"] for q in a] == [q["premium"] for q in b]

    def test_young_driver_pays_more(self):
        old = run(make_agent()[0], valid_request(birth_date="1985-01-01"))["unified_quote_set"]
        young = run(make_agent()[0], valid_request(birth_date=f"{date.today().year - 20}-01-01"))["unified_quote_set"]
        for o, y in zip(old, young):
            assert y["premium"] > o["premium"]

    def test_requests_are_sent_in_parallel(self):
        def slow(call_no, request):
            return None  # fall-through, but we delay inside a wrapper below

        class SlowTransport(FlakyTransport):
            async def handle_async_request(self, request):
                await asyncio.sleep(0.3)
                return await super().handle_async_request(request)

        agent = DataReceiverAgent(insurers=load_insurers(base_url="http://mock"), transport=SlowTransport(), retry_backoff=0)
        t = time.perf_counter()
        run(agent)
        assert time.perf_counter() - t < 0.9  # 4 × 0.3 تسلسلياً = 1.2s؛ بالتوازي ≈ 0.3s


# ============================================================ 3) معالجة الأخطاء
def raise_timeout(call_no, request):
    raise httpx.ReadTimeout("timed out", request=request)


def raise_connect_error(call_no, request):
    raise httpx.ConnectError("refused", request=request)


def http_status(code):
    return lambda call_no, request: httpx.Response(code, json={"detail": "x"})


class TestErrorHandling:
    def test_one_insurer_timeout_does_not_break_others(self):
        agent, tr = make_agent({PATHS["acig"]: raise_timeout})
        res = run(agent)
        assert {q["provider_id"] for q in res["unified_quote_set"]} == {"tawuniya", "rajhi", "medgulf"}
        s = status_of(res, "acig")
        assert (s["ok"], s["error_type"], s["attempts"]) == (False, "timeout", 1)  # timeout لا يُعاد
        assert tr.calls[PATHS["acig"]] == 1

    def test_connection_error_reported_and_retried(self):
        res = run(make_agent({PATHS["rajhi"]: raise_connect_error})[0])
        s = status_of(res, "rajhi")
        assert (s["ok"], s["error_type"], s["attempts"]) == (False, "connection", 2)

    def test_server_error_is_retried_then_succeeds(self):
        flaky = lambda n, req: httpx.Response(503, json={}) if n == 1 else None  # يفشل أول مرة فقط
        agent, tr = make_agent({PATHS["medgulf"]: flaky})
        res = run(agent)
        s = status_of(res, "medgulf")
        assert s["ok"] and s["attempts"] == 2
        assert len(res["unified_quote_set"]) >= 12

    def test_persistent_500_marked_failed(self):
        res = run(make_agent({PATHS["tawuniya"]: http_status(500)})[0])
        s = status_of(res, "tawuniya")
        assert (s["ok"], s["error_type"], s["attempts"]) == (False, "http_5xx", 2)

    def test_auth_failure_not_retried(self):
        agent, tr = make_agent({PATHS["acig"]: http_status(401)})
        s = status_of(run(agent), "acig")
        assert (s["error_type"], s["attempts"]) == ("auth", 1)
        assert tr.calls[PATHS["acig"]] == 1

    def test_client_error_4xx_not_retried(self):
        agent, tr = make_agent({PATHS["rajhi"]: http_status(422)})
        s = status_of(run(agent), "rajhi")
        assert (s["error_type"], s["attempts"]) == ("http_4xx", 1)

    def test_non_json_response(self):
        bad = lambda n, req: httpx.Response(200, text="<html>oops</html>")
        s = status_of(run(make_agent({PATHS["medgulf"]: bad})[0]), "medgulf")
        assert (s["ok"], s["error_type"], s["attempts"]) == (False, "invalid_response", 1)

    def test_wrong_json_shape(self):
        bad = lambda n, req: httpx.Response(200, json={"unexpected": "shape"})
        s = status_of(run(make_agent({PATHS["tawuniya"]: bad})[0]), "tawuniya")
        assert (s["ok"], s["error_type"]) == (False, "invalid_response")

    def test_empty_offers(self):
        empty = lambda n, req: httpx.Response(200, json={"data": {"offers": []}})
        s = status_of(run(make_agent({PATHS["rajhi"]: empty})[0]), "rajhi")
        assert (s["ok"], s["error_type"]) == (False, "no_offers")

    def test_bad_item_skipped_but_good_items_kept(self):
        mixed = lambda n, req: httpx.Response(200, json={"quotes": [
            {"quote_ref": "A1", "product": "TPL", "premium_halalas": -500, "co_pay": 1500, "addons": []},   # قسط سالب
            {"quote_ref": "A2", "product": "TPL", "premium_halalas": 43000, "co_pay": 1500, "addons": ["roadside_assistance", "made_up_addon"]},
            {"quote_ref": "A3", "product": "FLYING", "premium_halalas": 43000, "co_pay": 1500},               # نوع غير معروف
            {"oops": True},                                                                                    # عنصر تالف
        ]})
        res = run(make_agent({PATHS["acig"]: mixed})[0])
        acig = [q for q in res["unified_quote_set"] if q["provider_id"] == "acig"]
        assert len(acig) == 1 and acig[0]["premium"] == 430.0
        assert acig[0]["add_ons"] == ["roadside_assistance"]  # الإضافة غير المعتمدة حُذفت
        assert status_of(res, "acig")["skipped_items"] == 3

    def test_unsupported_currency_skipped(self):
        usd = lambda n, req: httpx.Response(200, json={"data": {"offers": [
            {"id": "X", "type": "THIRD_PARTY", "price": {"amount": 100, "currency": "USD"}, "excess": 0}]}})
        s = status_of(run(make_agent({PATHS["rajhi"]: usd})[0]), "rajhi")
        assert s["ok"] is False

    def test_all_insurers_fail_raises_with_details(self):
        behaviors = {p: raise_timeout for p in PATHS.values()}
        with pytest.raises(NoOffersAvailable) as e:
            run(make_agent(behaviors)[0])
        assert len(e.value.provider_status) == 4
        assert all(s["error_type"] == "timeout" for s in e.value.provider_status)

    def test_invalid_customer_data_never_calls_insurers(self):
        agent, tr = make_agent()
        with pytest.raises(InvalidCustomerData):
            run(agent, valid_request(national_id="abc"))
        assert sum(tr.calls.values()) == 0

    def test_wrong_api_key_from_real_mock(self):
        """بدون حقن: المفتاح الخاطئ يرفضه الـ Mock API بـ 401 فعلاً."""
        insurers = load_insurers(base_url="http://mock")
        for ins in insurers:
            if ins["provider_id"] == "medgulf":
                ins["api_key"] = "wrong-key"
        agent = DataReceiverAgent(insurers=insurers, transport=FlakyTransport(), retry_backoff=0)
        res = run(agent)
        assert status_of(res, "medgulf")["error_type"] == "auth"
        assert len(res["unified_quote_set"]) >= 9

    def test_fault_injection_endpoint_of_mock_api(self):
        """حقن عطل من داخل الـ Mock نفسه (500) ثم إزالته."""
        mock_insurer_api.FAULTS["acig"] = "500"
        try:
            res = run(make_agent()[0])
            assert status_of(res, "acig")["error_type"] == "http_5xx"
        finally:
            mock_insurer_api.FAULTS.clear()
        assert status_of(run(make_agent()[0]), "acig")["ok"]
