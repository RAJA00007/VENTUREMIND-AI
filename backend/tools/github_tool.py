"""
GitHub Tool

Fetches real repository metrics from the GitHub REST API. Unlike the
web search tool (which returns fuzzy, LLM-interpreted content), this
tool returns hard numeric/structural facts: commit dates, contributor
counts, presence of test directories, etc. This is what makes the
Code/GitHub Agent's scoring deterministic rather than LLM-judgment-based.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from core.config import settings
from core.constants import DEFAULT_TIMEOUT
from core.logging import app_logger
from core.cache import cache, make_cache_key

GITHUB_API_BASE = "https://api.github.com"


def parse_repo_path(github_url_or_path: str) -> Optional[tuple[str, str]]:
    """Accepts 'github.com/org/repo', 'https://github.com/org/repo', or
    'org/repo' and returns (owner, repo), or None if unparseable."""
    cleaned = github_url_or_path.strip()
    if cleaned.startswith("http"):
        parsed = urlparse(cleaned)
        parts = [p for p in parsed.path.split("/") if p]
    else:
        cleaned = cleaned.replace("github.com/", "")
        parts = [p for p in cleaned.split("/") if p]

    if len(parts) < 2:
        return None
    return parts[0], parts[1].replace(".git", "")


class GitHubTool:

    def __init__(self):
        self._headers = {"Accept": "application/vnd.github+json"}
        if settings.GITHUB_TOKEN:
            self._headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    async def get_repo_metrics(self, owner: str, repo: str, bypass_cache: bool = False) -> dict[str, Any]:
        """
        Fetches and pre-computes the raw facts the Code Agent's rubric
        needs. Returns a dict with a top-level "error" key if the repo
        can't be accessed (private, not found, rate-limited) so the
        caller can produce a clean no_data/failed result instead of a
        confusing partial crash.
        """
        cache_key = make_cache_key("github_repo", owner, repo)
        
        if not bypass_cache:
            cached_val = await cache.get(cache_key)
            if cached_val is not None:
                app_logger.info(f"[Cache Hit] GitHub repo metrics hit for {owner}/{repo}")
                return cached_val
            app_logger.info(f"[Cache Miss] GitHub repo metrics miss for {owner}/{repo}")
        else:
            app_logger.info(f"[Cache Bypass] Bypassing GitHub repo cache for {owner}/{repo}")

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, headers=self._headers) as client:
            repo_resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}")

            if repo_resp.status_code == 404:
                return {"error": "repository_not_found"}
            if repo_resp.status_code == 403:
                return {"error": "rate_limited_or_forbidden"}
            repo_resp.raise_for_status()
            repo_data = repo_resp.json()

            # Contributors (used for bus-factor / concentration risk)
            contributors_resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contributors",
                params={"per_page": 100, "anon": "false"},
            )
            contributors = contributors_resp.json() if contributors_resp.status_code == 200 else []

            # Recent commit activity (last ~100 commits, used for recency/frequency)
            commits_resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits",
                params={"per_page": 100},
            )
            commits = commits_resp.json() if commits_resp.status_code == 200 else []

            # Root directory listing (used to detect tests/ and CI config)
            contents_resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents"
            )
            root_contents = contents_resp.json() if contents_resp.status_code == 200 else []

            # CI workflow presence
            workflows_resp = await client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/.github/workflows"
            )
            has_ci = workflows_resp.status_code == 200

            # README presence
            readme_resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme")
            has_readme = readme_resp.status_code == 200
            readme_size = readme_resp.json().get("size", 0) if has_readme else 0

        computed = self._compute_facts(
            repo_data, contributors, commits, root_contents, has_ci, has_readme, readme_size
        )
        
        if "error" not in computed:
            await cache.set(cache_key, computed, settings.GITHUB_CACHE_TTL_SECONDS)
            
        return computed

    @staticmethod
    def _compute_facts(
        repo_data: dict,
        contributors: list,
        commits: list,
        root_contents: Any,
        has_ci: bool,
        has_readme: bool,
        readme_size: int,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)

        pushed_at = repo_data.get("pushed_at")
        days_since_last_push = None
        if pushed_at:
            last_push = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            days_since_last_push = (now - last_push).days

        # Commit recency distribution over the fetched window
        commit_dates = []
        for c in commits:
            try:
                date_str = c["commit"]["author"]["date"]
                commit_dates.append(datetime.fromisoformat(date_str.replace("Z", "+00:00")))
            except (KeyError, TypeError):
                continue
        commits_last_90_days = sum(1 for d in commit_dates if (now - d).days <= 90)

        # Contributor concentration (bus factor risk)
        total_contributions = sum(c.get("contributions", 0) for c in contributors) if isinstance(contributors, list) else 0
        top_contributor_share = None
        if contributors and isinstance(contributors, list) and total_contributions > 0:
            top_contributor_share = round(
                contributors[0].get("contributions", 0) / total_contributions, 2
            )

        # Test directory detection from root listing
        test_dir_names = {"tests", "test", "__tests__", "spec"}
        has_test_dir = False
        if isinstance(root_contents, list):
            has_test_dir = any(
                item.get("name", "").lower() in test_dir_names
                and item.get("type") == "dir"
                for item in root_contents
            )

        return {
            "error": None,
            "name": repo_data.get("full_name"),
            "description": repo_data.get("description"),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "open_issues": repo_data.get("open_issues_count", 0),
            "created_at": repo_data.get("created_at"),
            "days_since_last_push": days_since_last_push,
            "commits_last_90_days": commits_last_90_days,
            "commit_sample_size": len(commit_dates),
            "contributor_count": len(contributors) if isinstance(contributors, list) else 0,
            "top_contributor_share": top_contributor_share,
            "has_test_dir": has_test_dir,
            "has_ci": has_ci,
            "has_readme": has_readme,
            "readme_size_bytes": readme_size,
            "is_archived": repo_data.get("archived", False),
            "url": repo_data.get("html_url"),
        }


github_tool = GitHubTool()
