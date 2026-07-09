from tavily import TavilyClient

from core.config import settings


class SearchTool:

    def __init__(self):

        self.client = TavilyClient(
            api_key=settings.TAVILY_API_KEY
        )


    async def search(
        self,
        query: str
    ):

        response = self.client.search(
            query=query,
            max_results=5
        )

        results = []

        for item in response["results"]:

            results.append(
                {
                    "title": item["title"],
                    "url": item["url"],
                    "content": item["content"],
                }
            )

        return results



search_tool = SearchTool()