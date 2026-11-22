"""Local SQLite persistence repository for catalog items and recommendation audit trails."""

import sqlite3
from pathlib import Path

from lfq_pricing.config import settings
from lfq_pricing.models import CatalogItem, RecommendationOutput, RecommendationStatus


class PricingRepository:
    """Manages SQLite storage for items, recommendation runs, and approval records."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS catalog_items (
                    item_id TEXT PRIMARY KEY,
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    data JSON NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recommendations (
                    recommendation_id TEXT PRIMARY KEY,
                    item_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_at TIMESTAMP,
                    approver TEXT
                );
                """
            )
            conn.commit()

    def save_item(self, item: CatalogItem) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO catalog_items (item_id, sku, name, data, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(item_id) DO UPDATE SET
                    sku=excluded.sku,
                    name=excluded.name,
                    data=excluded.data,
                    updated_at=CURRENT_TIMESTAMP;
                """,
                (item.item_id, item.sku, item.name, item.model_dump_json()),
            )
            conn.commit()

    def get_item(self, item_id: str) -> CatalogItem | None:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT data FROM catalog_items WHERE item_id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                return None
            return CatalogItem.model_validate_json(row["data"])

    def list_items(self) -> list[CatalogItem]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT data FROM catalog_items ORDER BY item_id")
            return [CatalogItem.model_validate_json(row["data"]) for row in cur.fetchall()]

    def save_recommendation(self, rec: RecommendationOutput) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO recommendations (recommendation_id, item_id, status, data, created_at, approved_at, approver)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(recommendation_id) DO UPDATE SET
                    status=excluded.status,
                    data=excluded.data,
                    approved_at=excluded.approved_at,
                    approver=excluded.approver;
                """,
                (
                    rec.recommendation_id,
                    rec.item_id,
                    rec.status.value,
                    rec.model_dump_json(),
                    rec.created_at,
                    rec.approved_at,
                    rec.approver,
                ),
            )
            conn.commit()

    def get_recommendation(self, recommendation_id: str) -> RecommendationOutput | None:
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT data FROM recommendations WHERE recommendation_id = ?",
                (recommendation_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return RecommendationOutput.model_validate_json(row["data"])

    def approve_recommendation(
        self,
        recommendation_id: str,
        approver: str,
        approved_at: str,
    ) -> RecommendationOutput | None:
        rec = self.get_recommendation(recommendation_id)
        if not rec:
            return None

        rec.status = RecommendationStatus.APPROVED
        rec.approver = approver
        rec.approved_at = approved_at
        self.save_recommendation(rec)
        return rec
