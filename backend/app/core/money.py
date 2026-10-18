"""Money helpers. All arithmetic uses Decimal; floats are never used for prices.

Conversion strategy (documented in docs/ARCHITECTURE.md):
  * Rupee amounts are Decimal with 2 decimal places, stored as DECIMAL(12,2).
  * Gateway amounts are integer paise: paise = int((rupees * 100).quantize(1, ROUND_HALF_UP)).
  * paise -> rupees: Decimal(paise) / 100, quantized to 0.01.
"""
from decimal import ROUND_HALF_UP, Decimal

TWO = Decimal("0.01")
ZERO = Decimal("0.00")


def D(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        value = repr(value)
    return Decimal(str(value))


def q(value) -> Decimal:
    return D(value).quantize(TWO, rounding=ROUND_HALF_UP)


def to_paise(rupees) -> int:
    return int((D(rupees) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_paise(paise: int) -> Decimal:
    return q(Decimal(paise) / 100)


def discount_pct(mrp, price) -> int:
    mrp, price = D(mrp), D(price)
    if mrp <= 0 or price >= mrp:
        return 0
    return int(((mrp - price) / mrp * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def tax_from_inclusive(amount, rate) -> Decimal:
    """GST component contained in a tax-inclusive amount."""
    amount, rate = D(amount), D(rate)
    if rate <= 0:
        return ZERO
    return q(amount * rate / (Decimal(100) + rate))


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` across weights proportionally; rounding remainder goes to the largest weight."""
    total = q(total)
    s = sum(weights, Decimal(0))
    if s <= 0 or total == 0:
        return [ZERO for _ in weights]
    parts = [q(total * w / s) for w in weights]
    diff = total - sum(parts, Decimal(0))
    if diff:
        i = max(range(len(weights)), key=lambda k: weights[k])
        parts[i] = q(parts[i] + diff)
    return parts
