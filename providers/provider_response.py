from __future__ import annotations
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime

from constants import Retailer


class MoreBuyingChoices(BaseModel):
    heading: Optional[str] = None
    offer_text: Optional[str] = None
    offer_link: Optional[HttpUrl] = None


class ProductInfo(BaseModel):
    # Core
    product_id: str = Field(..., description="Retailer-specific ID (ASIN, Walmart ID, BestBuy SKU)")
    retailer: Retailer
    name: str
    url: HttpUrl
    image_url: Optional[HttpUrl] = None
    thumbnail: Optional[HttpUrl] = None

    # Pricing
    price: Optional[float] = None
    list_price: Optional[float] = None
    price_reduced: Optional[float] = None
    price_per_unit: Optional[float] = None
    typical_price: Optional[float] = None
    currency: Optional[str] = None
    currency_symbol: Optional[str] = None

    # Offers / promos
    offer_info: Optional[str] = None
    offer_msg: Optional[str] = None
    more_buying_choices: Optional[MoreBuyingChoices] = None

    # Ratings / reviews
    rating: Optional[float] = None
    total_ratings: Optional[int] = None
    total_reviews: Optional[int] = None

    # Stock / delivery
    in_stock: Optional[bool] = None
    is_prime: Optional[bool] = None
    is_sponsored: bool = False
    shipping_info: Optional[List[str]] = None
    est_delivery_date: Optional[datetime] = None

    # Seller / brand
    brand: Optional[str] = None
    seller_name: Optional[str] = None
    seller_info: Optional[str] = None
    retailer_badge: Optional[str] = None

    # Misc
    model_no: Optional[str] = None
    description: Optional[str] = None
    past_month_bought: Optional[str] = None
    variants: Optional[Dict[str, Any]] = None
    product_highlights: Optional[List[str]] = None

    @staticmethod
    def _parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(value, fmt)
                except Exception:
                    continue
        return None

    @classmethod
    def from_amazon(cls, d: Dict[str, Any]) -> ProductInfo:
        return cls(
            product_id=d.get("asin"),
            retailer=Retailer.Amazon,
            name=d.get("name") or "",
            url=d.get("url"),
            image_url=d.get("thumbnail"),
            thumbnail=d.get("thumbnail"),
            price=d.get("price"),
            list_price=d.get("list_price"),
            price_reduced=None,
            price_per_unit=d.get("price_per_unit"),
            typical_price=d.get("typical_price"),
            currency=d.get("currency"),
            currency_symbol=d.get("currency_symbol"),
            offer_info=d.get("offer_info"),
            rating=d.get("rating"),
            total_ratings=d.get("total_ratings"),
            is_prime=d.get("is_prime"),
            is_sponsored=bool(d.get("is_sponsored")),
            shipping_info=d.get("shipping_info"),
            brand=d.get("brand"),
            seller_info=d.get("seller_info"),
            retailer_badge=d.get("retailer_badge"),
            past_month_bought=d.get("past_month_bought"),
        )

    @classmethod
    def from_walmart(cls, d: Dict[str, Any]) -> ProductInfo:
        return cls(
            product_id=d.get("id"),
            retailer=Retailer.Walmart,
            name=d.get("name") or "",
            url=d.get("url"),
            image_url=d.get("image_url"),
            thumbnail=d.get("image_url"),
            price=d.get("price"),
            price_reduced=d.get("price_reduced"),
            currency=d.get("currency_code"),
            offer_msg=d.get("offer_msg"),
            rating=d.get("rating"),
            total_reviews=d.get("total_reviews"),
            in_stock=d.get("in_stock"),
            is_sponsored=bool(d.get("is_sponsored")),
            model_no=d.get("model_no"),
            description=d.get("description"),
            seller_name=d.get("seller_name"),
            variants=d.get("variants"),
            est_delivery_date=cls._parse_dt(d.get("est_delivery_date")),
        )

    @classmethod
    def from_bestbuy(cls, d: Dict[str, Any]) -> ProductInfo:
        return cls(
            product_id=d.get("id"),
            retailer=Retailer.BestBuy,
            name=d.get("name") or "",
            url=d.get("url"),
            image_url=d.get("thumbnail"),
            thumbnail=d.get("thumbnail"),
            price=d.get("price"),
            price_reduced=d.get("price_reduced"),
            currency=d.get("currency"),
            currency_symbol=d.get("currency_symbol"),
            rating=d.get("rating"),
            total_reviews=d.get("total_reviews"),
            model_no=d.get("model_no"),
            variants=d.get("variants"),
            product_highlights=d.get("product_highlights"),
        )
