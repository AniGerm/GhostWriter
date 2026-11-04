"""Kostenrechner für ärztliche Berichte (Pauschale, Kopien, Versand)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CopyTier:
    """Kopierpreis bis einschließlich `up_to_page`."""

    up_to_page: int
    price_per_page: float


@dataclass(frozen=True, slots=True)
class PostageOption:
    """Versandoption mit festem Preis."""

    key: str
    label: str
    price: float


@dataclass(frozen=True, slots=True)
class CostSettings:
    """Konfigurierbare Kosteneinstellungen."""

    flat_fee: float = 25.0
    copy_tiers: tuple[CopyTier, ...] = (CopyTier(up_to_page=100, price_per_page=0.50),)
    after_last_tier_price: float = 0.15
    postage_options: tuple[PostageOption, ...] = (
        PostageOption(key="standard", label="Standardbrief", price=0.95),
        PostageOption(key="kompakt", label="Kompaktbrief", price=1.25),
        PostageOption(key="gross", label="Großbrief", price=2.10),
        PostageOption(key="maxi", label="Maxibrief", price=3.40),
    )


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Ergebnis der Kostenberechnung."""

    page_count: int
    flat_fee: float
    copy_cost: float
    postage: float
    total: float


def _copy_cost(page_count: int, settings: CostSettings) -> float:
    remaining = page_count
    previous_cap = 0
    total = 0.0
    for tier in sorted(settings.copy_tiers, key=lambda t: t.up_to_page):
        if remaining <= 0:
            break
        span = tier.up_to_page - previous_cap
        if span <= 0:
            continue
        pages_in_tier = min(remaining, span)
        total += pages_in_tier * tier.price_per_page
        remaining -= pages_in_tier
        previous_cap = tier.up_to_page
    if remaining > 0:
        total += remaining * settings.after_last_tier_price
    return total


def _postage_amount(
    settings: CostSettings,
    postage_key: str | None,
    custom_postage: float | None,
) -> float:
    if custom_postage is not None:
        if custom_postage < 0:
            raise ValueError("custom_postage must be >= 0")
        return custom_postage
    if postage_key is None:
        return 0.0
    for option in settings.postage_options:
        if option.key == postage_key:
            return option.price
    raise ValueError(f"unknown postage_key: {postage_key}")


def calculate_costs(
    *,
    page_count: int,
    settings: CostSettings | None = None,
    postage_key: str | None = None,
    custom_postage: float | None = None,
) -> CostBreakdown:
    """Berechnet Pauschale + Kopierkosten + Versand.

    Args:
        page_count: Anzahl abrechenbarer Seiten (>= 0).
        settings: Kosteneinstellungen; Standardwerte wenn None.
        postage_key: Schlüssel einer PostageOption.
        custom_postage: Überschreibt postage_key, wenn gesetzt.

    Returns:
        CostBreakdown mit Einzelbeträgen und Summe.
    """
    if page_count < 0:
        raise ValueError("page_count must be >= 0")
    cfg = settings if settings is not None else CostSettings()
    copy_cost = _copy_cost(page_count, cfg)
    postage = _postage_amount(cfg, postage_key, custom_postage)
    flat = cfg.flat_fee
    return CostBreakdown(
        page_count=page_count,
        flat_fee=flat,
        copy_cost=copy_cost,
        postage=postage,
        total=flat + copy_cost + postage,
    )


DEFAULT_COST_SETTINGS = CostSettings()
