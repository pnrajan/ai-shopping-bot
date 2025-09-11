"""
Constants and Enumerations for InflectionCurator Shopping Assistant

This module contains all the constant values, enumerations, and configuration
mappings used throughout the InflectionCurator system. It defines the core
business logic for intent classification labels, supported retailers, product
categories, and their optimal platform relationships.

The constants defined here are used by:
- Intent classification system for understanding user behavior
- Product search providers for retailer selection
- Category-based routing for optimal shopping experiences
- Business logic for platform recommendations

Example Usage:
    from constants import (
        IntentLabels, Retailer, Categories, get_preferred_platform
    )

    # Check if user wants to shop
    if intent == IntentLabels.SHOPPING_INTENT:
        # Find best platforms for electronics
        platforms = get_preferred_platform(Categories.Electronics)
        # platforms = [Retailer.Amazon, Retailer.Walmart, Retailer.BestBuy]

Version:
    1.0.0

Authors:
    Inflection Team
"""

from enum import Enum
from typing import Final, List, Dict, Optional
import logging

# Configure module logger
logger = logging.getLogger(__name__)


class IntentLabels(str, Enum):
    """
    Enumeration of supported intent classification labels for the shopping
    assistant.

    These labels define the different types of user intentions that the system
    can recognize and respond to during conversational shopping interactions.

    The intent classification system uses these labels to:
    - Understand when users want to start shopping
    - Detect continued shopping interest
    - Recognize when users want to change topics or end the session

    Attributes:
        SHOPPING_INTENT: User expresses desire to purchase or find products.
                        Examples: "I need a new laptop", "Show me some shoes"

        SHOPPING_INTENT_CONTINUATION: User continues with existing shopping
            session. Examples: "Tell me more about this product",
            "Do you have it in blue?"

        DIGRESSION_INTENT: User wants to change topics or end shopping session.
            Examples: "Never mind", "Let's talk about something else",
            "I'm done shopping"

    Usage:
        # Check specific intent
        if predicted_label == IntentLabels.SHOPPING_INTENT:
            # Start product search workflow
            pass

        # Compare intents
        shopping_intents = [
            IntentLabels.SHOPPING_INTENT,
            IntentLabels.SHOPPING_INTENT_CONTINUATION
        ]
        if predicted_label in shopping_intents:
            # Continue shopping flow
            pass
    """

    SHOPPING_INTENT: str = "shopping_intent"
    """User expresses initial interest in shopping or purchasing products."""

    SHOPPING_INTENT_CONTINUATION: str = "shopping_continuation"
    """User continues with existing shopping conversation or requests more
    details."""

    DIGRESSION_INTENT: str = "digression_intent"
    """User wants to change topics, end shopping session, or discuss
    non-shopping matters."""

    @classmethod
    def is_shopping_related(cls, intent: str) -> bool:
        """
        Check if an intent label indicates shopping-related conversation.

        Args:
            intent (str): The intent label to check

        Returns:
            bool: True if the intent is shopping-related, False otherwise

        Example:
            is_shopping = IntentLabels.is_shopping_related(
                'shopping_intent'
            )  # True
            is_shopping = IntentLabels.is_shopping_related(
                'digression_intent'
            )  # False
        """
        shopping_intents = {cls.SHOPPING_INTENT, cls.SHOPPING_INTENT_CONTINUATION}
        return intent in shopping_intents

    @classmethod
    def get_all_labels(cls) -> list[str]:
        """
        Get all available intent labels as a list.

        Returns:
            List[str]: All intent labels

        Example:
            labels = IntentLabels.get_all_labels()
            # ['shopping_intent', 'shopping_continuation', 'digression_intent']
        """
        return [label.value for label in cls]


