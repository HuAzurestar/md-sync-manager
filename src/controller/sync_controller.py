"""Compatibility controller that assembles the transport-neutral sync service."""

from src.core.remote import RemoteAccessPolicy
from src.providers.gitee import GiteeClient, GiteeIssueProvider, GiteePullProvider
from src.providers.github import GitHubClient, GitHubIssueProvider, GitHubPullProvider
from src.providers.youtrack import (
    YouTrackArticleProvider,
    YouTrackClient,
    YouTrackIssueProvider,
)
from src.service.sync_service import SyncService


class SyncController(SyncService):
    def __init__(self, config: dict):
        super().__init__(access_policy=RemoteAccessPolicy.from_config(config))
        settings = config.get("providers", {})
        github = settings.get("github", {})
        if github.get("enabled") and github.get("token"):
            client = GitHubClient(github)
            self.register(GitHubIssueProvider(client))
            self.register(GitHubPullProvider(client))
        gitee = settings.get("gitee", {})
        if gitee.get("enabled") and gitee.get("token"):
            client = GiteeClient(gitee)
            self.register(GiteeIssueProvider(client))
            self.register(GiteePullProvider(client))
        youtrack = settings.get("youtrack", {})
        if youtrack.get("enabled") and youtrack.get("token"):
            client = YouTrackClient(youtrack)
            self.register(YouTrackIssueProvider(client))
            self.register(YouTrackArticleProvider(client))
