"""Product Catalog Providers for Inflection Curator.

This module implements the product search and data retrieval system that
connects to various retail APIs to fetch comprehensive product information. It
provides a unified interface for searching across multiple e-commerce platforms
including Amazon, Walmart, BestBuy, and Wayfair through the UnWrangle API
service.

Key Features:
    - Multi-retailer concurrent product search
    - Category-aware retailer selection
    - Standardized product data transformation
    - Robust error handling and logging
    - Scalable async processing for multiple API calls

Example:
    >>> from inflection_curator.providers import UnWrangleCatalogProvider
    >>> provider = UnWrangleCatalogProvider()
    >>> results = provider.search_items(
    ...     items=['gaming', 'laptop'],
    ...     category='Electronics'
    ... )
    >>> for result in results:
    ...     print(f"Found {len(result.results)} products from {result.provider}")
"""

import json
import logging
import time
from concurrent.futures.thread import ThreadPoolExecutor
from concurrent.futures import as_completed, Future
from typing import List, Optional, Union, Dict, Any
from dataclasses import dataclass, field
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

from .provider_response import ProductInfo
from ..settings import settings
from ..constants import Retailer, get_preferred_platform

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class QueryInfo:
    """Data structure for storing API query information and metadata.

    This class encapsulates the information needed to make a product search
    request to a specific retailer through the UnWrangle API. It includes
    the constructed URL and the retailer identifier for proper result
    attribution.

    Attributes:
        url (Optional[str]): The complete API endpoint URL with parameters.
        provider (Optional[str]): The retailer name (e.g., "Amazon", "Walmart").
        created_at (float): Timestamp when the query was created.
        timeout (int): Request timeout in seconds.
    """

    url: str | None
    provider: str | None
    created_at: float = field(default_factory=time.time)
    timeout: int = 30

    def __post_init__(self) -> None:
        """Validates query information after initialization."""
        if not self.url:
            logger.warning("QueryInfo created with empty URL")
        if not self.provider:
            logger.warning("QueryInfo created with empty provider")

    def is_valid(self) -> bool:
        """Checks if the query information is valid for execution."""
        return bool(self.url and self.provider)

    def get_age_seconds(self) -> float:
        """Gets the age of this query in seconds."""
        return time.time() - self.created_at


