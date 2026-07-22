from tavily import TavilyClient

from core.config import settings
from core.cache import cache, make_cache_key
from core.logging import app_logger


class SearchTool:

    def __init__(self):

        self.client = TavilyClient(
            api_key=settings.TAVILY_API_KEY
        )


    async def search(
        self,
        query: str,
        bypass_cache: bool = False
    ):
        cache_key = make_cache_key("tavily_search", query)
        
        if not bypass_cache:
            cached_val = await cache.get(cache_key)
            if cached_val is not None:
                app_logger.info(f"[Cache Hit] Tavily search hit for query: '{query}'")
                return cached_val
            app_logger.info(f"[Cache Miss] Tavily search miss for query: '{query}'")
        else:
            app_logger.info(f"[Cache Bypass] Bypassing search cache for query: '{query}'")

        response = self.client.search(
            query=query,
            max_results=5
        )

        results = []

        for item in response.get("results", []):

            results.append(
                {
                    "title": item["title"],
                    "url": item["url"],
                    "content": item["content"],
                }
            )

        await cache.set(cache_key, results, settings.SEARCH_CACHE_TTL_SECONDS)
        return results



search_tool = SearchTool()