from enum import Enum
from typing import Final


class IntentLabels(str, Enum):
    SHOPPING_INTENT: str = 'shopping_intent'  # user wants to shop
    SHOPPING_INTENT_CONTINUATION: str = 'shopping_continuation'  # user is continuing with shopping intent
    DIGRESSION_INTENT: str = 'digression_intent'  # the user wants to digress from the conversation


def get_intent_labels():
    """
    Get the common intent labels
    :return:
    """
    return [el for el in IntentLabels]


class Retailer(str, Enum):
    Walmart: Final = 'Walmart'
    Amazon: Final = 'Amazon'
    BestBuy: Final = 'BestBuy'
    WayFair: Final = 'WayFair'


class Categories(str, Enum):
    Electronics: Final = 'Electronics'
    Apparel: Final = 'Apparel'
    Furniture: Final = 'Furniture'


def get_preferred_platform(category: str):
    if category == Categories.Apparel:
        return [Retailer.Amazon, Retailer.Walmart]
    elif category == Categories.Electronics:
        return [Retailer.Amazon, Retailer.Walmart, Retailer.BestBuy]
    elif category == Categories.Furniture:
        return [Retailer.Amazon, Retailer.WayFair]
    else:
        return [Retailer.Amazon]
