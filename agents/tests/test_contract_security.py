import asyncio

import httpx

import main
import mock_insurer_api
from agent1_receiver import DataReceiverAgent, InvalidCustomerData, validate_customer_data
from insurers_config import load_insurers
from test_agent1 import valid_request


def test_risk_defaults_and_unknown_city_are_normalized():
    profile = validate_customer_data(valid_request())
    assert (profile["city"], profile["gender"], profile["has_accidents"], profile["cars_count"]) == ("riyadh", "male", "no", "single")
    assert validate_customer_data(valid_request(city="alula"))["city"] == "other"
    try:
        validate_customer_data(valid_request(gender="unknown"))
    except InvalidCustomerData as exc:
        assert "gender" in {e["field"] for e in exc.errors}
    else:
        raise AssertionError("invalid gender was accepted")


def test_concurrent_customers_keep_request_scoped_risk():
    transport = httpx.ASGITransport(app=mock_insurer_api.app)
    agent = DataReceiverAgent(insurers=load_insurers(base_url="http://mock"), transport=transport, retry_backoff=0)

    async def run_pair():
        return await asyncio.gather(
            agent.run(valid_request(city="riyadh", gender="male", has_accidents="yes", cars_count="single")),
            agent.run(valid_request(city="other", gender="female", has_accidents="no", cars_count="multiple")),
        )

    for _ in range(10):
        first, second = asyncio.run(run_pair())
        assert first["customer_profile"]["has_accidents"] == "yes"
        assert second["customer_profile"]["has_accidents"] == "no"
        assert first["unified_quote_set"] and second["unified_quote_set"]
        assert all(a["premium"] > b["premium"] for a, b in zip(first["unified_quote_set"], second["unified_quote_set"]))


def test_admin_company_data_is_not_public_and_provider_scoped():
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mock_insurer_api.app), base_url="http://test") as client:
            assert (await client.get("/portal/api/admin/company/tawuniya")).status_code == 401
            credentials = {"provider_id": "tawuniya", "username": "tawuniya_admin", "password": "Tawuniya@2026"}
            login = await client.post("/portal/api/admin/login", json=credentials)
            assert login.status_code == 200
            token = login.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}
            assert (await client.get("/portal/api/admin/company/rajhi", headers=headers)).status_code == 403
            assert (await client.get("/portal/api/admin/company/tawuniya", headers=headers)).status_code == 200
            assert "policies" not in (await client.get("/portal/api/company/tawuniya")).json()
    asyncio.run(scenario())


def test_comprehensive_vehicle_value_increases_tier_premiums_but_tpl_does_not():
    transport = httpx.ASGITransport(app=mock_insurer_api.app)
    agent = DataReceiverAgent(insurers=load_insurers(base_url="http://mock"), transport=transport, retry_backoff=0)
    low_comp = asyncio.run(agent.run(valid_request(coverage_type="Comprehensive", vehicle_value=20_000)))
    high_comp = asyncio.run(agent.run(valid_request(coverage_type="Comprehensive", vehicle_value=900_000)))
    low_tpl = asyncio.run(agent.run(valid_request(coverage_type="TPL", vehicle_value=20_000)))
    high_tpl = asyncio.run(agent.run(valid_request(coverage_type="TPL", vehicle_value=900_000)))
    lc = {q["plan_name"]: q["premium"] for q in low_comp["unified_quote_set"]}
    hc = {q["plan_name"]: q["premium"] for q in high_comp["unified_quote_set"]}
    lt = {q["plan_name"]: q["premium"] for q in low_tpl["unified_quote_set"]}
    ht = {q["plan_name"]: q["premium"] for q in high_tpl["unified_quote_set"]}
    assert lc.keys() == hc.keys() and all(hc[k] > lc[k] for k in lc)
    assert lt == ht
