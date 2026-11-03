from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Listing:
    source: str
    source_id: str
    url: str
    title: str
    price_eur: float | None
    price_raw: str
    currency: str
    shipping_eur: float | None
    merchant: str
    condition: str          # "new" | "used" | "unknown"
    posted_at: datetime
    expired: bool = False
    category: str | None = None
    model: str | None = None
    image_url: str | None = None

    @property
    def effective_eur(self) -> float | None:
        if self.price_eur is None:
            return None
        return round(self.price_eur + (self.shipping_eur or 0.0), 2)