def get_intent_labels() -> list[str]:
    """
    Get the complete list of intent classification labels.

    This function provides backward compatibility and is used by the intent
    classification system to get all available labels for classification.

    Returns:
        List[str]: All available intent labels for classification

    Example:
        labels = get_intent_labels()
        # ['shopping_intent', 'shopping_continuation', 'digression_intent']

        # Use with classifier
        classifier.predict(user_input, labels=get_intent_labels())
    """
    return IntentLabels.get_all_labels()


class Retailer(str, Enum):
    """
    Enumeration of supported retail platforms and e-commerce providers.

    This enum defines all the retail platforms that InflectionCurator can
    search across for products. Each retailer has specific characteristics in
    terms of:
    - Product categories they excel in
    - API integration capabilities
    - Data quality and availability
    - User experience and features

    The system uses this enum to:
    - Route product searches to appropriate platforms
    - Handle retailer-specific data formats
    - Provide consistent retailer identification
    - Enable retailer-specific features and optimizations

    Attributes:
        Walmart: Walmart.com - Strong in groceries, household items,
            electronics
        Amazon: Amazon.com - Comprehensive marketplace with extensive product
            range
        BestBuy: BestBuy.com - Electronics and technology specialist
        WayFair: Wayfair.com - Home goods and furniture specialist
    """

    Walmart: Final = "Walmart"
    """Walmart.com - Major retailer with strong grocery, household, and
    general merchandise."""

    Amazon: Final = "Amazon"
    """Amazon.com - Comprehensive marketplace with the largest product
    selection."""

    BestBuy: Final = "BestBuy"
    """BestBuy.com - Electronics and technology specialist retailer."""

    WayFair: Final = "WayFair"
    """Wayfair.com - Home goods, furniture, and home improvement specialist."""

    @classmethod
    def get_all_retailers(cls) -> list[str]:
        """
        Get all supported retailer names.

        Returns:
            List[str]: All supported retailer names

        Example:
            retailers = Retailer.get_all_retailers()
            # ['Walmart', 'Amazon', 'BestBuy', 'WayFair']
        """
        return [retailer.value for retailer in cls]

    @classmethod
    def is_supported_retailer(cls, retailer_name: str) -> bool:
        """
        Check if a retailer is supported by the system.

        Args:
            retailer_name (str): Name of the retailer to check

        Returns:
            bool: True if retailer is supported, False otherwise

        Example:
            is_supported = Retailer.is_supported_retailer('Amazon')  # True
            is_supported = Retailer.is_supported_retailer('Target')  # False
        """
        return retailer_name in cls.get_all_retailers()

    def get_retailer_info(self) -> dict[str, str]:
        """
        Get detailed information about this retailer.

        Returns:
            Dict[str, str]: Retailer information including specialties and
                characteristics
        """
        retailer_info = {
            self.Walmart: {
                "name": "Walmart",
                "url": "walmart.com",
                "specialties": [
                    "Groceries",
                    "Household Items",
                    "Electronics",
                    "Clothing",
                ],
                "characteristics": "Large selection with competitive prices",
            },
            self.Amazon: {
                "name": "Amazon",
                "url": "amazon.com",
                "specialties": ["Everything", "Electronics", "Books", "Prime Benefits"],
                "characteristics": ("Largest selection with fast delivery options"),
            },
            self.BestBuy: {
                "name": "Best Buy",
                "url": "bestbuy.com",
                "specialties": ["Electronics", "Technology", "Gaming", "Appliances"],
                "characteristics": "Technology specialist with expert advice",
            },
            self.WayFair: {
                "name": "Wayfair",
                "url": "wayfair.com",
                "specialties": ["Furniture", "Home Decor", "Home Improvement"],
                "characteristics": (
                    "Home goods specialist with extensive furniture selection"
                ),
            },
        }
        return retailer_info.get(self, {})


class PersonaType(str, Enum):
    """
    This class adds the support for different personas
    """

    SHOPPER: Final = "SHOPPER"


