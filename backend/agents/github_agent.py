"""
Code / GitHub Agent

Scores a company's codebase quality on a 0-100 rubric — VentureMind's
core differentiator, since most competing diligence tools rely only on
pitch decks and websites ("demos are theater, decks are marketing, code
is truth").

KEY DESIGN DIFFERENCE FROM OTHER AGENTS: scores here are computed
DETERMINISTICALLY from real GitHub API data (commit dates, contributor
counts, file presence), not judged by an LLM. This makes this agent the
lowest-hallucination-risk component in the whole system — there is no
"the LLM decided" step in the scoring itself. The LLM is only used at
the very end to phrase a natural-language summary of numbers that were
already computed in code, which is a much safer use of an LLM than
asking it to invent or judge a score.

If no GitHub repo is provided or found, this returns a no_data result
rather than penalizing the company — many legitimate startups (esp.
consumer/non-technical ones) have private or no public repos.
"""

from typing import Any

from agents.base_agent import BaseAgent
from core.logging import app_logger
from schemas.scoring import AgentScoreResult, ScoreFactor, make_no_data_result
from services.llm_service import llm_service, AllLLMProvidersFailedError
from tools.github_tool import github_tool, parse_repo_path


# Each scoring function below takes the raw `facts` dict from GitHubTool
# and returns (points, reason) — a fully deterministic, auditable
# calculation. This is the opposite pattern from other agents: instead
# of asking an LLM "how many points does this deserve", we compute the
# number in code and the LLM never touches it.

def _score_maintenance(facts: dict) -> tuple[float, str]:
    max_points = 25
    days = facts.get("days_since_last_push")
    commits_90d = facts.get("commits_last_90_days", 0)

    if facts.get("is_archived"):
        return 0.0, "Repository is archived — no longer maintained."
    if days is None:
        return 0.0, "Could not determine last push date."

    if days <= 14:
        recency_score = 15
    elif days <= 60:
        recency_score = 10
    elif days <= 180:
        recency_score = 4
    else:
        recency_score = 0

    activity_score = min(10, commits_90d)  # 1 point per commit in last 90d, capped at 10

    total = recency_score + activity_score
    return total, (
        f"Last push {days} days ago ({commits_90d} commits in the last 90 days "
        f"among the {facts.get('commit_sample_size', 0)} most recent commits sampled)."
    )


def _score_contributor_health(facts: dict) -> tuple[float, str]:
    max_points = 20
    count = facts.get("contributor_count", 0)
    top_share = facts.get("top_contributor_share")

    if count == 0:
        return 0.0, "No contributor data available."

    if count == 1:
        base = 5
    elif count <= 3:
        base = 12
    else:
        base = 18

    penalty = 0
    if top_share is not None and top_share >= 0.9 and count > 1:
        penalty = 4  # nominally multiple contributors but one person did nearly everything

    total = max(0, min(max_points, base - penalty))
    concentration_note = (
        f", top contributor accounts for {int(top_share * 100)}% of contributions"
        if top_share is not None else ""
    )
    return total, f"{count} contributor(s) found{concentration_note}."


def _score_testing_ci(facts: dict) -> tuple[float, str]:
    max_points = 20
    has_tests = facts.get("has_test_dir", False)
    has_ci = facts.get("has_ci", False)

    points = (12 if has_tests else 0) + (8 if has_ci else 0)
    parts = []
    parts.append("a test directory" if has_tests else "no detected test directory")
    parts.append("CI workflow configured" if has_ci else "no CI workflow detected")
    return points, f"Repository has {parts[0]} and {parts[1]}."


def _score_documentation(facts: dict) -> tuple[float, str]:
    max_points = 15
    has_readme = facts.get("has_readme", False)
    readme_size = facts.get("readme_size_bytes", 0)

    if not has_readme:
        return 0.0, "No README found."

    if readme_size < 200:
        return 4.0, f"README exists but is very short ({readme_size} bytes)."
    elif readme_size < 2000:
        return 10.0, f"README exists with moderate detail ({readme_size} bytes)."
    else:
        return 15.0, f"README exists with substantial detail ({readme_size} bytes)."


def _score_community_traction(facts: dict) -> tuple[float, str]:
    max_points = 10
    stars = facts.get("stars", 0)
    forks = facts.get("forks", 0)

    # Logarithmic-ish thresholds — stars are a weak signal and shouldn't
    # dominate the score, but zero vs. meaningfully-adopted is worth noting.
    if stars >= 500:
        points = 10
    elif stars >= 100:
        points = 7
    elif stars >= 20:
        points = 4
    elif stars >= 1:
        points = 1
    else:
        points = 0

    return points, f"{stars} stars, {forks} forks."


