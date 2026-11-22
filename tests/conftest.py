"""Test fixtures and synthetic data for LFQ pricing tests."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from lfq_pricing.models import CatalogItem, CompetitorObservation, PricingContext
from lfq_pricing.repository import PricingRepository


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    return tmp_path / "test_pricing.db"


@pytest.fixture
def repository(temp_db: Path) -> PricingRepository:
    return PricingRepository(db_path=temp_db)


@pytest.fixture
def synthetic_item() -> CatalogItem:
    return CatalogItem(
        item_id="LFQ-SKU-1001",
        sku="SKU-1001",
        name="Precision Industrial Actuator Assembly",
        cost=Decimal("120.00"),
        current_price=Decimal("180.00"),
        target_margin=Decimal("0.30"),  # 30% gross margin target
        min_price=Decimal("150.00"),
        max_price=Decimal("250.00"),
        currency="USD",
        domain="industrial_components",
    )


@pytest.fixture
def synthetic_context() -> PricingContext:
    now_iso = datetime.now(UTC).isoformat()
    return PricingContext(
        demand_index=1.1,
        competitor_observations=[
            CompetitorObservation(
                competitor_name="Competitor Alpha",
                observed_price=Decimal("185.00"),
                observed_at=now_iso,
                confidence=0.95,
            ),
            CompetitorObservation(
                competitor_name="Competitor Beta",
                observed_price=Decimal("190.00"),
                observed_at=now_iso,
                confidence=0.90,
            ),
        ],
    )
