import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from common import (
    IN_FLIGHT_GRACE,
    html2text,
    prune_incomplete_indices,
    switch_alias,
)
from fakes import FakeIndices, fake_client
from opensearchpy import OpenSearch

SHA_PATTERN = r"[0-9a-f]{40}"
TIMESTAMP_PATTERN = r"\d{4}(?:-\d{2}){5}"

html = """
<html>
<head/>
<body>
<div>This is my body</div>
</body>
</html>
"""

text = """



This is my body


"""


class TestHTML2Text(unittest.TestCase):
    def test1(self) -> None:
        mytext = html2text(html)
        self.assertEqual(text, mytext)


class TestPruneNamingGuard(unittest.TestCase):
    """
    Deletion must only ever reach indices an indexer itself created, since an
    index no alias points at is otherwise indistinguishable from someone's
    hand-made one.
    """

    def test_sha_named_indices_are_ours(self) -> None:
        ours = f"docs-{'a' * 40}"
        es, indices = fake_client(indices=[ours])

        prune_incomplete_indices(es, "docs", SHA_PATTERN, keep="docs-other")

        self.assertEqual(indices.deleted, [ours])

    def test_near_misses_of_the_sha_scheme_survive(self) -> None:
        names = [
            "docs-archive",
            f"docs-{'a' * 39}",
            f"docs-{'a' * 41}",
            f"docs-{'A' * 40}",
            f"docs-{'z' * 40}",
            f"docs-{'a' * 40}-copy",
        ]
        es, indices = fake_client(indices=names)

        prune_incomplete_indices(es, "docs", SHA_PATTERN, keep="docs-other")

        self.assertEqual(indices.deleted, [])

    def test_timestamp_named_indices_are_ours(self) -> None:
        ours = "blog-2026-08-20-08-51-12"
        es, indices = fake_client(indices=[ours])

        prune_incomplete_indices(es, "blog", TIMESTAMP_PATTERN, keep="blog-other")

        self.assertEqual(indices.deleted, [ours])

    def test_near_misses_of_the_timestamp_scheme_survive(self) -> None:
        names = [
            "blog-archive",
            "blog-2026-08-20",
            "blog-2026-08-20-08-51",
            "blog-2026-08-20-08-51-12-13",
            "blog-20260820085112",
        ]
        es, indices = fake_client(indices=names)

        prune_incomplete_indices(es, "blog", TIMESTAMP_PATTERN, keep="blog-other")

        self.assertEqual(indices.deleted, [])

    def test_the_two_index_sets_do_not_reach_each_other(self) -> None:
        es, indices = fake_client(
            indices=[f"docs-{'a' * 40}", "blog-2026-08-20-08-51-12"]
        )

        prune_incomplete_indices(es, "blog", TIMESTAMP_PATTERN, keep="blog-other")

        self.assertEqual(indices.deleted, ["blog-2026-08-20-08-51-12"])


class TestPruneLeavesInFlightIndicesAlone(unittest.TestCase):
    """
    An index carries no alias until the last step of a run, so "unaliased" alone
    cannot distinguish a leftover from an index a concurrent run is filling.
    """

    def setUp(self) -> None:
        self.name = f"docs-{'a' * 40}"

    def _client(self, age: timedelta) -> tuple[OpenSearch, FakeIndices]:
        return fake_client(
            indices=[self.name],
            created={self.name: datetime.now(timezone.utc) - age},
        )

    def test_recently_created_index_survives(self) -> None:
        es, indices = self._client(timedelta(minutes=2))

        prune_incomplete_indices(es, "docs", SHA_PATTERN, keep="docs-other")

        self.assertEqual(indices.deleted, [])

    def test_index_older_than_any_possible_run_is_deleted(self) -> None:
        es, indices = self._client(timedelta(hours=2))

        prune_incomplete_indices(es, "docs", SHA_PATTERN, keep="docs-other")

        self.assertEqual(indices.deleted, [self.name])

    def test_grace_outlives_the_job_deadline(self) -> None:
        # the CronJobs are capped at activeDeadlineSeconds: 600, so nothing
        # older than the grace can still be running
        self.assertGreater(IN_FLIGHT_GRACE, timedelta(seconds=600))


class TestSwitchAliasIsAtomic(unittest.TestCase):
    def test_removes_and_adds_in_one_call(self) -> None:
        es, indices = fake_client(
            indices=["blog-new", "blog-old"], aliases={"blog": ["blog-old"]}
        )
        indices.update_aliases = mock.Mock(wraps=indices.update_aliases)  # type: ignore[method-assign]

        switch_alias(es, "blog", "blog-new")

        indices.update_aliases.assert_called_once()
        actions = indices.update_aliases.call_args.kwargs["body"]["actions"]
        self.assertEqual(
            actions,
            [
                {"remove": {"index": "blog-old", "alias": "blog"}},
                {"add": {"index": "blog-new", "alias": "blog"}},
            ],
        )

    def test_predecessor_is_deleted_only_after_the_alias_moved(self) -> None:
        es, indices = fake_client(
            indices=["blog-new", "blog-old"], aliases={"blog": ["blog-old"]}
        )
        order: list[str] = []
        indices.update_aliases = mock.Mock(  # type: ignore[method-assign]
            side_effect=lambda body: order.append("alias")
        )
        indices.delete = mock.Mock(side_effect=lambda index: order.append("delete"))  # type: ignore[method-assign]

        switch_alias(es, "blog", "blog-new")

        self.assertEqual(order, ["alias", "delete"])


if __name__ == "__main__":
    unittest.main()
