"""Domain models for catalog items, competitor observations, audit traces, and recommendations."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class RecommendationStatus(StrEnum):
    RECOMMENDED = "recommended"
    INSUFFICIENT_DATA = "insufficient_data"
    APPROVED = "approved"
    REJECTED = "rejected"


class CompetitorObservation(BaseModel):
    competitor_name: str
    observed_price: Decimal = Field(gt=Decimal("0.00"))
    observed_at: str  # ISO 8601 string
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class CatalogItem(BaseModel):
    item_id: str
    sku: str
    name: str
    cost: Decimal = Field(ge=Decimal("0.00"))
    current_price: Decimal | None = Field(default=None, gt=Decimal("0.00"))
    target_margin: Decimal | None = Field(default=None, ge=Decimal("0.00"), lt=Decimal("1.00"))
    min_price: Decimal | None = Field(default=None, gt=Decimal("0.00"))
    max_price: Decimal | None = Field(default=None, gt=Decimal("0.00"))
    currency: str = "USD"
    domain: str = "configurable_general"


class PricingContext(BaseModel):
    demand_index: float | None = Field(default=1.0, ge=0.1, le=5.0)
    competitor_observations: list[CompetitorObservation] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    item_id: str
    context: PricingContext = Field(default_factory=PricingContext)
    target_margin: Decimal | None = Field(default=None, ge=Decimal("0.00"), lt=Decimal("1.00"))
    strategy: str = "balanced"  # balanced, cost_plus, competitor_following


class AppliedRule(BaseModel):
    rule_id: str
    description: str
    price_before: Decimal
    price_after: Decimal
    effect: str


class Economics(BaseModel):
    cost: Decimal
    proposed_price: Decimal
    margin: Decimal  # (price - cost) / price
    markup: Decimal  # (price - cost) / cost


class ConfidenceAssessment(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    freshness_status: str


class RecommendationOutput(BaseModel):
    recommendation_id: str
    item_id: str
    status: RecommendationStatus
    created_at: str
    proposed_price: Decimal | None = None
    recommended_min: Decimal | None = None
    recommended_max: Decimal | None = None
    currency: str
    economics: Economics | None = None
    confidence: ConfidenceAssessment
    applied_rules: list[AppliedRule] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    explanation: str
    approved_at: str | None = None
    approver: str | None = None


class ApprovalRequest(BaseModel):
    approver: str = Field(min_length=2)
    notes: str | None = None
