import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from tavily import TavilyClient

from core.config import settings
from core.cache import cache, make_cache_key
from core.logging import app_logger
from schemas.evidence import EvidenceRecord, SourceCredibility


def extract_domain(url: str) -> str:
    """Extracts clean normalized domain from URL (e.g., https://www.reuters.com/x -> reuters.com)."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.split(":")[0].lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def determine_domain_credibility(domain: str) -> SourceCredibility:
    """Determines conservative baseline credibility for a domain."""
    d = (domain or "").lower()
    if not d:
        return SourceCredibility.UNKNOWN

    # High Credibility: Government/regulatory sources and official APIs
    if d.endswith(".gov") or d.endswith(".gov.in") or d in {
        "sec.gov", "mca.gov.in", "github.com", "api.github.com"
    }:
        return SourceCredibility.HIGH

    # Medium Credibility: Established journalism, research institutes, reputable databases
    if d in {
        "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
        "techcrunch.com", "forbes.com", "crunchbase.com", "wikipedia.org",
        "nytimes.com", "nature.com", "sciencedirect.com"
    }:
        return SourceCredibility.MEDIUM

    # Low Credibility: PR distribution networks and press release wire services
    if d in {
        "prnewswire.com", "businesswire.com", "globenewswire.com",
        "prweb.com", "openpr.com"
    }:
        return SourceCredibility.LOW

    return SourceCredibility.UNKNOWN


def generate_web_evidence_id(url: str, query: str) -> str:
    """Generates a deterministic evidence ID from normalized URL and query."""
    norm_url = (url or "").strip().lower()
    norm_query = (query or "").strip().lower()
    raw = f"{norm_url}|{norm_query}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"ev_web_{digest}"


def create_evidence_record_from_hit(hit: dict, query: str) -> EvidenceRecord:
    """Converts a raw search hit dictionary into a structured EvidenceRecord."""
    title = hit.get("title") or "Untitled Web Source"
    url = hit.get("url") or ""
    content = hit.get("content") or ""
    score = hit.get("score")
    pub_date = hit.get("published_date")

    domain = extract_domain(url)
    credibility = determine_domain_credibility(domain)
    evidence_id = generate_web_evidence_id(url, query)

    return EvidenceRecord(
        evidence_id=evidence_id,
        source_type="web_search",
        source_name=title,
        url=url if url else None,
        raw_snippet=content if content else None,
        credibility=credibility,
        independence_group=domain if domain else None,  # Provisional source-origin group
        retrieved_at=datetime.now(timezone.utc),
        query=query,
        relevance_score=score,
        published_date=pub_date,
        domain=domain if domain else None,
    )


class SearchResultsWithEvidence(BaseModel):
    """Structured container holding prompt-compatible dict results alongside EvidenceRecord objects."""
    results: List[Dict[str, Any]] = Field(description="Prompt-compatible raw result dicts")
    evidence_records: List[EvidenceRecord] = Field(description="Structured evidence records")


class SearchTool:

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            key = (settings.TAVILY_API_KEY or "").strip()
            if not key:
                raise ValueError("No valid TAVILY_API_KEY configured.")
            self._client = TavilyClient(api_key=key)
        return self._client

    async def search(
        self,
        query: str,
        bypass_cache: bool = False
    ) -> List[Dict[str, Any]]:
        """Standard search method returning List[dict] for 100% backward compatibility."""
        cache_key = make_cache_key("tavily_search", query)
        
        if not bypass_cache:
            cached_val = await cache.get(cache_key)
            if cached_val is not None:
                app_logger.info(f"[Cache Hit] Tavily search hit for query: '{query}'")
                return cached_val
            app_logger.info(f"[Cache Miss] Tavily search miss for query: '{query}'")
        else:
            app_logger.info(f"[Cache Bypass] Bypassing search cache for query: '{query}'")

        try:
            client = self.client
            response = await asyncio.to_thread(
                client.search,
                query=query,
                max_results=5
            )
        except Exception as exc:
            app_logger.warning(f"[SearchTool] search failed for query '{query}': {exc}")
            return []

        results = []

        for item in response.get("results", []):
            hit = {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            if "score" in item:
                hit["score"] = item["score"]
            if "published_date" in item:
                hit["published_date"] = item["published_date"]
            results.append(hit)

        await cache.set(cache_key, results, settings.SEARCH_CACHE_TTL_SECONDS)
        return results

    async def search_with_evidence(
        self,
        query: str,
        bypass_cache: bool = False
    ) -> SearchResultsWithEvidence:
        """New structured search method returning both prompt-compatible dicts and EvidenceRecord objects."""
        results = await self.search(query=query, bypass_cache=bypass_cache)
        records = [create_evidence_record_from_hit(hit, query) for hit in results]
        return SearchResultsWithEvidence(results=results, evidence_records=records)


search_tool = SearchTool()