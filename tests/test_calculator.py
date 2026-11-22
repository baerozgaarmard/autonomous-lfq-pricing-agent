"""Unit tests for pricing formulas, Decimal rounding, and boundary enforcement."""

from decimal import Decimal

import pytest

from lfq_pricing.calculator import (
    PricingCalculationError,
    calculate_gross_margin,
    calculate_markup,
    calculate_target_margin_price,
    clamp_price,
    quantize_money,
)


def test_gross_margin_calculation() -> None:
    # (200 - 150) / 200 = 50 / 200 = 0.2500
    margin = calculate_gross_margin(Decimal("200.00"), Decimal("150.00"))
    assert margin == Decimal("0.2500")

    # Non-positive price raises error
    with pytest.raises(PricingCalculationError):
        calculate_gross_margin(Decimal("0.00"), Decimal("50.00"))
    with pytest.raises(PricingCalculationError):
        calculate_gross_margin(Decimal("-10.00"), Decimal("50.00"))


def test_markup_calculation() -> None:
    # (200 - 150) / 150 = 50 / 150 = 0.3333
    markup = calculate_markup(Decimal("200.00"), Decimal("150.00"))
    assert markup == Decimal("0.3333")

    # Zero or negative cost raises error
    with pytest.raises(PricingCalculationError):
        calculate_markup(Decimal("100.00"), Decimal("0.00"))


def test_target_margin_price() -> None:
    # cost = 120, margin = 0.30 => 120 / (1 - 0.30) = 120 / 0.70 = 171.42857... => 171.43
    price = calculate_target_margin_price(Decimal("120.00"), Decimal("0.30"))
    assert price == Decimal("171.43")

    # Impossible margin >= 1.0
    with pytest.raises(PricingCalculationError):
        calculate_target_margin_price(Decimal("100.00"), Decimal("1.00"))
    with pytest.raises(PricingCalculationError):
        calculate_target_margin_price(Decimal("100.00"), Decimal("1.20"))
    with pytest.raises(PricingCalculationError):
        calculate_target_margin_price(Decimal("100.00"), Decimal("-0.10"))

    # Negative cost
    with pytest.raises(PricingCalculationError):
        calculate_target_margin_price(Decimal("-50.00"), Decimal("0.20"))


def test_clamp_price_boundaries() -> None:
    # Within bounds
    price, warnings = clamp_price(
        Decimal("180.00"), min_price=Decimal("150.00"), max_price=Decimal("200.00")
    )
    assert price == Decimal("180.00")
    assert len(warnings) == 0

    # Below min
    price_low, warnings_low = clamp_price(Decimal("120.00"), min_price=Decimal("150.00"))
    assert price_low == Decimal("150.00")
    assert len(warnings_low) == 1
    assert "minimum price" in warnings_low[0]

    # Above max
    price_high, warnings_high = clamp_price(Decimal("250.00"), max_price=Decimal("200.00"))
    assert price_high == Decimal("200.00")
    assert len(warnings_high) == 1
    assert "maximum price" in warnings_high[0]


def test_decimal_rounding_half_up() -> None:
    assert quantize_money(Decimal("100.005")) == Decimal("100.01")
    assert quantize_money(Decimal("100.004")) == Decimal("100.00")
