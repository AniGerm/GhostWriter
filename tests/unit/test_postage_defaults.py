"""Aktuelle Deutsche-Post-Versandpreise und Default Großbrief."""

from __future__ import annotations

from ghostwriter.costs import CostSettings, calculate_costs
from ghostwriter.settings import AppSettings


def test_default_postage_prices_match_post() -> None:
    settings = AppSettings()
    assert settings.postage["standard"] == 0.95
    assert settings.postage["kompakt"] == 1.10
    assert settings.postage["gross"] == 1.80
    assert settings.default_postage_key == "gross"


def test_cost_settings_defaults_use_new_prices() -> None:
    cfg = CostSettings()
    by_key = {o.key: o.price for o in cfg.postage_options}
    assert by_key["kompakt"] == 1.10
    assert by_key["gross"] == 1.80
    result = calculate_costs(page_count=0, settings=cfg, postage_key="gross")
    assert result.postage == 1.80
