"""Unit tests for pricing rules engine, competitor observation filtering, and audit trails."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from lfq_pricing.models import CatalogItem, CompetitorObservation, PricingContext
from lfq_pricing.rules import PricingRulesEngine


def test_rules_evaluation_full_context(
    synthetic_item: CatalogItem, synthetic_context: PricingContext
) -> None:
    engine = PricingRulesEngine(max_observation_age_days=30)
    (
        proposed_price,
        rec_min,
        rec_max,
        applied_rules,
        warnings,
        confidence,
    ) = engine.evaluate(
        item=synthetic_item,
        context=synthetic_context,
        target_margin=Decimal("0.30"),
        strategy="balanced",
    )

    assert proposed_price > synthetic_item.cost
    assert rec_min <= proposed_price <= rec_max
    assert len(applied_rules) >= 2
    assert any(r.rule_id == "RULE_01_TARGET_MARGIN_BASELINE" for r in applied_rules)
    assert any(r.rule_id == "RULE_02_COMPETITOR_BENCHMARK" for r in applied_rules)
    assert confidence.score > 0.6
    assert confidence.freshness_status == "fresh"


def test_stale_competitor_observations_excluded(synthetic_item: CatalogItem) -> None:
    # Observation older than 30 days
    old_time = (datetime.now(UTC) - timedelta(days=45)).isoformat()
    stale_context = PricingContext(
        competitor_observations=[
            CompetitorObservation(
                competitor_name="Ancient Competitor",
                observed_price=Decimal("170.00"),
                observed_at=old_time,
            )
        ]
    )

    engine = PricingRulesEngine(max_observation_age_days=30)
    (
        proposed_price,
        rec_min,
        rec_max,
        applied_rules,
        warnings,
        confidence,
    ) = engine.evaluate(item=synthetic_item, context=stale_context)

    # Competitor rule should NOT be applied because observation is stale
    assert not any(r.rule_id == "RULE_02_COMPETITOR_BENCHMARK" for r in applied_rules)
    assert any("exceeds threshold" in w for w in warnings)
    assert confidence.freshness_status == "stale_competitors"


def test_missing_competitor_observations(synthetic_item: CatalogItem) -> None:
    empty_context = PricingContext(competitor_observations=[])
    engine = PricingRulesEngine()
    (
        proposed_price,
        rec_min,
        rec_max,
        applied_rules,
        warnings,
        confidence,
    ) = engine.evaluate(item=synthetic_item, context=empty_context)

    # Should rely on target margin baseline
    assert len(applied_rules) >= 1
    assert applied_rules[0].rule_id == "RULE_01_TARGET_MARGIN_BASELINE"
    assert confidence.freshness_status == "no_competitors"