def _score_repo_hygiene(facts: dict) -> tuple[float, str]:
    max_points = 10
    open_issues = facts.get("open_issues", 0)

    if open_issues <= 5:
        points = 10
    elif open_issues <= 20:
        points = 7
    elif open_issues <= 50:
        points = 4
    else:
        points = 1

    return points, f"{open_issues} open issues."


SCORERS = [
    ("Maintenance & activity", 25, _score_maintenance),
    ("Contributor health (bus factor)", 20, _score_contributor_health),
    ("Testing & CI practices", 20, _score_testing_ci),
    ("Documentation quality", 15, _score_documentation),
    ("Community traction", 10, _score_community_traction),
    ("Repository hygiene", 10, _score_repo_hygiene),
]

MAX_TOTAL_POINTS = sum(s[1] for s in SCORERS)  # = 100


class GitHubAgent(BaseAgent):

    def __init__(self):
        super().__init__(
            name="Code / GitHub Agent",
            role="Technical due-diligence analyst",
        )

    async def run(self, input_data: Any) -> AgentScoreResult:
        company = input_data["company"]
        github_repo = input_data.get("github_repo")

        if not github_repo:
            return make_no_data_result(
                self.name,
                f"No GitHub repository provided for '{company}'. Code quality "
                f"cannot be assessed without a public repo — this is not a "
                f"negative signal on its own (many companies keep code private).",
            )

        parsed = parse_repo_path(github_repo)
        if not parsed:
            return make_no_data_result(
                self.name,
                f"Could not parse GitHub repository path from '{github_repo}'.",
            )
        owner, repo = parsed

        try:
            facts = await github_tool.get_repo_metrics(owner, repo)
        except Exception as exc:
            app_logger.error(f"[Code / GitHub Agent] GitHub API call failed: {exc}")
            raise

        if facts.get("error") == "repository_not_found":
            return make_no_data_result(
                self.name,
                f"Repository '{owner}/{repo}' not found or private.",
            )
        if facts.get("error") == "rate_limited_or_forbidden":
            # This IS a real failure (transient/infra), not a no_data
            # situation — raise so base_agent retries / marks as failed
            # rather than silently reporting "no code" for a real repo.
            raise RuntimeError(f"GitHub API rate-limited or forbidden for {owner}/{repo}")

        # --- Deterministic scoring — no LLM involved in the numbers ---------
        factors = []
        for factor_name, max_points, scorer_fn in SCORERS:
            points, reason = scorer_fn(facts)
            factors.append(
                ScoreFactor(
                    factor=factor_name,
                    points=round(points, 1),
                    max_points=max_points,
                    reason=reason,
                    source=facts.get("url"),
                )
            )

        total_score = sum(f.points for f in factors)

        # Confidence here reflects DATA COMPLETENESS, not LLM uncertainty —
        # e.g. if commit sampling was thin, confidence is lower.
        confidence = 0.9 if facts.get("commit_sample_size", 0) >= 10 else 0.6

        # LLM is used ONLY to phrase a summary of numbers already computed
        # above — it cannot alter the score and has no scoring authority.
        summary_prompt = f"""Write a 2-3 sentence plain-language summary of this
repository's code quality for a VC due-diligence report, based ONLY on these
computed facts. Do not add any information not present here.

Facts: {facts}
Computed sub-scores: {[(f.factor, f.points, f.max_points) for f in factors]}
Overall score: {total_score}/100"""

        try:
            summary = await llm_service.generate(summary_prompt)
        except AllLLMProvidersFailedError as exc:
            return make_no_data_result(
                self.name,
                "All LLM providers unavailable — evaluation could not be completed for this factor."
            )
        except Exception as exc:
            app_logger.warning(f"[Code / GitHub Agent] summary generation failed: {exc}")
            summary = (
                f"Code quality score: {total_score}/100 based on maintenance activity, "
                f"contributor health, testing practices, documentation, and community traction."
            )

        return AgentScoreResult(
            agent=self.name,
            score=round(total_score, 1),
            score_breakdown=factors,
            summary=summary.strip(),
            confidence=confidence,
            sources=[facts.get("url")] if facts.get("url") else [],
            status="ok",
        )
