import unittest
from datetime import datetime
from unittest import mock

import blog
from blog import full_index_name, parse_date
from fakes import fake_client


class TestFullIndexName(unittest.TestCase):
    def test_name_carries_a_timestamp(self) -> None:
        dt = datetime(2026, 8, 20, 8, 51, 12)

        self.assertEqual(full_index_name(dt), "blog-2026-08-20-08-51-12")

    def test_name_matches_the_pattern_pruning_is_scoped_to(self) -> None:
        # the two must agree, or pruning silently stops collecting leftovers
        import re

        name = full_index_name(datetime(2026, 8, 20, 8, 51, 12))
        pattern = rf"{blog.INDEX_NAME_PREFIX}-{blog.INDEX_SUFFIX_PATTERN}"

        self.assertIsNotNone(re.fullmatch(pattern, name))


class TestParseDate(unittest.TestCase):
    def test_fine_and_coarse_formats(self) -> None:
        self.assertEqual(
            parse_date("2026-08-20T08:51:12.123Z").replace(tzinfo=None),
            datetime(2026, 8, 20, 8, 51, 12, 123000),
        )
        self.assertEqual(
            parse_date("2026-08-20T08:51:12Z").replace(tzinfo=None),
            datetime(2026, 8, 20, 8, 51, 12),
        )


class TestPruneIncompleteIndices(unittest.TestCase):
    def setUp(self) -> None:
        self.new = "blog-2026-09-04-08-51-19"
        self.live = "blog-2026-09-03-08-51-01"
        self.orphan = "blog-2026-08-20-08-51-12"

    def test_unaliased_index_is_deleted(self) -> None:
        es, indices = fake_client(
            indices=[self.live, self.orphan], aliases={"blog": [self.live]}
        )

        blog.prune_incomplete_indices(es, keep=self.new)

        self.assertEqual(indices.deleted, [self.orphan])

    def test_live_and_kept_indices_survive(self) -> None:
        es, indices = fake_client(
            indices=[self.new, self.live], aliases={"blog": [self.live]}
        )

        blog.prune_incomplete_indices(es, keep=self.new)

        self.assertEqual(indices.deleted, [])

    def test_other_index_sets_survive(self) -> None:
        es, indices = fake_client(indices=[f"docs-{'a' * 40}"])

        blog.prune_incomplete_indices(es, keep=self.new)

        self.assertEqual(indices.deleted, [])


class TestSetIndexAlias(unittest.TestCase):
    def test_alias_moves_and_predecessor_is_deleted(self) -> None:
        es, indices = fake_client(
            indices=["blog-2026-09-04-08-51-19", "blog-2026-09-03-08-51-01"],
            aliases={"blog": ["blog-2026-09-03-08-51-01"]},
        )

        blog.set_index_alias(es, "blog-2026-09-04-08-51-19")

        self.assertEqual(indices.aliases["blog"], ["blog-2026-09-04-08-51-19"])
        self.assertEqual(indices.deleted, ["blog-2026-09-03-08-51-01"])

    def test_first_run_adds_the_alias(self) -> None:
        es, indices = fake_client(indices=["blog-2026-09-04-08-51-19"])

        blog.set_index_alias(es, "blog-2026-09-04-08-51-19")

        self.assertEqual(indices.aliases["blog"], ["blog-2026-09-04-08-51-19"])
        self.assertEqual(indices.deleted, [])


@mock.patch.object(blog, "HUBSPOT_ACCESS_TOKEN", "token")
@mock.patch.object(blog, "OPENSEARCH_ENDPOINT", "http://opensearch:9200")
@mock.patch.object(blog, "sleep", lambda _seconds: None)
class TestRun(unittest.TestCase):
    """
    run() end to end against the fake client, which is where the leftover
    behaviour actually lives.
    """

    def setUp(self) -> None:
        self.orphan = "blog-2026-08-20-08-51-12"
        self.live = "blog-2026-09-03-08-51-01"
        self.es, self.indices = fake_client(
            indices=[self.live, self.orphan], aliases={"blog": [self.live]}
        )
        patcher = mock.patch.object(blog, "OpenSearch", return_value=self.es)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, id: str) -> dict:
        return {
            "id": id,
            "state": "PUBLISHED",
            "url": f"https://www.giantswarm.io/blog/{id}",
            "created": "2026-09-04T08:00:00Z",
            "htmlTitle": f"<h1>Post {id}</h1>",
            "postBody": "<p>Body</p>",
            "featuredImage": "https://example.com/i.png",
        }

    def test_successful_run_prunes_switches_and_retires(self) -> None:
        with mock.patch.object(
            blog, "get_blog_posts", return_value=iter([self._post("1")])
        ):
            blog.run()

        # the orphan is collected, the new index takes the alias, the previous
        # one is retired, and nothing unaliased is left behind
        self.assertIn(self.orphan, self.indices.deleted)
        self.assertIn(self.live, self.indices.deleted)
        aliased = self.indices.aliases["blog"]
        self.assertEqual(len(aliased), 1)
        self.assertEqual(set(self.indices.indices), set(aliased))

    def test_run_without_posts_leaves_no_empty_index(self) -> None:
        with mock.patch.object(blog, "get_blog_posts", return_value=iter([])):
            blog.run()

        # the previous index stays in service and the empty one is not kept
        self.assertEqual(self.indices.aliases["blog"], [self.live])
        self.assertEqual(set(self.indices.indices), {self.live})

    def _interrupt(self) -> str:
        """Run and blow up mid-index; returns the leftover index name."""

        class Boom(Exception):
            pass

        with mock.patch.object(blog, "get_blog_posts", side_effect=Boom):
            with self.assertRaises(Boom):
                blog.run()

        # the alias never moved, so search is unaffected
        self.assertEqual(self.indices.aliases["blog"], [self.live])
        leftovers = [
            i for i in self.indices.indices if i not in (self.live, self.orphan)
        ]
        self.assertEqual(len(leftovers), 1)
        return leftovers[0]

    def test_interrupted_run_leaves_a_leftover_the_next_run_collects(self) -> None:
        names = iter(["blog-2026-09-04-08-51-19", "blog-2026-09-05-08-51-22"])
        with mock.patch.object(blog, "full_index_name", lambda _dt: next(names)):
            leftover = self._interrupt()

            with mock.patch.object(
                blog, "get_blog_posts", return_value=iter([self._post("1")])
            ):
                blog.run()

        self.assertIn(leftover, self.indices.deleted)
        self.assertEqual(len(self.indices.aliases["blog"]), 1)
        self.assertEqual(set(self.indices.indices), set(self.indices.aliases["blog"]))

    def test_leftover_under_the_same_name_is_replaced(self) -> None:
        # two runs in the same second produce the same index name, which pruning
        # spares because it is the name the second run is about to use
        with mock.patch.object(
            blog, "full_index_name", lambda _dt: "blog-2026-09-04-08-51-19"
        ):
            leftover = self._interrupt()

            with mock.patch.object(
                blog, "get_blog_posts", return_value=iter([self._post("1")])
            ):
                blog.run()

        self.assertIn(leftover, self.indices.deleted)
        self.assertEqual(self.indices.aliases["blog"], ["blog-2026-09-04-08-51-19"])
        self.assertEqual(set(self.indices.indices), {"blog-2026-09-04-08-51-19"})


if __name__ == "__main__":
    unittest.main()