class ShoppingCategories(str, Enum):
    """
    Enumeration of supported product categories for intelligent retailer
    routing.

    This enum defines the main product categories that InflectionCurator
    recognizes and can optimize retailer selection for. Each category has
    preferred retailers that typically offer the best selection, prices, or
    expertise in that area.

    The category system enables:
    - Smart retailer selection based on product type
    - Optimized search strategies per category
    - Category-specific features and recommendations
    - Specialized handling of different product types

    Attributes:
        Electronics: Technology products, gadgets, computers, phones, etc.
        Apparel: Clothing, shoes, accessories, fashion items
        Furniture: Home furniture, home decor, large household items
    """

    Electronics: Final = "Electronics"
    """Technology products including computers, phones, gaming, audio, and
    electronics."""

    Apparel: Final = "Apparel"
    """Clothing, shoes, accessories, and fashion-related products."""

    Furniture: Final = "Furniture"
    """Home furniture, decor, large household items, and home improvement
    products."""

    @classmethod
    def get_all_categories(cls) -> list[str]:
        """
        Get all supported product categories.

        Returns:
            List[str]: All supported category names

        Example:
            categories = Categories.get_all_categories()
            # ['Electronics', 'Apparel', 'Furniture']
        """
        return [category.value for category in cls]

    @classmethod
    def is_supported_category(cls, category_name: str) -> bool:
        """
        Check if a product category is supported.

        Args:
            category_name (str): Name of the category to check

        Returns:
            bool: True if category is supported, False otherwise

        Example:
            is_supported = Categories.is_supported_category(
                'Electronics'
            )  # True
            is_supported = Categories.is_supported_category('Books')  # False
        """
        return category_name in cls.get_all_categories()

    def get_category_keywords(self) -> list[str]:
        """
        Get typical keywords associated with this category.

        Returns:
            List[str]: Common keywords that might indicate this category

        Example:
            keywords = Categories.Electronics.get_category_keywords()
            # ['laptop', 'phone', 'computer', 'tablet', 'headphones', ...]
        """
        category_keywords = {
            self.Electronics: [
                "laptop",
                "computer",
                "phone",
                "tablet",
                "headphones",
                "speaker",
                "gaming",
                "console",
                "camera",
                "tv",
                "monitor",
                "keyboard",
                "mouse",
                "electronics",
                "gadget",
                "device",
                "tech",
                "smart",
            ],
            self.Apparel: [
                "shirt",
                "pants",
                "dress",
                "shoes",
                "jacket",
                "sweater",
                "jeans",
                "clothing",
                "fashion",
                "wear",
                "outfit",
                "style",
                "sneakers",
                "boots",
                "hat",
                "accessories",
                "jewelry",
                "watch",
            ],
            self.Furniture: [
                "chair",
                "table",
                "sofa",
                "bed",
                "desk",
                "dresser",
                "furniture",
                "home",
                "decor",
                "lamp",
                "rug",
                "cabinet",
                "bookshelf",
                "mattress",
                "couch",
                "dining",
                "bedroom",
                "living",
            ],
        }
        return category_keywords.get(self, [])


# Platform-Category Optimization Mapping
# Mapping of product categories to their preferred retail platforms.
# This mapping is based on:
# - Retailer specialization and expertise
# - Product selection and availability
# - Pricing competitiveness
# - User experience quality
# - API data quality and completeness
RETAILER_CATEGORY_MAPPING: dict[str, list[Retailer]] = {
    ShoppingCategories.Apparel: [Retailer.Amazon, Retailer.Walmart],
    ShoppingCategories.Electronics: [
        Retailer.Amazon,
        Retailer.Walmart,
        Retailer.BestBuy,
    ],
    ShoppingCategories.Furniture: [Retailer.Amazon, Retailer.WayFair],
}


