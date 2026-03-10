"""Tests for GitHub connectors with mocked API responses."""

from unittest.mock import MagicMock, patch, PropertyMock
import base64
from datetime import datetime, timezone

from github import GithubException

from connectors.github_docs import GitHubDocsConnector, GitHubDoc
from connectors.github_issues import GitHubIssuesConnector, GitHubIssue


def _make_mock_content(path, content_str, encoding="base64"):
    """Create a mock GitHub content file."""
    mock = MagicMock()
    mock.path = path
    mock.name = path.split("/")[-1]
    mock.type = "file"
    mock.encoding = encoding
    mock.content = base64.b64encode(content_str.encode()).decode() if encoding == "base64" else content_str
    return mock


def _make_mock_repo(name="mes-test-service", html_url="https://github.com/org/mes-test-service"):
    """Create a mock GitHub repo."""
    repo = MagicMock()
    repo.name = name
    repo.html_url = html_url
    return repo


class TestGitHubDocsConnector:
    def _make_connector(self):
        connector = GitHubDocsConnector.__new__(GitHubDocsConnector)
        connector.github = MagicMock()
        connector.org = "test-org"
        connector.repo_prefix = "mes-"
        return connector

    def test_decode_base64_content(self):
        connector = self._make_connector()
        mock_file = _make_mock_content("README.md", "Hello world")
        result = connector._decode_content(mock_file)
        assert result == "Hello world"

    def test_filters_by_prefix(self):
        connector = self._make_connector()
        matching_repo = _make_mock_repo("mes-service")
        non_matching_repo = _make_mock_repo("other-service")
        org_mock = MagicMock()
        org_mock.get_repos.return_value = [matching_repo, non_matching_repo]
        connector.github.get_organization.return_value = org_mock

        repos = list(connector._get_repos())
        assert len(repos) == 1
        assert repos[0].name == "mes-service"

    def test_fetch_docs_gets_readme(self):
        connector = self._make_connector()
        repo = _make_mock_repo()
        readme = _make_mock_content("README.md", "# My Service\nSome docs here.")
        repo.get_readme.return_value = readme
        repo.get_contents.side_effect = GithubException(404, "not found", None)

        org_mock = MagicMock()
        org_mock.get_repos.return_value = [repo]
        connector.github.get_organization.return_value = org_mock

        docs = connector.fetch_docs()
        assert len(docs) == 1
        assert docs[0].file_path == "README.md"
        assert "My Service" in docs[0].content

    def test_fetch_docs_gets_docs_dir(self):
        connector = self._make_connector()
        repo = _make_mock_repo()
        repo.get_readme.side_effect = GithubException(404, "not found", None)

        doc_file = _make_mock_content("docs/setup.md", "# Setup\nInstall steps.")
        repo.get_contents.return_value = [doc_file]

        org_mock = MagicMock()
        org_mock.get_repos.return_value = [repo]
        connector.github.get_organization.return_value = org_mock

        docs = connector.fetch_docs()
        assert len(docs) == 1
        assert docs[0].file_path == "docs/setup.md"

    def test_skips_empty_content(self):
        connector = self._make_connector()
        repo = _make_mock_repo()
        readme = _make_mock_content("README.md", "   ")
        repo.get_readme.return_value = readme
        repo.get_contents.side_effect = GithubException(404, "not found", None)

        org_mock = MagicMock()
        org_mock.get_repos.return_value = [repo]
        connector.github.get_organization.return_value = org_mock

        docs = connector.fetch_docs()
        assert len(docs) == 0


class TestGitHubIssuesConnector:
    def _make_connector(self):
        connector = GitHubIssuesConnector.__new__(GitHubIssuesConnector)
        connector.github = MagicMock()
        connector.org = "test-org"
        connector.repo_prefix = "mes-"
        connector.since = datetime(2025, 1, 1, tzinfo=timezone.utc)
        return connector

    def _make_mock_issue(self, number=1, title="Bug fix", body="Fixed the thing", is_pr=False):
        issue = MagicMock()
        issue.number = number
        issue.title = title
        issue.body = body
        issue.pull_request = MagicMock() if is_pr else None
        issue.user = MagicMock()
        issue.user.login = "testuser"
        issue.updated_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
        issue.get_comments.return_value = []
        return issue

    def _make_mock_pr(self, number=10, title="Add feature", body="New feature details", merged=True):
        pr = MagicMock()
        pr.number = number
        pr.title = title
        pr.body = body
        pr.merged = merged
        pr.user = MagicMock()
        pr.user.login = "testuser"
        pr.updated_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
        return pr

    def test_fetch_issues_excludes_prs(self):
        connector = self._make_connector()
        repo = _make_mock_repo()
        real_issue = self._make_mock_issue(number=1, is_pr=False)
        pr_as_issue = self._make_mock_issue(number=2, is_pr=True)
        repo.get_issues.return_value = [real_issue, pr_as_issue]

        org_mock = MagicMock()
        org_mock.get_repos.return_value = [repo]
        connector.github.get_organization.return_value = org_mock

        issues = connector.fetch_issues()
        assert len(issues) == 1
        assert issues[0].number == 1
        assert issues[0].source_type == "github_issue"

    def test_fetch_issues_includes_comments(self):
        connector = self._make_connector()
        repo = _make_mock_repo()
        issue = self._make_mock_issue()
        comment = MagicMock()
        comment.body = "This is a comment"
        comment.user = MagicMock()
        comment.user.login = "commenter"
        issue.get_comments.return_value = [comment]
        repo.get_issues.return_value = [issue]

        org_mock = MagicMock()
        org_mock.get_repos.return_value = [repo]
        connector.github.get_organization.return_value = org_mock

        issues = connector.fetch_issues()
        assert "This is a comment" in issues[0].body

    def test_fetch_merged_prs_only(self):
        connector = self._make_connector()
        repo = _make_mock_repo()
        merged_pr = self._make_mock_pr(number=10, merged=True)
        unmerged_pr = self._make_mock_pr(number=11, merged=False)
        # unmerged still within lookback so won't trigger break
        unmerged_pr.updated_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.get_pulls.return_value = [merged_pr, unmerged_pr]

        org_mock = MagicMock()
        org_mock.get_repos.return_value = [repo]
        connector.github.get_organization.return_value = org_mock

        prs = connector.fetch_merged_prs()
        assert len(prs) == 1
        assert prs[0].number == 10
        assert prs[0].source_type == "github_pr"

    def test_pr_stops_at_lookback_boundary(self):
        connector = self._make_connector()
        repo = _make_mock_repo()
        old_pr = self._make_mock_pr(number=5, merged=True)
        old_pr.updated_at = datetime(2024, 6, 1, tzinfo=timezone.utc)  # Before lookback
        repo.get_pulls.return_value = [old_pr]

        org_mock = MagicMock()
        org_mock.get_repos.return_value = [repo]
        connector.github.get_organization.return_value = org_mock

        prs = connector.fetch_merged_prs()
        assert len(prs) == 0
