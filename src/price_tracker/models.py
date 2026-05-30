from dataclasses import dataclass


@dataclass(frozen=True)
class Listing:
    """A single product offer scraped from a marketplace."""

    marketplace: str
    title: str
    url: str
    price_cents: int | None
    currency: str = "BRL"

    @property
    def price(self) -> float | None:
        return None if self.price_cents is None else self.price_cents / 100
