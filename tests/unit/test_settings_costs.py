"""AppSettings → CostSettings mapping."""

from __future__ import annotations

from ghostwriter.settings import AppSettings


def test_to_cost_settings() -> None:
    s = AppSettings(flat_fee=10.0, copy_tier_up_to=50, copy_tier_price=0.4)
    c = s.to_cost_settings()
    assert c.flat_fee == 10.0
    assert c.copy_tiers[0].up_to_page == 50
    assert any(o.key == "standard" for o in c.postage_options)
