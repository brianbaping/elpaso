"""GitHub issues/PRs connector — fetches issues and merged PRs from repos."""

from dataclasses import dataclass
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta
from github import Github, GithubException


@dataclass
class GitHubIssue:
    repo_name: str
    repo_url: str
    number: int
    title: str
    body: str
    author: str
    last_modified: str
    source_type: str  # "github_issue" or "github_pr"


class GitHubIssuesConnector:
    """Fetches issues and merged PRs from GitHub repos."""

    def __init__(self, token: str, org: str, repo_prefix: str = "", lookback_months: int = 12):
        self.github = Github(token)
        self.org = org
        self.repo_prefix = repo_prefix
        self.since = datetime.now(timezone.utc) - relativedelta(months=lookback_months)

    def _get_repos(self):
        """List repos matching the prefix filter."""
        org = self.github.get_organization(self.org)
        for repo in org.get_repos():
            if self.repo_prefix and not repo.name.startswith(self.repo_prefix):
                continue
            yield repo

    def _build_issue_body(self, issue) -> str:
        """Concatenate issue title + body + comments into a single text."""
        parts = [f"# {issue.title}"]
        if issue.body:
            parts.append(issue.body)

        try:
            for comment in issue.get_comments():
                if comment.body:
                    parts.append(f"**{comment.user.login}**: {comment.body}")
        except GithubException:
            pass

        return "\n\n".join(parts)

    def _build_pr_body(self, pr) -> str:
        """Concatenate PR title + body."""
        parts = [f"# {pr.title}"]
        if pr.body:
            parts.append(pr.body)
        return "\n\n".join(parts)

    def fetch_issues(self) -> list[GitHubIssue]:
        """Fetch issues updated since lookback date from all matching repos."""
        all_issues: list[GitHubIssue] = []

        for repo in self._get_repos():
            try:
                issues = repo.get_issues(state="all", since=self.since, sort="updated")
                for issue in issues:
                    # Skip pull requests (GitHub API returns PRs as issues too)
                    if issue.pull_request is not None:
                        continue

                    body = self._build_issue_body(issue)
                    if not body.strip():
                        continue

                    all_issues.append(GitHubIssue(
                        repo_name=repo.name,
                        repo_url=repo.html_url,
                        number=issue.number,
                        title=issue.title,
                        body=body,
                        author=issue.user.login if issue.user else "unknown",
                        last_modified=issue.updated_at.isoformat() if issue.updated_at else "",
                        source_type="github_issue",
                    ))
            except GithubException:
                continue

        return all_issues

    def fetch_merged_prs(self) -> list[GitHubIssue]:
        """Fetch merged PRs from the last lookback period."""
        all_prs: list[GitHubIssue] = []

        for repo in self._get_repos():
            try:
                pulls = repo.get_pulls(state="closed", sort="updated", direction="desc")
                for pr in pulls:
                    # Stop when we pass the lookback window
                    if pr.updated_at and pr.updated_at < self.since:
                        break

                    # Only merged PRs
                    if not pr.merged:
                        continue

                    body = self._build_pr_body(pr)
                    if not body.strip():
                        continue

                    all_prs.append(GitHubIssue(
                        repo_name=repo.name,
                        repo_url=repo.html_url,
                        number=pr.number,
                        title=pr.title,
                        body=body,
                        author=pr.user.login if pr.user else "unknown",
                        last_modified=pr.updated_at.isoformat() if pr.updated_at else "",
                        source_type="github_pr",
                    ))
            except GithubException:
                continue

        return all_prs
