"""Tests for the medical report cost calculator."""

from __future__ import annotations

import pytest
from ghostwriter.costs import (
    CopyTier,
    CostSettings,
    PostageOption,
    calculate_costs,
)


def test_default_flat_fee_only_for_zero_pages() -> None:
    result = calculate_costs(page_count=0, settings=CostSettings())
    assert result.flat_fee == pytest.approx(25.0)
    assert result.copy_cost == pytest.approx(0.0)
    assert result.postage == pytest.approx(0.0)
    assert result.total == pytest.approx(25.0)


def test_copy_cost_within_first_tier() -> None:
    settings = CostSettings(
        flat_fee=25.0,
        copy_tiers=(CopyTier(up_to_page=100, price_per_page=0.50),),
        after_last_tier_price=0.15,
    )
    result = calculate_costs(page_count=10, settings=settings)
    assert result.copy_cost == pytest.approx(5.0)
    assert result.total == pytest.approx(30.0)


def test_copy_cost_spans_into_after_last_tier() -> None:
    settings = CostSettings(
        flat_fee=25.0,
        copy_tiers=(CopyTier(up_to_page=100, price_per_page=0.50),),
        after_last_tier_price=0.15,
    )
    result = calculate_costs(page_count=110, settings=settings)
    # 100 * 0.50 + 10 * 0.15 = 50 + 1.5
    assert result.copy_cost == pytest.approx(51.5)
    assert result.total == pytest.approx(76.5)


def test_multiple_tiers() -> None:
    settings = CostSettings(
        flat_fee=0.0,
        copy_tiers=(
            CopyTier(up_to_page=50, price_per_page=0.50),
            CopyTier(up_to_page=100, price_per_page=0.30),
        ),
        after_last_tier_price=0.10,
    )
    result = calculate_costs(page_count=120, settings=settings)
    # 50*0.50 + 50*0.30 + 20*0.10 = 25 + 15 + 2 = 42
    assert result.copy_cost == pytest.approx(42.0)


def test_postage_option_added() -> None:
    settings = CostSettings(
        flat_fee=25.0,
        postage_options=(PostageOption(key="standard", label="Standardbrief", price=0.95),),
    )
    result = calculate_costs(
        page_count=0,
        settings=settings,
        postage_key="standard",
    )
    assert result.postage == pytest.approx(0.95)
    assert result.total == pytest.approx(25.95)


def test_custom_postage_overrides_key() -> None:
    result = calculate_costs(
        page_count=0,
        settings=CostSettings(),
        custom_postage=3.40,
    )
    assert result.postage == pytest.approx(3.40)


def test_manual_page_count_override_is_callers_responsibility() -> None:
    """Calculator trusts the given page_count; UI may override before calling."""
    result = calculate_costs(page_count=7, settings=CostSettings())
    assert result.page_count == 7


def test_negative_pages_rejected() -> None:
    with pytest.raises(ValueError, match="page_count"):
        calculate_costs(page_count=-1, settings=CostSettings())
