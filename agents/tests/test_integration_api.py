import asyncio
import os
from pathlib import Path

import httpx

import main
import mock_insurer_api
from agent1_receiver import DataReceiverAgent
from insurers_config import load_insurers
from test_agent1 import valid_request


async def request(path, **kwargs):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        return await client.request(kwargs.pop("method", "GET"), path, **kwargs)


def test_provider_listing_does_not_disclose_api_keys():
    response = asyncio.run(request("/providers"))
    assert response.status_code == 200
    assert response.json() and all("api_key" not in p for p in response.json())


def test_invalid_json_recommendation_is_json_422():
    response = asyncio.run(
        request(
            "/recommend",
            method="POST",
            content="{broken",
            headers={"Content-Type": "application/json"},
        )
    )
    assert response.status_code == 422
    assert "application/json" in response.headers["content-type"]
    assert response.json()["detail"]


def test_recommendation_returns_named_packages_without_persisting(monkeypatch):
    transport = httpx.ASGITransport(app=mock_insurer_api.app)
    monkeypatch.setattr(
        main,
        "agent1",
        DataReceiverAgent(
            insurers=load_insurers(base_url="http://mock"),
            transport=transport,
            retry_backoff=0,
        ),
    )

    first = asyncio.run(
        request("/recommend", method="POST", json=valid_request())
    )
    second = asyncio.run(
        request("/recommend", method="POST", json=valid_request())
    )

    assert first.status_code == second.status_code == 200
    first_data = first.json()
    second_data = second.json()
    offers = first_data["all_offers_ranked"]
    assert len(offers) > 1
    assert all(offer.get("plan_name") for offer in offers)
    assert first_data["recommended_package"]["plan_name"] in {
        offer["plan_name"] for offer in offers
    }
    assert [offer["plan_name"] for offer in second_data["all_offers_ranked"]] == [
        offer["plan_name"] for offer in offers
    ]
    # /recommend is deliberately stateless until profile/vehicle persistence exists.
    assert not Path(os.environ["THIQA_DB_PATH"]).exists()