@dataclass
class ProviderResults:
    """Container for product search results from a specific retailer.

    This class aggregates the search results from a single retailer/provider,
    including metadata about the search performance and result quality.

    Attributes:
        provider (str): Name of the retailer/provider (e.g., "Amazon", "Walmart").
        results (List[ProductInfo]): List of product information objects.
        query_time_ms (Optional[float]): Time taken for the API query in
            milliseconds.
        total_found (Optional[int]): Total number of products found (if provided
            by the API).
        error (Optional[str]): Error message if the query failed.
    """

    provider: str
    results: list[ProductInfo]
    query_time_ms: float | None = None
    total_found: int | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Initializes computed properties after creation."""
        if self.results is None:
            self.results = []

    @property
    def success(self) -> bool:
        """Checks if the provider search was successful."""
        return self.error is None and len(self.results) > 0

    @property
    def result_count(self) -> int:
        """Gets the number of products returned."""
        return len(self.results)

    def get_top_products(self, limit: int = 5) -> list[ProductInfo]:
        """Gets the top N products from this provider.

        Args:
            limit: The maximum number of products to return.

        Returns:
            A list of the top products.
        """
        return self.results[:limit]

    def filter_by_price_range(
        self, min_price: float | None = None, max_price: float | None = None
    ) -> list[ProductInfo]:
        """Filters products by price range.

        Args:
            min_price: The minimum price threshold.
            max_price: The maximum price threshold.

        Returns:
            A list of filtered products within the price range.
        """
        filtered = self.results

        if min_price is not None:
            filtered = [p for p in filtered if p.price and p.price >= min_price]

        if max_price is not None:
            filtered = [p for p in filtered if p.price and p.price <= max_price]

        return filtered


class BaseProductCatalogProvider:
    """Abstract base class for all product catalog providers.

    This class defines the interface and common functionality for product
    catalog providers. It provides the foundation for implementing different
    backend services (e.g., UnWrangle, direct retailer APIs) while maintaining
    a consistent interface for the shopping assistant.
    """

    def search_items(
        self, items: str | list[str], **kwargs: Any
    ) -> list[ProviderResults]:
        """Searches for products across supported retailers.

        This method must be implemented by subclasses to provide actual
        product search functionality.

        Args:
            items: The search terms or keywords.
            **kwargs: Additional search parameters (e.g., category, limit,
                filters).

        Returns:
            A list of `ProviderResults` from each retailer.

        Raises:
            NotImplementedError: If not implemented by a subclass.
        """
        raise NotImplementedError("Subclasses must implement search_items method")

    @staticmethod
    def get_commerce_partner(category: str = "default") -> list[Retailer]:
        """Gets the optimal retailers for a product category.

        This method determines which retailers to search based on the product
        category. It uses the business logic defined in `constants.py` to select
        retailers that typically have the best selection and pricing for
        specific product types.

        Args:
            category: The product category (e.g., 'Electronics', 'Apparel',
                'Furniture'). Use 'default' for general searches.

        Returns:
            An ordered list of preferred retailers for the category.
        """
        if category == "default":
            # Default selection for general searches
            return [Retailer.Amazon, Retailer.Walmart]
        else:
            # Use category-specific platform selection
            try:
                return get_preferred_platform(category)
            except Exception as e:
                logger.warning(
                    f"Error getting preferred platforms for category '{category}': {e}"
                )
                return [Retailer.Amazon, Retailer.Walmart]

    @staticmethod
    def generate_search_queries(
        provider_url: str,
        partners: list[Retailer],
        items: list[str],
        api_key: str,
        country: str = "us",
    ) -> list[QueryInfo]:
        """Generates API query URLs for multiple retailers.

        This method constructs the complete API URLs needed to search across
        multiple retailers. It formats the base URL template with specific
        parameters for each retailer, creating a list of queryable endpoints.

        Args:
            provider_url: The URL template with placeholders for parameters.
                Example: "https://api.unwrangle.com/search?platform={platform}&query={query}&country={cn}&api_key={api_key}"
            partners: A list of retailers to generate queries for.
            items: A list of search keywords/terms to query for.
            api_key: The API authentication key.
            country: The country code for localized results (default: 'us').

        Returns:
            A list of `QueryInfo` objects containing URLs and metadata.
        """
        if not provider_url:
            logger.error("Provider URL template is empty")
            return []

        if not partners:
            logger.warning("No retailer partners provided for query generation")
            return []

        if not items:
            logger.warning("No search items provided for query generation")
            return []

        queries = []
        search_query = " ".join(
            str(item) for item in items if item
        )  # Join and filter empty items

        for partner in partners:
            try:
                # Format the URL with parameters
                formatted_url = provider_url.format(
                    platform=partner.value,
                    query=search_query,
                    cn=country,
                    api_key=api_key,
                )

                query_info = QueryInfo(url=formatted_url, provider=partner.value)
                queries.append(query_info)

                logger.debug(
                    f"Generated query for {partner.value}: {formatted_url[:100]}..."
                )

            except KeyError as e:
                logger.error(
                    f"URL template missing placeholder {e} for provider {partner.value}"
                )
            except Exception as e:
                logger.error(f"Error generating query for {partner.value}: {e}")

        logger.info(
            f"Generated {len(queries)} search queries for {len(partners)} retailers"
        )
        return queries

    @staticmethod
    def call_url(url: str, timeout: int = 30) -> dict[str, Any]:
        """Makes an HTTP GET request to retrieve product data.

        This method handles the actual HTTP communication with retailer APIs,
        including error handling, timeout management, and response parsing.

        Args:
            url: The complete API endpoint URL to request.
            timeout: The request timeout in seconds (default: 30).

        Returns:
            A dictionary containing the parsed JSON response from the API, or an
            empty dictionary on error.
        """
        if not url:
            logger.error("Cannot call empty URL")
            return {}

        start_time = time.time()

        try:
            logger.debug(f"Making API request to: {url[:100]}...")

            response = requests.get(url, timeout=timeout)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Parse JSON response
            data = response.json()

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                f"API request completed in {elapsed_ms:.1f}ms, received {len(data) if isinstance(data, list) else 'non-list'} items"
            )

            return data

        except Timeout:
            logger.error(f"Request timeout after {timeout}s for URL: {url[:100]}")
        except ConnectionError:
            logger.error(f"Connection error for URL: {url[:100]}")
        except RequestException as e:
            logger.error(f"Request failed for URL: {url[:100]} - {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from URL: {url[:100]} - {e}")
        except Exception as e:
            logger.error(f"Unexpected error calling URL: {url[:100]} - {e}")

        return {}

    def get_provider_info(self) -> dict[str, Any]:
        """Gets information about this provider implementation.

        Returns:
            A dictionary containing provider metadata and capabilities.
        """
        return {
            "name": self.__class__.__name__,
            "supported_retailers": [r.value for r in Retailer],
            "capabilities": ["product_search", "multi_retailer", "concurrent_search"],
        }


class UnWrangleCatalogProvider(BaseProductCatalogProvider):
    """UnWrangle API-based product catalog provider for multi-retailer search.

    This class implements product search functionality using the UnWrangle API
    service, which provides unified access to multiple e-commerce retailers.

    Attributes:
        _api_key (str): The UnWrangle API key.
        _url (str): The UnWrangle API search URL template.
        _total_searches (int): The total number of searches performed.
        _successful_searches (int): The number of successful searches.
        _failed_searches (int): The number of failed searches.
    """

    def __init__(self) -> None:
        """Initializes the UnWrangleCatalogProvider.

        Raises:
            ValueError: If the required API key or URL is not configured.
        """
        super().__init__()

        # Load configuration from settings
        self._api_key = settings.unwrangle_apikey
        self._url = settings.unwrangle_search_url  # Use the search URL template

        # Validate required configuration
        if not self._api_key:
            raise ValueError(
                "UnWrangle API key is required. "
                "Set UNWRANGLE_APIKEY in your .env file."
            )

        if not self._url:
            raise ValueError(
                "UnWrangle API URL is required. "
                "Set UNWRANGLE_SEARCH_URL in your .env file."
            )

        # Initialize metrics
        self._total_searches = 0
        self._successful_searches = 0
        self._failed_searches = 0

        logger.info(f"UnWrangleCatalogProvider initialized with API endpoint")
        logger.debug(f"Using URL template: {self._url[:50]}...")

    def search_items(self, items: list[str], **kwargs: Any) -> list[ProviderResults]:
        """Searches for products across multiple retailers using the UnWrangle API.

        This method orchestrates a comprehensive product search across multiple
        retail platforms. It automatically selects the best retailers for the
        given product category, executes concurrent API calls, and transforms
        the raw responses into standardized product information.

        Args:
            items: A list of search keywords and terms.
            **kwargs: Additional search parameters, such as `category`,
                `country`, and `timeout`.

        Returns:
            A list of `ProviderResults` organized by retailer.

        Raises:
            ValueError: If the `items` list is empty or invalid.
        """
        # Input validation
        if not items:
            raise ValueError("Search items cannot be empty")

        # Filter out empty items and convert to strings
        clean_items = [
            str(item).strip() for item in items if item and str(item).strip()
        ]
        if not clean_items:
            raise ValueError("No valid search items provided")

        # Extract search parameters
        category = kwargs.get("category", "default")
        country = kwargs.get("country", "us")
        timeout = kwargs.get("timeout", 30)

        logger.info(
            f"Starting product search for items: {clean_items} in category: {category}"
        )

        # Track search metrics
        self._total_searches += 1
        search_start_time = time.time()

        try:
            # Step 1: Get optimal retailers for the category
            partners = self.get_commerce_partner(category)
            logger.debug(
                f"Selected retailers for category '{category}': {[p.value for p in partners]}"
            )

            # Step 2: Generate API query URLs
            partner_queries = self.generate_search_queries(
                provider_url=self._url,
                partners=partners,
                items=clean_items,
                api_key=self._api_key,
                country=country,
            )

            if not partner_queries:
                logger.error("No valid queries generated")
                return []

            # Step 3: Execute concurrent API requests
            logger.info(f"Executing {len(partner_queries)} concurrent API requests")
            product_results = self._execute_concurrent_searches(
                partner_queries, timeout
            )

            # Step 4: Log search completion
            search_duration = time.time() - search_start_time
            successful_results = sum(1 for r in product_results if r.success)
            total_products = sum(r.result_count for r in product_results)

            logger.info(
                f"Search completed in {search_duration:.2f}s: "
                f"{successful_results}/{len(product_results)} retailers succeeded, "
                f"{total_products} total products found"
            )

            if successful_results > 0:
                self._successful_searches += 1
            else:
                self._failed_searches += 1

            return product_results

        except Exception as e:
            self._failed_searches += 1
            logger.error(f"Product search failed: {e}")
            raise

    def _execute_concurrent_searches(
        self, queries: list[QueryInfo], timeout: int
    ) -> list[ProviderResults]:
        """Executes multiple API searches concurrently using a thread pool.

        Args:
            queries: A list of `QueryInfo` objects to execute.
            timeout: The timeout for individual requests.

        Returns:
            A list of `ProviderResults` from each retailer.
        """
        future_to_provider = {}
        product_results = []

        # Execute concurrent API calls
        with ThreadPoolExecutor(max_workers=len(queries)) as executor:
            # Submit all requests
            for query in queries:
                if query.is_valid():
                    future = executor.submit(self.call_url, query.url, timeout)
                    future_to_provider[future] = query.provider
                else:
                    logger.warning(
                        f"Skipping invalid query for provider {query.provider}"
                    )

        # Collect results as they complete
        for future in as_completed(future_to_provider):
            provider = future_to_provider[future]

            try:
                start_time = time.time()
                api_response = future.result()
                query_time_ms = (time.time() - start_time) * 1000

                if api_response:
                    # Transform API response to ProductInfo objects
                    product_details = self._transform_api_response(
                        api_response, provider
                    )

                    result = ProviderResults(
                        provider=provider,
                        results=product_details,
                        query_time_ms=query_time_ms,
                        total_found=(
                            len(api_response)
                            if isinstance(api_response, list)
                            else None
                        ),
                    )

                    logger.debug(
                        f"{provider}: Successfully processed {len(product_details)} products "
                        f"in {query_time_ms:.1f}ms"
                    )
                else:
                    # Empty response
                    result = ProviderResults(
                        provider=provider,
                        results=[],
                        query_time_ms=query_time_ms,
                        error="Empty response from API",
                    )
                    logger.warning(f"{provider}: Received empty response")

            except Exception as e:
                # Request failed
                result = ProviderResults(provider=provider, results=[], error=str(e))
                logger.error(f"{provider}: Request failed - {e}")

            product_results.append(result)

        return product_results

    def _transform_api_response(
        self, api_response: list[dict[str, Any]] | dict[str, Any], provider: str
    ) -> list[ProductInfo]:
        """Transforms a raw API response into standardized ProductInfo objects.

        Args:
            api_response: The raw response from the UnWrangle API.
            provider: The name of the retailer for this response.

        Returns:
            A list of transformed `ProductInfo` objects.
        """
        if not api_response:
            return []

        # Handle both list and dict responses
        if isinstance(api_response, dict):
            api_response = [api_response]
        elif not isinstance(api_response, list):
            logger.warning(f"Unexpected API response type: {type(api_response)}")
            return []

        product_details = []

        for item in api_response:
            try:
                product = self.to_product_detail(item, provider)
                if product:
                    product_details.append(product)
            except Exception as e:
                logger.error(f"Error transforming product data from {provider}: {e}")
                logger.debug(f"Problematic data: {item}")

        logger.debug(
            f"Transformed {len(product_details)}/{len(api_response)} products from {provider}"
        )
        return product_details

    @staticmethod
    def to_product_detail(
        el: str | dict[str, Any], provider: Retailer | str
    ) -> ProductInfo | None:
        """Transforms raw product data into a standardized ProductInfo object.

        This method handles the conversion of retailer-specific product data
        formats into the unified `ProductInfo` data model. It supports different
        input formats and handles parsing errors gracefully.

        Args:
            el: The raw product data from the API response. Can be a JSON
                string or a dictionary.
            provider: The retailer that provided this data.

        Returns:
            A standardized `ProductInfo` object, or `None` if parsing failed.
        """
        if not el:
            return None

        try:
            # Handle string input (JSON)
            if isinstance(el, str):
                try:
                    product_data = json.loads(el)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON product data: {e}")
                    return None
            elif isinstance(el, dict):
                product_data = el
            else:
                logger.error(f"Unexpected product data type: {type(el)}")
                return None

            # Convert provider to Retailer enum if it's a string
            if isinstance(provider, str):
                try:
                    # Find matching retailer enum
                    retailer_enum = None
                    for retailer in Retailer:
                        if retailer.value.lower() == provider.lower():
                            retailer_enum = retailer
                            break

                    if not retailer_enum:
                        logger.warning(f"Unknown retailer: {provider}")
                        return None

                    provider = retailer_enum
                except Exception as e:
                    logger.error(f"Error converting provider '{provider}' to enum: {e}")
                    return None

            # Transform data based on retailer
            if provider == Retailer.Amazon:
                return ProductInfo.from_amazon(product_data)
            elif provider == Retailer.Walmart:
                return ProductInfo.from_walmart(product_data)
            elif provider == Retailer.BestBuy:
                return ProductInfo.from_bestbuy(product_data)
            elif provider == Retailer.WayFair:
                # Note: WayFair parser would need to be implemented in ProductInfo
                logger.warning(f"WayFair parser not yet implemented")
                return None
            else:
                logger.error(
                    f"Unsupported retailer for product transformation: {provider}"
                )
                return None

        except Exception as ex:
            logger.error(f"Error processing product data from {provider}: {ex}")
            logger.debug(f"Problematic product data: {el}")
            return None

    def get_search_stats(self) -> dict[str, Any]:
        """Gets performance statistics for this provider instance.

        Returns:
            A dictionary of statistics, including search counts and success rates.
        """
        total = self._total_searches
        success_rate = (self._successful_searches / total * 100) if total > 0 else 0

        return {
            "total_searches": self._total_searches,
            "successful_searches": self._successful_searches,
            "failed_searches": self._failed_searches,
            "success_rate_percent": round(success_rate, 1),
            "provider_type": "UnWrangle API",
        }
