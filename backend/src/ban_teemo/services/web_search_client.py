"""Web search client for fetching meta context.

Provides both a real implementation (using a search API) and a mock
for testing/development.
"""

import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class MockWebSearchClient:
    """Mock web search client with hardcoded meta context.

    Use this for testing and development when you don't have a search API.
    """

    # Hardcoded meta context based on common pro play patterns
    META_CONTEXT = """
## Recent Pro Play Meta (Patch 15.17)

### Top Priority Picks
- **Top**: Rumble, Ambessa, Renekton, Jax, Ksante
- **Jungle**: Poppy, Vi, Xin Zhao, Elise, Lee Sin
- **Mid**: Azir, Aurora, Orianna, Syndra, Ahri
- **Bot**: Kai'Sa, Jinx, Aphelios, Zeri, Sivir
- **Support**: Rakan, Alistar, Nautilus, Thresh, Lulu

### High Ban Priority
- Azir (contested mid, flex potential)
- Poppy (jungle/support flex, strong engage)
- Rumble (top priority, team fight ultimate)
- Pantheon (flex top/jungle/support)
- Neeko (support priority, engage)

### Composition Trends
- Team fight compositions with Orianna ball delivery remain strong
- Engage supports highly valued for objective control
- Scaling ADCs preferred in bot lane meta
- Flex picks crucial for hiding draft strategy

### Player Tendencies (LCK/LPL)
- Chovy: Known for Azir, Orianna, control mages
- Faker: Wide champion pool, signature Azir/Syndra
- Canyon: Aggressive jungle pathing, Vi/Xin Zhao comfort
- Kiin: Rumble specialist, carry top laners
- Ruler: Late game ADCs, Kai'Sa/Jinx preference

### Draft Psychology
- First pick often goes to flex champions to hide role assignment
- Blue side tends to secure priority supports early
- Red side can counter-pick solo lanes in later rotation
"""

    async def search(self, query: str, limit: int = 3) -> str:
        """Return mock meta context regardless of query."""
        logger.info(f"MockWebSearch: Returning hardcoded context for query: {query}")
        return self.META_CONTEXT


class WebSearchClient:
    """Real web search client using Tavily or similar API.

    Set up with a search API key to get real-time meta information.
    """

    # Tavily API (good for this use case)
    TAVILY_API_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str, timeout: float = 10.0):
        """Initialize the web search client.

        Args:
            api_key: Tavily API key (or other search API)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # Authoritative esports/analytics domains for better pro play context
    INCLUDE_DOMAINS = [
        "lol.fandom.com",  # Leaguepedia - pro match data
        "gol.gg",  # Pro player/team stats
        "oracleselixir.com",  # Pro analytics
        "u.gg",  # Meta tier lists
        "lolalytics.com",  # Champion analytics
    ]

    async def search(self, query: str, limit: int = 3) -> str:
        """Search the web for meta context.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            Formatted search results as a string
        """
        try:
            client = await self._get_client()
            response = await client.post(
                self.TAVILY_API_URL,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "advanced",  # Better quality results
                    "max_results": limit,
                    "include_answer": True,
                    "include_domains": self.INCLUDE_DOMAINS,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Format results
            results = []
            if data.get("answer"):
                results.append(f"Summary: {data['answer']}")

            for i, result in enumerate(data.get("results", [])[:limit], 1):
                title = result.get("title", "")
                content = result.get("content", "")[:300]
                results.append(f"{i}. {title}\n   {content}")

            return "\n\n".join(results) if results else "No search results found."
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Web search failed: {e}"


def get_web_search_client(
    api_key: Optional[str] = None, use_mock: bool = False
) -> MockWebSearchClient | WebSearchClient:
    """Factory function to get appropriate web search client.

    Args:
        api_key: Search API key (Tavily, etc.)
        use_mock: Force use of mock client

    Returns:
        WebSearchClient or MockWebSearchClient
    """
    if use_mock or not api_key:
        logger.info("Using MockWebSearchClient")
        return MockWebSearchClient()
    logger.info("Using real WebSearchClient")
    return WebSearchClient(api_key)
