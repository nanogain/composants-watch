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


def verify_all_active(store, now) -> dict:
    """Vérification simulée : toutes les annonces Dealabs sont actives."""
    todo = store.to_check(now, 3650, 0, 10**6)
    for sid, _ in todo:
        store.mark_checked("dealabs", sid, False, now)
    return {"checked": len(todo), "expired": 0, "failures": 0, "stopped": None}
