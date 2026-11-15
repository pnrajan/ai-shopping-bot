"""Product catalog providers. One file per external source."""

from ai_shopping_bot.providers.base import CatalogProvider
from ai_shopping_bot.providers.fake import FakeProvider
from ai_shopping_bot.providers.unwrangle import UnWrangleProvider

__all__ = ["CatalogProvider", "FakeProvider", "UnWrangleProvider"]
