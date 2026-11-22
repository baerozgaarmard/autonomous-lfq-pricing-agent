"""Autonomous pricing recommendation agent executing a bounded, inspectable decision workflow."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from lfq_pricing.calculator import (
    PricingCalculationError,
    calculate_gross_margin,
    calculate_markup,
)
from lfq_pricing.models import (
    ConfidenceAssessment,
    Economics,
    RecommendationOutput,
    RecommendationRequest,
    RecommendationStatus,
)
from lfq_pricing.repository import PricingRepository
from lfq_pricing.rules import PricingRulesEngine


class PricingAgent:
    """Bounded, explainable pricing agent producing verifiable recommendations with an audit trail."""

    def __init__(
        self,
        repository: PricingRepository | None = None,
        rules_engine: PricingRulesEngine | None = None,
    ) -> None:
        self.repository = repository or PricingRepository()
        self.rules_engine = rules_engine or PricingRulesEngine()

    def run_recommendation(self, request: RecommendationRequest) -> RecommendationOutput:
        rec_id = f"rec_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(UTC).isoformat()

        # Step 1: Validate item exists
        item = self.repository.get_item(request.item_id)
        if not item:
            output = RecommendationOutput(
                recommendation_id=rec_id,
                item_id=request.item_id,
                status=RecommendationStatus.INSUFFICIENT_DATA,
                created_at=now_iso,
                currency="USD",
                confidence=ConfidenceAssessment(
                    score=0.0, completeness=0.0, freshness_status="missing_item"
                ),
                warnings=[f"Item '{request.item_id}' not found in catalog repository."],
                explanation="Cannot generate pricing recommendation because the target catalog item is missing.",
            )
            self.repository.save_recommendation(output)
            return output

        # Step 2: Validate item cost boundary
        if item.cost <= Decimal("0.00"):
            output = RecommendationOutput(
                recommendation_id=rec_id,
                item_id=item.item_id,
                status=RecommendationStatus.INSUFFICIENT_DATA,
                created_at=now_iso,
                currency=item.currency,
                confidence=ConfidenceAssessment(
                    score=0.2, completeness=0.3, freshness_status="zero_cost"
                ),
                warnings=[f"Item '{item.item_id}' has non-positive cost: {item.cost}"],
                explanation="Pricing recommendation halted: Item unit cost must be strictly positive to establish baseline margin.",
            )
            self.repository.save_recommendation(output)
            return output

        try:
            # Step 3, 4, 5, 6: Evaluate Rules Engine
            (
                proposed_price,
                rec_min,
                rec_max,
                applied_rules,
                warnings,
                confidence,
            ) = self.rules_engine.evaluate(
                item=item,
                context=request.context,
                target_margin=request.target_margin,
                strategy=request.strategy,
            )

            # Step 7: Calculate final economics
            margin = calculate_gross_margin(proposed_price, item.cost)
            markup = calculate_markup(proposed_price, item.cost)
            economics = Economics(
                cost=item.cost,
                proposed_price=proposed_price,
                margin=margin,
                markup=markup,
            )

            explanation = (
                f"Recommended price {item.currency} {proposed_price} establishes a {margin * 100}% gross margin "
                f"({markup * 100}% markup) based on unit cost {item.cost}. "
                f"Applied {len(applied_rules)} rule(s) under '{request.strategy}' strategy."
            )

            output = RecommendationOutput(
                recommendation_id=rec_id,
                item_id=item.item_id,
                status=RecommendationStatus.RECOMMENDED,
                created_at=now_iso,
                proposed_price=proposed_price,
                recommended_min=rec_min,
                recommended_max=rec_max,
                currency=item.currency,
                economics=economics,
                confidence=confidence,
                applied_rules=applied_rules,
                warnings=warnings,
                explanation=explanation,
            )

        except PricingCalculationError as err:
            output = RecommendationOutput(
                recommendation_id=rec_id,
                item_id=item.item_id,
                status=RecommendationStatus.INSUFFICIENT_DATA,
                created_at=now_iso,
                currency=item.currency,
                confidence=ConfidenceAssessment(
                    score=0.1, completeness=0.2, freshness_status="error"
                ),
                warnings=[str(err)],
                explanation=f"Pricing calculation error encountered: {err}",
            )

        # Step 8: Persist snapshot and audit trace
        self.repository.save_recommendation(output)
        return output

    def approve_recommendation(
        self, recommendation_id: str, approver: str
    ) -> RecommendationOutput | None:
        """Record explicit human approval for a pricing recommendation without side effects."""
        now_iso = datetime.now(UTC).isoformat()
        return self.repository.approve_recommendation(
            recommendation_id=recommendation_id,
            approver=approver,
            approved_at=now_iso,
        )
