"""GitHub docs connector — fetches README and /docs markdown from repos."""

import base64
from dataclasses import dataclass

from github import Github, GithubException


@dataclass
class GitHubDoc:
    repo_name: str
    repo_url: str
    file_path: str
    content: str


class GitHubDocsConnector:
    """Fetches markdown documentation from GitHub repos."""

    def __init__(self, token: str, org: str, repo_prefix: str = ""):
        self.github = Github(token)
        self.org = org
        self.repo_prefix = repo_prefix

    def _get_repos(self):
        """List repos matching the prefix filter."""
        org = self.github.get_organization(self.org)
        for repo in org.get_repos():
            if self.repo_prefix and not repo.name.startswith(self.repo_prefix):
                continue
            yield repo

    def _decode_content(self, content_file) -> str:
        """Decode base64 file content from GitHub API."""
        if content_file.encoding == "base64":
            return base64.b64decode(content_file.content).decode("utf-8", errors="replace")
        return content_file.content or ""

    def _fetch_docs_dir(self, repo) -> list[GitHubDoc]:
        """Fetch markdown files from /docs directory."""
        docs = []
        try:
            contents = repo.get_contents("docs")
            # Flatten — handle nested dirs one level deep
            files = []
            for item in contents:
                if item.type == "dir":
                    try:
                        files.extend(repo.get_contents(item.path))
                    except GithubException:
                        continue
                else:
                    files.append(item)

            for item in files:
                if item.type == "file" and item.name.lower().endswith((".md", ".mdx", ".txt", ".rst")):
                    content = self._decode_content(item)
                    if content.strip():
                        docs.append(GitHubDoc(
                            repo_name=repo.name,
                            repo_url=repo.html_url,
                            file_path=item.path,
                            content=content,
                        ))
        except GithubException:
            pass  # No docs directory
        return docs

    def fetch_docs(self) -> list[GitHubDoc]:
        """Fetch README + /docs from all matching repos."""
        all_docs: list[GitHubDoc] = []

        for repo in self._get_repos():
            # Fetch README
            try:
                readme = repo.get_readme()
                content = self._decode_content(readme)
                if content.strip():
                    all_docs.append(GitHubDoc(
                        repo_name=repo.name,
                        repo_url=repo.html_url,
                        file_path=readme.path,
                        content=content,
                    ))
            except GithubException:
                pass  # No README

            # Fetch /docs directory
            all_docs.extend(self._fetch_docs_dir(repo))

        return all_docs
