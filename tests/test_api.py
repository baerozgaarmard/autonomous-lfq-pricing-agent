"""REST API tests for Autonomous LFQ Pricing Agent."""

import pytest
from fastapi.testclient import TestClient

from lfq_pricing.api import agent, app
from lfq_pricing.repository import PricingRepository

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: pytest.TempPathFactory) -> None:
    # Point agent repository to clean temp SQLite db for each test
    agent.repository = PricingRepository(db_path=tmp_path / "api_test.db")


def test_api_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": "0.1.0"}


def test_api_full_pricing_flow() -> None:
    # 1. Create Catalog Item
    item_payload = {
        "item_id": "LFQ-ITEM-500",
        "sku": "LFQ-SKU-500",
        "name": "High Pressure Actuator",
        "cost": "150.00",
        "current_price": "220.00",
        "target_margin": "0.35",
        "min_price": "180.00",
        "max_price": "300.00",
        "currency": "USD",
        "domain": "industrial_components",
    }
    create_resp = client.post("/v1/catalog/items", json=item_payload)
    assert create_resp.status_code == 201
    assert create_resp.json()["item_id"] == "LFQ-ITEM-500"

    # 2. Get Item
    get_item_resp = client.get("/v1/catalog/items/LFQ-ITEM-500")
    assert get_item_resp.status_code == 200
    assert get_item_resp.json()["name"] == "High Pressure Actuator"

    # 3. Create Pricing Recommendation
    rec_payload = {
        "item_id": "LFQ-ITEM-500",
        "context": {
            "demand_index": 1.05,
            "competitor_observations": [
                {
                    "competitor_name": "Rival Corp",
                    "observed_price": "235.00",
                    "observed_at": "2026-11-22T12:00:00Z",
                    "confidence": 0.9,
                }
            ],
        },
        "target_margin": "0.35",
        "strategy": "balanced",
    }
    rec_resp = client.post("/v1/pricing/recommendations", json=rec_payload)
    assert rec_resp.status_code == 201
    rec_data = rec_resp.json()
    rec_id = rec_data["recommendation_id"]
    assert rec_data["status"] == "recommended"
    assert rec_data["proposed_price"] is not None
    assert len(rec_data["applied_rules"]) > 0

    # 4. Retrieve Recommendation
    get_rec_resp = client.get(f"/v1/pricing/recommendations/{rec_id}")
    assert get_rec_resp.status_code == 200
    assert get_rec_resp.json()["recommendation_id"] == rec_id

    # 5. Approve Recommendation
    approve_payload = {
        "approver": "lead_pricing_analyst",
        "notes": "Approved for seasonal rollout.",
    }
    app_resp = client.post(f"/v1/pricing/recommendations/{rec_id}/approve", json=approve_payload)
    assert app_resp.status_code == 200
    app_data = app_resp.json()
    assert app_data["status"] == "approved"
    assert app_data["approver"] == "lead_pricing_analyst"
