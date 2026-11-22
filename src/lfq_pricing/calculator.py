"""Pure financial calculations using Python Decimal for exact rounding and precision."""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


class PricingCalculationError(Exception):
    """Raised when calculation inputs violate financial boundaries."""


def quantize_money(amount: Decimal) -> Decimal:
    """Round currency amount to nearest cent using ROUND_HALF_UP."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def quantize_ratio(ratio: Decimal) -> Decimal:
    """Round margin/markup ratio to four decimal places."""
    return ratio.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def calculate_gross_margin(price: Decimal, cost: Decimal) -> Decimal:
    """Calculate gross margin: (price - cost) / price.

    Requires price > 0.
    """
    if price <= Decimal("0.00"):
        raise PricingCalculationError(
            f"Cannot calculate gross margin for non-positive price: {price}"
        )
    margin = (price - cost) / price
    return quantize_ratio(margin)


def calculate_markup(price: Decimal, cost: Decimal) -> Decimal:
    """Calculate markup: (price - cost) / cost.

    Requires cost > 0. If cost is zero, markup is undefined.
    """
    if cost <= Decimal("0.00"):
        raise PricingCalculationError(f"Cannot calculate markup for non-positive cost: {cost}")
    markup = (price - cost) / cost
    return quantize_ratio(markup)


def calculate_target_margin_price(cost: Decimal, target_margin: Decimal) -> Decimal:
    """Calculate price to achieve target gross margin: cost / (1 - target_margin).

    Requires cost >= 0 and 0.00 <= target_margin < 1.00.
    """
    if target_margin < Decimal("0.00") or target_margin >= Decimal("1.00"):
        raise PricingCalculationError(
            f"Target margin must be in range [0.00, 1.00); received {target_margin}"
        )
    if cost < Decimal("0.00"):
        raise PricingCalculationError(f"Cost cannot be negative: {cost}")

    divisor = Decimal("1.00") - target_margin
    calculated_price = cost / divisor
    return quantize_money(calculated_price)


def clamp_price(
    price: Decimal,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
) -> tuple[Decimal, list[str]]:
    """Enforce minimum and maximum price constraints."""
    warnings: list[str] = []
    final_price = price

    if min_price is not None and final_price < min_price:
        warnings.append(
            f"Price clamped to configured minimum price {min_price} (was {final_price})"
        )
        final_price = min_price

    if max_price is not None and final_price > max_price:
        warnings.append(
            f"Price clamped to configured maximum price {max_price} (was {final_price})"
        )
        final_price = max_price

    return quantize_money(final_price), warnings
