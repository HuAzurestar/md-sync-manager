import unittest

from scripts.update_from_github import is_github_remote


class SkillUpdaterTests(unittest.TestCase):
    def test_accepts_common_github_remote_formats(self):
        self.assertTrue(
            is_github_remote("https://github.com/HuAzurestar/md-sync-manager.git")
        )
        self.assertTrue(
            is_github_remote("git@github.com:HuAzurestar/md-sync-manager.git")
        )
        self.assertTrue(
            is_github_remote("ssh://git@github.com/HuAzurestar/md-sync-manager.git")
        )

    def test_rejects_non_github_and_lookalike_remotes(self):
        self.assertFalse(
            is_github_remote("https://gitee.com/HuAzurestar/md-sync-manager.git")
        )
        self.assertFalse(is_github_remote("https://github.com.example.test/repo.git"))


if __name__ == "__main__":
    unittest.main()
