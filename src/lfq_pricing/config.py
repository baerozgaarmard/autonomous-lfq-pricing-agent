"""Configuration settings for Autonomous LFQ Pricing Agent."""

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass
class Settings:
    host: str = os.getenv("LFQ_PRICING_HOST", "127.0.0.1")
    port: int = int(os.getenv("LFQ_PRICING_PORT", "8002"))
    db_path: Path = Path(os.getenv("LFQ_PRICING_DB_PATH", "./data/pricing_agent.db"))
    max_observation_age_days: int = int(os.getenv("LFQ_PRICING_MAX_OBSERVATION_AGE_DAYS", "30"))
    default_target_margin: Decimal = Decimal(os.getenv("LFQ_PRICING_DEFAULT_TARGET_MARGIN", "0.25"))
    default_currency: str = os.getenv("LFQ_PRICING_DEFAULT_CURRENCY", "USD")
    allow_external_execution: bool = (
        os.getenv("LFQ_PRICING_ALLOW_EXTERNAL_EXECUTION", "false").lower() == "true"
    )


settings = Settings()
