"""FastAPI REST application for catalog management, recommendations, and human approvals."""

from fastapi import FastAPI, HTTPException, status

from lfq_pricing import __version__
from lfq_pricing.agent import PricingAgent
from lfq_pricing.models import (
    ApprovalRequest,
    CatalogItem,
    RecommendationOutput,
    RecommendationRequest,
)

app = FastAPI(
    title="Autonomous LFQ Pricing Agent API",
    version=__version__,
    description=(
        "Configurable pricing recommendation and decision-support agent. "
        "Produces transparent, explainable recommendations with human-in-the-loop approval. "
        "Note: 'LFQ' is preserved as supplied; the underlying pricing rules and catalog are domain-configurable."
    ),
)

agent = PricingAgent()


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Service health verification."""
    return {"status": "ok", "version": __version__}


@app.post(
    "/v1/catalog/items",
    response_model=CatalogItem,
    status_code=status.HTTP_201_CREATED,
    tags=["Catalog"],
)
def create_or_update_item(item: CatalogItem) -> CatalogItem:
    """Create or update a catalog item with costs and price boundaries."""
    agent.repository.save_item(item)
    return item


@app.get("/v1/catalog/items", response_model=list[CatalogItem], tags=["Catalog"])
def list_catalog_items() -> list[CatalogItem]:
    """List all registered catalog items."""
    return agent.repository.list_items()


@app.get("/v1/catalog/items/{item_id}", response_model=CatalogItem, tags=["Catalog"])
def get_catalog_item(item_id: str) -> CatalogItem:
    """Retrieve details for a specific catalog item."""
    item = agent.repository.get_item(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Catalog item '{item_id}' not found.",
        )
    return item


@app.post(
    "/v1/pricing/recommendations",
    response_model=RecommendationOutput,
    status_code=status.HTTP_201_CREATED,
    tags=["Pricing Agent"],
)
def create_recommendation(request: RecommendationRequest) -> RecommendationOutput:
    """Run the bounded pricing recommendation workflow for a catalog item."""
    return agent.run_recommendation(request)


@app.get(
    "/v1/pricing/recommendations/{recommendation_id}",
    response_model=RecommendationOutput,
    tags=["Pricing Agent"],
)
def get_recommendation(recommendation_id: str) -> RecommendationOutput:
    """Retrieve an existing pricing recommendation and its rule audit trace."""
    rec = agent.repository.get_recommendation(recommendation_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation '{recommendation_id}' not found.",
        )
    return rec


@app.post(
    "/v1/pricing/recommendations/{recommendation_id}/approve",
    response_model=RecommendationOutput,
    tags=["Pricing Agent"],
)
def approve_recommendation(
    recommendation_id: str,
    approval: ApprovalRequest,
) -> RecommendationOutput:
    """Record human approval for a pricing recommendation.

    SAFETY NOTICE: This records human decision review in the audit log only;
    it does not publish, submit, or apply prices to any external production system.
    """
    updated = agent.approve_recommendation(
        recommendation_id=recommendation_id,
        approver=approval.approver,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation '{recommendation_id}' not found.",
        )
    return updated
