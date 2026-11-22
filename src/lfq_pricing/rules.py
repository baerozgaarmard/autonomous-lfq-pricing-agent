"""Configurable rule evaluation engine tracking an inspectable audit trace."""

import statistics
from datetime import UTC, datetime
from decimal import Decimal

from lfq_pricing.calculator import calculate_target_margin_price, clamp_price, quantize_money
from lfq_pricing.config import settings
from lfq_pricing.models import (
    AppliedRule,
    CatalogItem,
    CompetitorObservation,
    ConfidenceAssessment,
    PricingContext,
)


class PricingRulesEngine:
    """Evaluates ordered, deterministic pricing rules and records the exact audit trail."""

    def __init__(self, max_observation_age_days: int | None = None) -> None:
        self.max_age_days = (
            max_observation_age_days
            if max_observation_age_days is not None
            else settings.max_observation_age_days
        )

    def evaluate(
        self,
        item: CatalogItem,
        context: PricingContext,
        target_margin: Decimal | None = None,
        strategy: str = "balanced",
    ) -> tuple[Decimal, Decimal, Decimal, list[AppliedRule], list[str], ConfidenceAssessment]:
        applied_rules: list[AppliedRule] = []
        warnings: list[str] = []

        # 1. Quality & Confidence Assessment
        confidence = self._assess_confidence(item, context, warnings)

        # 2. Baseline Price: Cost + Target Margin
        effective_margin = target_margin or item.target_margin or settings.default_target_margin
        baseline_price = calculate_target_margin_price(item.cost, effective_margin)

        applied_rules.append(
            AppliedRule(
                rule_id="RULE_01_TARGET_MARGIN_BASELINE",
                description=f"Calculated baseline price using target gross margin {effective_margin * 100}%",
                price_before=item.cost,
                price_after=baseline_price,
                effect=f"+{baseline_price - item.cost}",
            )
        )

        current_price = baseline_price

        # 3. Competitor Benchmarking (if fresh observations exist)
        fresh_competitors = self._filter_fresh_competitors(
            context.competitor_observations, warnings
        )
        if fresh_competitors:
            comp_prices = [c.observed_price for c in fresh_competitors]
            median_comp = quantize_money(Decimal(str(statistics.median(comp_prices))))

            price_before_comp = current_price
            if strategy == "competitor_following":
                # Follow competitor median directly
                current_price = median_comp
            elif strategy == "balanced":
                # Weighted blend: 60% internal target margin, 40% competitor median
                blended = (current_price * Decimal("0.60")) + (median_comp * Decimal("0.40"))
                current_price = quantize_money(blended)

            applied_rules.append(
                AppliedRule(
                    rule_id="RULE_02_COMPETITOR_BENCHMARK",
                    description=(
                        f"Adjusted for {len(fresh_competitors)} fresh competitor observation(s) "
                        f"(median: {median_comp}) using '{strategy}' strategy."
                    ),
                    price_before=price_before_comp,
                    price_after=current_price,
                    effect=f"{current_price - price_before_comp:+}",
                )
            )

        # 4. Demand Signal Adjustment
        if context.demand_index and context.demand_index != 1.0:
            price_before_demand = current_price
            demand_multiplier = Decimal(str(round(context.demand_index**0.5, 4)))
            current_price = quantize_money(current_price * demand_multiplier)
            applied_rules.append(
                AppliedRule(
                    rule_id="RULE_03_DEMAND_ELASTICITY",
                    description=f"Adjusted for market demand index {context.demand_index}",
                    price_before=price_before_demand,
                    price_after=current_price,
                    effect=f"{current_price - price_before_demand:+}",
                )
            )

        # 5. Hard Business Constraints (Clamping)
        price_before_clamp = current_price
        clamped_price, clamp_warnings = clamp_price(
            current_price,
            min_price=item.min_price,
            max_price=item.max_price,
        )
        warnings.extend(clamp_warnings)

        if clamped_price != price_before_clamp:
            applied_rules.append(
                AppliedRule(
                    rule_id="RULE_04_BOUNDARY_CLAMP",
                    description="Clamped price to enforce hard business min/max price limits",
                    price_before=price_before_clamp,
                    price_after=clamped_price,
                    effect=f"{clamped_price - price_before_clamp:+}",
                )
            )

        proposed_price = clamped_price
        recommended_min = quantize_money(proposed_price * Decimal("0.95"))
        recommended_max = quantize_money(proposed_price * Decimal("1.08"))

        if item.min_price is not None:
            recommended_min = max(recommended_min, item.min_price)
        if item.max_price is not None:
            recommended_max = min(recommended_max, item.max_price)

        return (
            proposed_price,
            recommended_min,
            recommended_max,
            applied_rules,
            warnings,
            confidence,
        )

    def _assess_confidence(
        self,
        item: CatalogItem,
        context: PricingContext,
        warnings: list[str],
    ) -> ConfidenceAssessment:
        completeness_pts = 0.5  # Base for having cost and item definition
        if item.current_price:
            completeness_pts += 0.2
        if item.min_price and item.max_price:
            completeness_pts += 0.1
        if context.competitor_observations:
            completeness_pts += 0.2

        completeness = min(1.0, completeness_pts)

        # Freshness check
        freshness_status = "no_competitors"
        fresh_count = 0
        if context.competitor_observations:
            for obs in context.competitor_observations:
                try:
                    obs_dt = datetime.fromisoformat(obs.observed_at.replace("Z", "+00:00"))
                    age_days = (datetime.now(UTC) - obs_dt).days
                    if age_days <= self.max_age_days:
                        fresh_count += 1
                except Exception:
                    pass

            if fresh_count == len(context.competitor_observations):
                freshness_status = "fresh"
            elif fresh_count > 0:
                freshness_status = "mixed_freshness"
            else:
                freshness_status = "stale_competitors"

        score = completeness
        if freshness_status == "fresh":
            score = min(1.0, score + 0.1)
        elif freshness_status == "stale_competitors":
            score = max(0.2, score - 0.2)

        return ConfidenceAssessment(
            score=round(score, 2),
            completeness=round(completeness, 2),
            freshness_status=freshness_status,
        )

    def _filter_fresh_competitors(
        self,
        observations: list[CompetitorObservation],
        warnings: list[str],
    ) -> list[CompetitorObservation]:
        fresh: list[CompetitorObservation] = []
        now = datetime.now(UTC)

        for obs in observations:
            try:
                obs_dt = datetime.fromisoformat(obs.observed_at.replace("Z", "+00:00"))
                age_days = (now - obs_dt).days
                if age_days > self.max_age_days:
                    warnings.append(
                        f"Competitor observation for '{obs.competitor_name}' is {age_days} days old "
                        f"(exceeds threshold of {self.max_age_days} days) and was excluded."
                    )
                else:
                    fresh.append(obs)
            except Exception:
                warnings.append(
                    f"Could not parse timestamp '{obs.observed_at}' for competitor '{obs.competitor_name}'."
                )

        return fresh