def get_preferred_platform(category: str) -> list[Retailer]:
    """
    Get the preferred retail platforms for a specific product category.

    This function implements the core business logic for retailer selection
    based on product categories. It returns an ordered list of retailers that
    typically provide the best experience, selection, and pricing for the
    given category.

    The selection is based on:
    - Retailer expertise and specialization in the category
    - Product selection breadth and depth
    - Competitive pricing and deals
    - API data quality and completeness
    - User experience and features

    Args:
        category (str): The product category to get platforms for.
                       Should match one of the Categories enum values.

    Returns:
        List[Retailer]: Ordered list of preferred retailers for the category.
                       First retailer is the most preferred.

    Example:
        # Get best platforms for electronics
        platforms = get_preferred_platform('Electronics')
        # [Retailer.Amazon, Retailer.Walmart, Retailer.BestBuy]

        # Get best platforms for furniture
        platforms = get_preferred_platform('Furniture')
        # [Retailer.Amazon, Retailer.WayFair]

        # Unknown category defaults to Amazon
        platforms = get_preferred_platform('Books')
        # [Retailer.Amazon]

    Note:
        If the category is not recognized, returns [Retailer.Amazon] as a safe
        default since Amazon has the broadest product selection across all
        categories.
    """
    # Convert string to Categories enum if possible
    category_key = category

    # Handle both string and enum inputs
    if isinstance(category, str):
        try:
            # Try to match as Categories enum value
            if hasattr(ShoppingCategories, category):
                category_key = getattr(ShoppingCategories, category).value
            elif category in ShoppingCategories.get_all_categories():
                category_key = category
        except (AttributeError, ValueError):
            logger.warning(f"Unknown category '{category}', defaulting to Amazon")
            return [Retailer.Amazon]

    # Get preferred platforms from mapping
    preferred_platforms = RETAILER_CATEGORY_MAPPING.get(category_key)

    if preferred_platforms:
        logger.debug(
            f"Found {len(preferred_platforms)} preferred platforms for "
            f"category '{category}'"
        )
        return preferred_platforms
    else:
        # Default fallback to Amazon for unknown categories
        logger.info(
            f"No specific platforms configured for category '{category}', "
            f"using Amazon as default"
        )
        return [Retailer.Amazon]


def get_category_retailer_matrix() -> dict[str, list[str]]:
    """
    Get a complete matrix of categories and their preferred retailers.

    Returns:
        Dict[str, List[str]]: Dictionary mapping category names to retailer
            lists

    Example:
        matrix = get_category_retailer_matrix()
        # {
        #     'Electronics': ['Amazon', 'Walmart', 'BestBuy'],
        #     'Apparel': ['Amazon', 'Walmart'],
        #     'Furniture': ['Amazon', 'WayFair']
        # }
    """
    return {
        category: [retailer.value for retailer in retailers]
        for category, retailers in RETAILER_CATEGORY_MAPPING.items()
    }


def suggest_category_from_keywords(keywords: list[str]) -> str | None:
    """
    Suggest a product category based on keywords found in user input.

    This function analyzes a list of keywords and attempts to determine the
    most likely product category based on keyword matching with category
    vocabularies.

    Args:
        keywords (List[str]): List of keywords extracted from user input

    Returns:
        Optional[str]: Suggested category name, or None if no clear match

    Example:
        category = suggest_category_from_keywords(
            ['laptop', 'computer', 'gaming']
        )
        # 'Electronics'

        category = suggest_category_from_keywords(
            ['shirt', 'clothing', 'fashion']
        )
        # 'Apparel'
    """
    if not keywords:
        return None

    # Convert keywords to lowercase for matching
    lower_keywords = [kw.lower() for kw in keywords]

    # Score each category based on keyword matches
    category_scores = {}

    for category in ShoppingCategories:
        category_keywords = category.get_category_keywords()
        matches = sum(1 for kw in lower_keywords if kw in category_keywords)
        if matches > 0:
            category_scores[category.value] = matches

    # Return category with highest score
    if category_scores:
        best_category = max(category_scores, key=category_scores.get)
        logger.debug(
            f"Suggested category '{best_category}' based on keywords: " f"{keywords}"
        )
        return best_category

    return None
