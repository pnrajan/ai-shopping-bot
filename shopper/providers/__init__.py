"""Product catalog providers. One file per external source."""

from shopper.providers.base import CatalogProvider
from shopper.providers.fake import FakeProvider
from shopper.providers.unwrangle import UnWrangleProvider

__all__ = ["CatalogProvider", "FakeProvider", "UnWrangleProvider"]
