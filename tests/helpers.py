from datetime import datetime, timezone

from composants_watch.models import Listing

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def make_listing(**kw) -> Listing:
    base = dict(source="dealabs", source_id="1", url="https://www.dealabs.com/bons-plans/x-1",
                title="MSI RTX 4070 Super", price_eur=600.0, price_raw="600€", currency="EUR",
                shipping_eur=None, merchant="LDLC", condition="new", posted_at=NOW,
                category="GPU", model="GPU:RTX 4070 Super")
    base.update(kw)
    return Listing(**base)
