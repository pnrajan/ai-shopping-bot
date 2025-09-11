"""Product Response Models for Inflection Curator.

This module defines the standardized data models for representing product
information from various retail platforms. It provides a unified structure for
product data, ensuring consistency and type safety when handling information
from different sources.

Key Features:
    - Unified product data model (`ProductInfo`) for all retailers.
    - Type-safe Pydantic models with validation.
    - Retailer-specific data transformation methods (e.g., `from_amazon`).
    - Comprehensive product information fields.

Example:
    >>> from inflection_curator.providers import ProductInfo
    >>> amazon_data = {
    ...     "asin": "B08N5WRWNW",
    ...     "name": "Sony WH-1000XM4 Headphones",
    ...     "price": 279.99,
    ...     "url": "https://amazon.com/dp/B08N5WRWNW"
    ... }
    >>> product = ProductInfo.from_amazon(amazon_data)
    >>> print(product.name)
    Sony WH-1000XM4 Headphones
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, HttpUrl, Field, validator
from datetime import datetime
import logging

from ..constants import Retailer

# Configure module logger
logger = logging.getLogger(__name__)


class MoreBuyingChoices(BaseModel):
    """Model for additional purchasing options and offers.

    This model captures alternative purchasing options that retailers often
    provide, such as different sellers, bulk discounts, or special promotions.

    Attributes:
        heading (Optional[str]): The title or category for the buying options.
        offer_text (Optional[str]): A description of the alternative offer.
        offer_link (Optional[HttpUrl]): A URL to view the alternative offers.
    """

    heading: str | None = Field(
        None, description="Title or category for buying options"
    )

    offer_text: str | None = Field(
        None, description="Description of alternative offers"
    )

    offer_link: HttpUrl | None = Field(
        None, description="URL to view alternative purchasing options"
    )

    class Config:
        """Pydantic configuration for the MoreBuyingChoices model."""

        schema_extra = {
            "example": {
                "heading": "Other Sellers and Prices",
                "offer_text": "3 new from $29.99",
                "offer_link": "https://amazon.com/gp/offer-listing/B08N5WRWNW",
            }
        }


class ProductInfo(BaseModel):
    """Comprehensive product information model for multi-retailer data.

    This is the central data model for representing product information across
    all supported retailers. It provides a standardized structure that normalizes
    the different data formats from various platforms into a consistent
    interface.

    Attributes:
        product_id (str): The retailer-specific unique identifier.
        retailer (Retailer): The retail platform where the product is sold.
        name (str): The product name or title.
        url (HttpUrl): The direct URL to the product page.
        image_url (Optional[HttpUrl]): The URL to the main product image.
        thumbnail (Optional[HttpUrl]): The URL to a smaller thumbnail image.
        price (Optional[float]): The current selling price.
        list_price (Optional[float]): The original or manufacturer's suggested
            retail price (MSRP).
        currency (Optional[str]): The currency code (e.g., "USD").
        rating (Optional[float]): The average customer rating.
        in_stock (Optional[bool]): Whether the product is currently available.
    """

    # ========================================
    # Core Product Information
    # ========================================

    product_id: str = Field(
        ...,
        description="Retailer-specific unique identifier "
        "(ASIN, Walmart ID, BestBuy SKU, etc.)",
        min_length=1,
        max_length=50,
    )

    retailer: Retailer = Field(
        ..., description="The retail platform where this product is sold"
    )

    name: str = Field(
        ..., description="Product name or title", min_length=1, max_length=500
    )

    url: HttpUrl = Field(
        ...,
        description="Direct URL to the product page on the retailer's website",
    )

    image_url: HttpUrl | None = Field(
        None, description="URL to the main product image"
    )

    thumbnail: HttpUrl | None = Field(
        None, description="URL to a smaller thumbnail image"
    )

    # ========================================
    # Pricing Information
    # ========================================

    price: float | None = Field(None, description="Current selling price", ge=0.0)

    list_price: float | None = Field(
        None,
        description="Original or manufacturer's suggested retail price (MSRP)",
        ge=0.0,
    )

    price_reduced: float | None = Field(
        None, description="Previous price before current discount", ge=0.0
    )

    price_per_unit: float | None = Field(
        None,
        description="Price per unit of measurement (per oz, per lb, etc.)",
        ge=0.0,
    )

    typical_price: float | None = Field(
        None,
        description="Typical price range or historical average price",
        ge=0.0,
    )

    currency: str | None = Field(
        None, description="Currency code (USD, EUR, CAD, etc.)", max_length=3
    )

    currency_symbol: str | None = Field(
        None, description="Currency symbol ($, €, £, etc.)", max_length=3
    )

    # ========================================
    # Offers and Promotions
    # ========================================

    offer_info: str | None = Field(
        None,
        description="Information about current offers or promotions",
        max_length=200,
    )

    offer_msg: str | None = Field(
        None,
        description="Promotional message or special deal information",
        max_length=200,
    )

    more_buying_choices: MoreBuyingChoices | None = Field(
        None,
        description="Alternative purchasing options from different sellers",
    )

    # ========================================
    # Ratings and Reviews
    # ========================================

    rating: float | None = Field(
        None,
        description="Average customer rating (typically 0-5 scale)",
        ge=0.0,
        le=5.0,
    )

    total_ratings: int | None = Field(
        None, description="Total number of customer ratings", ge=0
    )

    total_reviews: int | None = Field(
        None, description="Total number of written customer reviews", ge=0
    )

    # ========================================
    # Stock and Delivery Information
    # ========================================

    in_stock: bool | None = Field(
        None,
        description="Whether the product is currently available for purchase",
    )

    is_prime: bool | None = Field(
        None,
        description="Whether the product is eligible for Amazon Prime shipping",
    )

    is_sponsored: bool = Field(
        False,
        description="Whether this is a sponsored/promoted product listing",
    )

    shipping_info: list[str] | None = Field(
        None,
        description="List of shipping options and information",
        max_items=10,
    )

    est_delivery_date: datetime | None = Field(
        None, description="Estimated delivery date"
    )

    # ========================================
    # Seller and Brand Information
    # ========================================

    brand: str | None = Field(
        None, description="Product brand or manufacturer name", max_length=100
    )

    seller_name: str | None = Field(
        None,
        description="Name of the seller (may differ from retailer)",
        max_length=100,
    )

    seller_info: str | None = Field(
        None,
        description="Additional information about the seller",
        max_length=200,
    )

    retailer_badge: str | None = Field(
        None,
        description="Special badges or certifications from the retailer",
        max_length=50,
    )

    # ========================================
    # Miscellaneous Product Details
    # ========================================

    model_no: str | None = Field(
        None, description="Manufacturer model number or SKU", max_length=50
    )

    description: str | None = Field(
        None, description="Detailed product description", max_length=2000
    )

    past_month_bought: str | None = Field(
        None,
        description="Information about recent purchase volume",
        max_length=50,
    )

    variants: dict[str, Any] | None = Field(
        None,
        description="Available product variants (colors, sizes, configurations)",
    )

    product_highlights: list[str] | None = Field(
        None, description="Key product features and highlights", max_items=20
    )

    class Config:
        """Pydantic model configuration."""

        use_enum_values = True
        validate_assignment = True
        extra = "ignore"  # Ignore extra fields from API responses
        schema_extra = {
            "example": {
                "product_id": "B08N5WRWNW",
                "retailer": "Amazon",
                "name": "Sony WH-1000XM4 Wireless Premium Noise Canceling "
                "Overhead Headphones",
                "url": "https://amazon.com/dp/B08N5WRWNW",
                "price": 279.99,
                "list_price": 349.99,
                "currency": "USD",
                "currency_symbol": "$",
                "rating": 4.5,
                "total_ratings": 73251,
                "in_stock": True,
                "is_prime": True,
                "brand": "Sony",
            }
        }

    @validator("price", "list_price", "price_reduced", "typical_price", pre=True)
    def validate_prices(cls, v: Any) -> float | None:
        """Validates and cleans price values.

        Args:
            v: The price value to validate.

        Returns:
            The validated price as a float, or `None` if invalid.
        """
        if v is None:
            return v
        try:
            # Convert string prices to float
            if isinstance(v, str):
                # Remove currency symbols and whitespace
                cleaned = v.replace("$", "").replace(",", "").strip()
                if cleaned:
                    return float(cleaned)
            elif isinstance(v, (int, float)):
                return float(v)
        except (ValueError, TypeError):
            logger.warning(f"Invalid price value: {v}")
        return None

    @validator("rating", pre=True)
    def validate_rating(cls, v: Any) -> float | None:
        """Validates rating values.

        Args:
            v: The rating value to validate.

        Returns:
            The validated rating as a float, or `None` if invalid.
        """
        if v is None:
            return v
        try:
            rating = float(v)
            # Clamp rating between 0 and 5
            return max(0.0, min(5.0, rating))
        except (ValueError, TypeError):
            logger.warning(f"Invalid rating value: {v}")
            return None

    @property
    def has_discount(self) -> bool:
        """Checks if the product has a discount from the list price."""
        return bool(self.price and self.list_price and self.price < self.list_price)

    @property
    def discount_percentage(self) -> float | None:
        """Calculates the discount percentage from the list price."""
        if not self.has_discount:
            return None
        return round(((self.list_price - self.price) / self.list_price) * 100, 1)

    @property
    def display_price(self) -> str:
        """Gets a formatted price for display."""
        if not self.price:
            return "Price not available"

        symbol = self.currency_symbol or "$"
        return f"{symbol}{self.price:.2f}"

    @property
    def display_rating(self) -> str:
        """Gets a formatted rating for display."""
        if not self.rating:
            return "No rating"

        stars = "★" * int(self.rating) + "☆" * (5 - int(self.rating))
        rating_text = f"{stars} {self.rating}/5"

        if self.total_ratings:
            rating_text += f" ({self.total_ratings:,} reviews)"

        return rating_text

    def get_key_info(self) -> dict[str, Any]:
        """Gets essential product information for a quick display."""
        return {
            "name": self.name,
            "price": self.display_price,
            "rating": self.display_rating,
            "retailer": self.retailer.value,
            "in_stock": (self.in_stock if self.in_stock is not None else "Unknown"),
            "url": str(self.url),
        }

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        """Parses datetime strings from various retailer formats.

        This utility method handles the different datetime formats that various
        retailers use in their APIs. It attempts multiple parsing strategies
        to handle ISO formats, timezone indicators, and common variations.

        Args:
            value: The date/time string to parse.

        Returns:
            A parsed `datetime` object, or `None` if parsing fails.
        """
        if not value:
            return None

        try:
            # Try ISO format with timezone replacement
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            # Try common datetime formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with microseconds and Z
                "%Y-%m-%dT%H:%M:%SZ",  # ISO with Z
                "%Y-%m-%dT%H:%M:%S",  # ISO without timezone
                "%Y-%m-%d %H:%M:%S",  # Space-separated
                "%Y-%m-%d",  # Date only
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)
                except (ValueError, TypeError):
                    continue

        logger.warning(f"Could not parse datetime: {value}")
        return None

    @classmethod
    def from_amazon(cls, d: dict[str, Any]) -> ProductInfo:
        """Creates a `ProductInfo` object from Amazon API response data.

        This factory method transforms a raw Amazon product data dictionary into a
        standardized `ProductInfo` object. It handles Amazon's specific field
        naming conventions and data structures.

        Args:
            d: The raw product data dictionary from the Amazon API.

        Returns:
            A standardized `ProductInfo` object.

        Raises:
            ValueError: If the provided data is invalid.
        """
        try:
            return cls(
                product_id=d.get("asin", ""),
                retailer=Retailer.Amazon,
                name=d.get("name", ""),
                url=d.get("url", ""),
                image_url=d.get("image_url") or d.get("thumbnail"),
                thumbnail=d.get("thumbnail"),
                price=d.get("price"),
                list_price=d.get("list_price"),
                price_per_unit=d.get("price_per_unit"),
                typical_price=d.get("typical_price"),
                currency=d.get("currency"),
                currency_symbol=d.get("currency_symbol"),
                offer_info=d.get("offer_info"),
                rating=d.get("rating"),
                total_ratings=d.get("total_ratings"),
                is_prime=d.get("is_prime"),
                is_sponsored=bool(d.get("is_sponsored", False)),
                shipping_info=d.get("shipping_info"),
                brand=d.get("brand"),
                seller_info=d.get("seller_info"),
                retailer_badge=d.get("retailer_badge"),
                past_month_bought=d.get("past_month_bought"),
            )
        except Exception as e:
            logger.error(f"Error creating ProductInfo from Amazon data: {e}")
            raise ValueError(f"Invalid Amazon product data: {e}")

    @classmethod
    def from_walmart(cls, d: dict[str, Any]) -> ProductInfo:
        """Creates a `ProductInfo` object from Walmart API response data.

        This factory method transforms a raw Walmart product data dictionary into a
        standardized `ProductInfo` object. It handles Walmart's specific field
        naming conventions and data structures.

        Args:
            d: The raw product data dictionary from the Walmart API.

        Returns:
            A standardized `ProductInfo` object.

        Raises:
            ValueError: If the provided data is invalid.
        """
        try:
            return cls(
                product_id=d.get("id", ""),
                retailer=Retailer.Walmart,
                name=d.get("name", ""),
                url=d.get("url", ""),
                image_url=d.get("image_url"),
                thumbnail=d.get("image_url"),  # Walmart often uses same URL
                # for both
                price=d.get("price"),
                price_reduced=d.get("price_reduced"),
                currency=d.get("currency_code", "USD"),
                offer_msg=d.get("offer_msg"),
                rating=d.get("rating"),
                total_reviews=d.get("total_reviews"),
                in_stock=d.get("in_stock"),
                is_sponsored=bool(d.get("is_sponsored", False)),
                model_no=d.get("model_no"),
                description=d.get("description"),
                seller_name=d.get("seller_name"),
                variants=d.get("variants"),
                est_delivery_date=cls._parse_dt(d.get("est_delivery_date")),
            )
        except Exception as e:
            logger.error(f"Error creating ProductInfo from Walmart data: {e}")
            raise ValueError(f"Invalid Walmart product data: {e}")

    @classmethod
    def from_bestbuy(cls, d: dict[str, Any]) -> ProductInfo:
        """Creates a `ProductInfo` object from BestBuy API response data.

        This factory method transforms a raw BestBuy product data dictionary into a
        standardized `ProductInfo` object. It handles BestBuy's specific field
        naming conventions and data structures.

        Args:
            d: The raw product data dictionary from the BestBuy API.

        Returns:
            A standardized `ProductInfo` object.

        Raises:
            ValueError: If the provided data is invalid.
        """
        try:
            return cls(
                product_id=d.get("id", ""),
                retailer=Retailer.BestBuy,
                name=d.get("name", ""),
                url=d.get("url", ""),
                image_url=d.get("image_url") or d.get("thumbnail"),
                thumbnail=d.get("thumbnail"),
                price=d.get("price"),
                price_reduced=d.get("price_reduced"),
                currency=d.get("currency", "USD"),
                currency_symbol=d.get("currency_symbol"),
                rating=d.get("rating"),
                total_reviews=d.get("total_reviews"),
                model_no=d.get("model_no"),
                brand=d.get("brand"),
                variants=d.get("variants"),
                product_highlights=d.get("product_highlights"),
                is_sponsored=bool(d.get("is_sponsored", False)),
            )
        except Exception as e:
            logger.error(f"Error creating ProductInfo from BestBuy data: {e}")
            raise ValueError(f"Invalid BestBuy product data: {e}")

    @classmethod
    def from_wayfair(cls, d: dict[str, Any]) -> ProductInfo:
        """Creates a `ProductInfo` object from Wayfair API response data.

        This factory method transforms a raw Wayfair product data dictionary into a
        standardized `ProductInfo` object. It handles Wayfair's specific field
        naming conventions for furniture and home goods.

        Note:
            This method is a placeholder for future Wayfair API integration.

        Args:
            d: The raw product data dictionary from the Wayfair API.

        Returns:
            A standardized `ProductInfo` object.

        Raises:
            ValueError: If the provided data is invalid.
        """
        try:
            return cls(
                product_id=d.get("id", ""),
                retailer=Retailer.WayFair,
                name=d.get("name", ""),
                url=d.get("url", ""),
                image_url=d.get("image_url"),
                thumbnail=d.get("thumbnail"),
                price=d.get("price"),
                list_price=d.get("list_price"),
                currency=d.get("currency", "USD"),
                rating=d.get("rating"),
                total_reviews=d.get("total_reviews"),
                in_stock=d.get("in_stock"),
                brand=d.get("brand"),
                description=d.get("description"),
                product_highlights=d.get(
                    "features"
                ),  # Wayfair might use 'features' instead
                is_sponsored=bool(d.get("is_sponsored", False)),
            )
        except Exception as e:
            logger.error(f"Error creating ProductInfo from Wayfair data: {e}")
            raise ValueError(f"Invalid Wayfair product data: {e}")

    def to_dict(self) -> dict[str, Any]:
        """Converts the `ProductInfo` object to a dictionary.

        Returns:
            A dictionary representation of the product data.
        """
        return self.dict(exclude_none=True)

    def to_json(self) -> str:
        """Converts the `ProductInfo` object to a JSON string.

        Returns:
            A JSON representation of the product data.
        """
        return self.json(exclude_none=True)
