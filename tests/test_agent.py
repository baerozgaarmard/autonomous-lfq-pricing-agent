"""Integration tests for PricingAgent bounded workflow, persistence, and human approvals."""

from decimal import Decimal

from lfq_pricing.agent import PricingAgent
from lfq_pricing.models import (
    CatalogItem,
    PricingContext,
    RecommendationRequest,
    RecommendationStatus,
)
from lfq_pricing.repository import PricingRepository


def test_agent_recommendation_deterministic(
    repository: PricingRepository,
    synthetic_item: CatalogItem,
    synthetic_context: PricingContext,
) -> None:
    repository.save_item(synthetic_item)
    agent = PricingAgent(repository=repository)

    req = RecommendationRequest(
        item_id=synthetic_item.item_id,
        context=synthetic_context,
        target_margin=Decimal("0.30"),
        strategy="balanced",
    )

    rec1 = agent.run_recommendation(req)
    rec2 = agent.run_recommendation(req)

    assert rec1.status == RecommendationStatus.RECOMMENDED
    assert rec2.status == RecommendationStatus.RECOMMENDED
    assert rec1.proposed_price == rec2.proposed_price
    assert rec1.economics.margin == rec2.economics.margin
    assert len(rec1.applied_rules) == len(rec2.applied_rules)


def test_agent_missing_item(repository: PricingRepository) -> None:
    agent = PricingAgent(repository=repository)
    req = RecommendationRequest(item_id="NON_EXISTENT_SKU")

    rec = agent.run_recommendation(req)
    assert rec.status == RecommendationStatus.INSUFFICIENT_DATA
    assert rec.proposed_price is None
    assert any("not found" in w.lower() for w in rec.warnings)


def test_agent_zero_cost_item(repository: PricingRepository) -> None:
    zero_item = CatalogItem(
        item_id="ITEM-ZERO",
        sku="SKU-ZERO",
        name="Zero Cost Sample",
        cost=Decimal("0.00"),
    )
    repository.save_item(zero_item)
    agent = PricingAgent(repository=repository)

    req = RecommendationRequest(item_id="ITEM-ZERO")
    rec = agent.run_recommendation(req)
    assert rec.status == RecommendationStatus.INSUFFICIENT_DATA
    assert any("non-positive cost" in w for w in rec.warnings)


def test_agent_approval_workflow(
    repository: PricingRepository,
    synthetic_item: CatalogItem,
    synthetic_context: PricingContext,
) -> None:
    repository.save_item(synthetic_item)
    agent = PricingAgent(repository=repository)

    rec = agent.run_recommendation(
        RecommendationRequest(item_id=synthetic_item.item_id, context=synthetic_context)
    )
    assert rec.status == RecommendationStatus.RECOMMENDED

    # Approve recommendation
    approved = agent.approve_recommendation(
        recommendation_id=rec.recommendation_id,
        approver="senior_pricing_manager",
    )
    assert approved is not None
    assert approved.status == RecommendationStatus.APPROVED
    assert approved.approver == "senior_pricing_manager"
    assert approved.approved_at is not None

    # Retrieve from repository to verify persistence
    retrieved = repository.get_recommendation(rec.recommendation_id)
    assert retrieved is not None
    assert retrieved.status == RecommendationStatus.APPROVED
    assert retrieved.approver == "senior_pricing_manager"
