import json
import logging
from concurrent.futures.thread import ThreadPoolExecutor
from concurrent.futures import as_completed

from typing import List, Optional, Union
from dataclasses import dataclass
import requests

from providers.provider_response import ProductInfo
from settings import settings
from constants import Retailer


@dataclass
class QueryInfo:
    url: Optional[str]
    provider: Optional[str]


@dataclass
class ProviderResults:
    provider: str
    results: List[ProductInfo]


class BaseProductCatalogProvider:

    def search_items(self, items: str):
        pass

    @staticmethod
    def get_commerce_partner(category: str = 'default'):
        if category == 'default':
            return [Retailer.Amazon, Retailer.Walmart]

    @staticmethod
    def generate_search_queries(provider_url: str, partners: list, items: List[str], api_key: str,
                                country: str = 'us') -> List[QueryInfo]:
        urls = []
        for partner in partners:
            url = provider_url.format(platform=partner, query=' '.join(items), cn=country, api_key=api_key)
            urls.append(QueryInfo(url=url, provider=partner))
        return urls

    @staticmethod
    def call_url(url: str):
        response = requests.get(url)
        if response.status_code == response.ok:
            return response.json()
        return {}


class UnWrangleCatalogProvider(BaseProductCatalogProvider):
    """
    Provides support for getting product details from the UnWrangle APIs
    https://www.unwrangle.com/
    """

    def __init__(self):
        self._api_key = settings.unwrangle_apikey
        self._url = settings.unwrangle_url

    def search_items(self, items: List[str], **kwargs):
        category = kwargs.get('category', 'default')
        partners = self.get_commerce_partner(category)
        partner_queries = self.generate_search_queries(self._url, partners, items, api_key=self._api_key)
        future_dict = {}
        product_results = []
        with ThreadPoolExecutor() as tp:
            for pq in partner_queries:
                future_dict[tp.submit(self.call_url, pq.url)] = pq.provider
        for res in as_completed(future_dict):
            provider = future_dict.get(res)
            outcomes = res.result()
            product_details = [self.to_product_detail(el, provider) for el in outcomes]
            prod_res = ProviderResults(provider=provider, results=product_details)
            product_results.append(prod_res)
        return product_results

    @staticmethod
    def to_product_detail(el: Union[str, dict], provider: Union[Retailer,str]):
        """
        This method will be used to fill in the product details
        :param provider: Provider this product is fetched from
        :param el:
        :return:
        """
        try:
            prod = json.loads(el)
            if provider == Retailer.Amazon:
                return ProductInfo.from_amazon(prod)
            if provider == Retailer.Walmart:
                return ProductInfo.from_walmart(prod)
            if provider == Retailer.BestBuy:
                return ProductInfo.from_bestbuy(prod)
        except  Exception as ex:
            logging.error(f"Error processing the input ={el}")
