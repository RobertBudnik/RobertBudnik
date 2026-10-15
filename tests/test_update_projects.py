import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_projects  # noqa: E402


class FakeResponse:
    def __init__(self, payload, link=None, status=200):
        self._payload = payload
        self.status = status
        self.headers = {"Link": link} if link else {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        import json

        return json.dumps(self._payload).encode("utf-8")


class UpdateProjectsTests(unittest.TestCase):
    def test_filter_repos_keeps_only_public_owner_non_fork_non_archived_non_profile(self):
        repos = [
            {"name": "RobertBudnik", "full_name": "RobertBudnik/RobertBudnik", "private": False, "visibility": "public", "fork": False, "archived": False, "owner": {"login": "RobertBudnik"}},
            {"name": "private", "full_name": "RobertBudnik/private", "private": True, "visibility": "private", "fork": False, "archived": False, "owner": {"login": "RobertBudnik"}},
            {"name": "forked", "full_name": "RobertBudnik/forked", "private": False, "visibility": "public", "fork": True, "archived": False, "owner": {"login": "RobertBudnik"}},
            {"name": "arch", "full_name": "RobertBudnik/arch", "private": False, "visibility": "public", "fork": False, "archived": True, "owner": {"login": "RobertBudnik"}},
            {"name": "other-owner", "full_name": "Else/other-owner", "private": False, "visibility": "public", "fork": False, "archived": False, "owner": {"login": "Else"}},
            {"name": "good", "full_name": "RobertBudnik/good", "private": False, "visibility": "public", "fork": False, "archived": False, "owner": {"login": "RobertBudnik"}, "html_url": "https://github.com/RobertBudnik/good"},
        ]

        selected, stats = update_projects.filter_repos(repos)

        self.assertEqual([r["name"] for r in selected], ["good"])
        self.assertEqual(stats["fetched"], 6)
        self.assertEqual(stats["rejected"], 5)
        self.assertEqual(stats["selected"], 1)

    def test_fetch_public_repos_uses_pagination(self):
        first_url = "https://api.github.com/users/RobertBudnik/repos?type=owner&sort=pushed&per_page=100&page=1"
        second_url = "https://api.github.com/users/RobertBudnik/repos?type=owner&sort=pushed&per_page=100&page=2"
        first = FakeResponse(
            [{"name": "r1"}],
            link=f'<{second_url}>; rel="next", <{second_url}>; rel="last"',
        )
        second = FakeResponse([{"name": "r2"}], link=None)

        with patch("update_projects.USERNAME", "RobertBudnik"):
            with patch("urllib.request.urlopen", side_effect=[first, second]) as mocked:
                repos = update_projects.fetch_public_repos()

        self.assertEqual([r["name"] for r in repos], ["r1", "r2"])
        self.assertEqual(mocked.call_count, 2)

    def test_main_does_not_overwrite_readme_on_api_error(self):
        original = """start\n<!-- PROJECTS:START -->\nOLD\n<!-- PROJECTS:END -->\nend\n"""
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(original, encoding="utf-8")

            with patch("update_projects.README", str(readme)):
                with patch("update_projects.fetch_public_repos", side_effect=RuntimeError("API down")):
                    with self.assertRaises(SystemExit):
                        update_projects.main()

            self.assertEqual(readme.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
