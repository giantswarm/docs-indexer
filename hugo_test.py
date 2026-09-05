import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import hugo
from fakes import fake_client
from hugo import (
    collect_properties_text,
    get_front_matter,
    get_last_modified,
    get_pages,
    markdown_to_text,
)

doc_with_yaml_front_matter = """---
title: Node Pools
description: A general description of node pools as a concept, it's benefits, and some details you should be aware of.
date: 2019-12-19
weight: 130
type: page
categories: ["basics"]
---

This is the YAML example's text
"""

doc_without_front_matter = """# Headline 1

The _Giant Swarm App Catalog_ refers to a set of features and concepts that allow
you to browse, install and manage the configurations of apps (such as prometheus)
from a single place; the Control Plane.
"""


class TestFrontMatter(unittest.TestCase):
    def test_get_front_matter_yaml(self) -> None:
        data, text = get_front_matter(doc_with_yaml_front_matter, "yamlpath")
        assert data is not None
        self.assertEqual(data["title"], "Node Pools")
        self.assertEqual(text, "This is the YAML example's text")

    def test_get_front_matter_none(self) -> None:
        data, text = get_front_matter(doc_without_front_matter, "nonepath")
        self.assertIs(data, None)


class TestMarkdownToText(unittest.TestCase):
    def test_fenced_code_language_indicator_stripped(self) -> None:
        md = "Intro text.\n\n```nohighlight\nkubectl get pods\n```\n\nAfter text."
        text = markdown_to_text(md)
        self.assertNotIn("nohighlight", text)
        self.assertIn("kubectl get pods", text)

    def test_table_separators_stripped(self) -> None:
        md = (
            "Intro.\n\n"
            "| Name | Role |\n"
            "| ---- | ---- |\n"
            "| Alice | Admin |\n"
            "| Bob | User |\n\n"
            "Outro."
        )
        text = markdown_to_text(md)
        self.assertNotIn("|", text)
        self.assertNotIn("---", text)
        for cell in ("Name", "Role", "Alice", "Admin", "Bob", "User"):
            self.assertIn(cell, text)

    def test_heading_anchor_stripped(self) -> None:
        md = (
            "## Resource types {#types}\n\nSome content.\n\n### Flags {#flags}\n\nMore."
        )
        text = markdown_to_text(md)
        self.assertNotIn("{#types}", text)
        self.assertNotIn("{#flags}", text)
        self.assertIn("Resource types", text)
        self.assertIn("Flags", text)

    def test_shortcodes_stripped(self) -> None:
        md = (
            "Install manually.\n\n"
            "{{< tabs >}}\n"
            '{{< tab name="Krew" >}}\n'
            "Pull the image.\n"
            "{{< /tab >}}\n"
            "{{< /tabs >}}\n\n"
            "{{% steps %}}\n"
            "Do the thing.\n"
            "{{% /steps %}}\n"
        )
        text = markdown_to_text(md)
        self.assertNotIn("{{", text)
        self.assertNotIn("}}", text)
        self.assertNotIn("tabs", text)
        self.assertNotIn("steps", text)
        self.assertIn("Pull the image.", text)
        self.assertIn("Do the thing.", text)


class TestGetPages(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, *parts: str) -> str:
        """Create a file (and its parent dirs) at root/parts, with dummy content."""
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("content")
        return path

    def test_uris_and_index_handling(self) -> None:
        self._write("index.md")
        self._write("basics", "_index.md")
        self._write("basics", "nodepools.md")

        pages = get_pages(self.root)
        by_uri = {p["uri"]: p for p in pages}

        # top-level index.md maps to the root URI
        self.assertIn("/", by_uri)
        # _index.md yields the directory URI, without a file segment
        self.assertIn("/basics/", by_uri)
        # a regular page appends its filename (without .md) as the last segment
        self.assertIn("/basics/nodepools/", by_uri)

        nodepools = by_uri["/basics/nodepools/"]
        self.assertEqual(nodepools["path"], ["basics", "nodepools"])
        self.assertEqual(
            nodepools["file_path"],
            os.path.join(self.root, "basics", "nodepools.md"),
        )

    def test_uri_is_lowercased(self) -> None:
        self._write("Advanced", "MyPage.md")

        pages = get_pages(self.root)
        by_uri = {p["uri"]: p for p in pages}

        self.assertIn("/advanced/mypage/", by_uri)
        # the URI is lowercased, but the path segments keep their original case
        self.assertEqual(by_uri["/advanced/mypage/"]["path"], ["Advanced", "MyPage"])

    def test_non_markdown_and_pruned_dirs_ignored(self) -> None:
        self._write("notes.txt")
        self._write("img", "diagram.md")
        self._write(".git", "config.md")
        self._write("real.md")

        pages = get_pages(self.root)
        uris = {p["uri"] for p in pages}

        self.assertEqual(uris, {"/real/"})


class TestCollectPropertiesText(unittest.TestCase):
    def test_empty_schema(self) -> None:
        self.assertEqual(collect_properties_text({}), [])

    def test_description_only(self) -> None:
        self.assertEqual(collect_properties_text({"description": "top"}), ["top"])

    def test_nested_properties_recursion(self) -> None:
        schema = {
            "description": "top",
            "properties": {
                "spec": {
                    "description": "spec desc",
                    "properties": {
                        "replicas": {"description": "number of replicas"},
                        "name": {},  # no description, no children
                    },
                },
                "status": {"description": "status desc"},
            },
        }
        self.assertEqual(
            collect_properties_text(schema),
            [
                "top",
                "spec",
                "spec desc",
                "replicas",
                "number of replicas",
                "name",
                "status",
                "status desc",
            ],
        )


class TestGetLastModified(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.mkdtemp()
        self._git("init", "-q", "-b", "main")
        self._git("config", "user.email", "indexer@example.com")
        self._git("config", "user.name", "Indexer")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", self.root, *args],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _commit(self, date: str, *paths: str) -> None:
        """Write and commit the given paths, with date as the commit date."""
        for rel in paths:
            path = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as f:
                f.write("content\n")
        self._git("add", "-A")
        subprocess.run(
            ["git", "-C", self.root, "commit", "-q", "-m", f"commit {date}"],
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_DATE": date,
                "GIT_COMMITTER_DATE": date,
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def _expected(date: str) -> datetime:
        """The naive local datetime get_last_modified reports for a commit date."""
        return datetime.fromtimestamp(datetime.fromisoformat(date).timestamp())

    def test_last_commit_per_file(self) -> None:
        self._commit("2026-01-01T00:00:00+00:00", "a.md", "deep/nested/b.md")
        self._commit("2026-02-02T00:00:00+00:00", "deep/nested/b.md")

        last_modified = get_last_modified(self.root)

        self.assertEqual(
            last_modified["a.md"], self._expected("2026-01-01T00:00:00+00:00")
        )
        # the later commit wins for the file it touched, the earlier one does not
        self.assertEqual(
            last_modified["deep/nested/b.md"],
            self._expected("2026-02-02T00:00:00+00:00"),
        )

    def test_paths_are_relative_to_the_repo_root(self) -> None:
        self._commit("2026-01-01T00:00:00+00:00", "src/content/page.md")

        self.assertIn("src/content/page.md", get_last_modified(self.root))

    def test_non_markdown_files_are_ignored(self) -> None:
        self._commit("2026-01-01T00:00:00+00:00", "a.md", "notes.txt", "img/x.png")

        last_modified = get_last_modified(self.root)

        self.assertEqual(list(last_modified), ["a.md"])

    def test_merge_commit_does_not_claim_the_files(self) -> None:
        self._commit("2026-01-01T00:00:00+00:00", "base.md")
        self._git("checkout", "-q", "-b", "side")
        self._commit("2026-02-02T00:00:00+00:00", "side.md")
        self._git("checkout", "-q", "main")
        self._commit("2026-03-03T00:00:00+00:00", "main.md")
        self._git(
            "-c",
            "user.email=indexer@example.com",
            "-c",
            "user.name=Indexer",
            "merge",
            "-q",
            "--no-ff",
            "-m",
            "merge side",
            "side",
        )

        last_modified = get_last_modified(self.root)

        # the merge commit's own date must not overwrite the real edit dates
        self.assertEqual(last_modified["side.md"].month, 2)
        self.assertEqual(last_modified["main.md"].month, 3)
        self.assertEqual(last_modified["base.md"].month, 1)


@mock.patch.object(hugo, "INDEX_NAME", "docs")
class TestCheckIndex(unittest.TestCase):
    def test_missing_index_proceeds(self) -> None:
        es, indices = fake_client()

        hugo.check_index(es, "docs-abc")

        self.assertEqual(indices.deleted, [])

    def test_aliased_index_exits(self) -> None:
        es, indices = fake_client(indices=["docs-abc"], aliases={"docs": ["docs-abc"]})

        with self.assertRaises(SystemExit) as cm:
            hugo.check_index(es, "docs-abc")

        # a complete index is nothing to do, not a failure
        self.assertIn(cm.exception.code, (None, 0))
        self.assertEqual(indices.deleted, [])

    def test_unaliased_index_is_deleted(self) -> None:
        # what a run killed before the alias switch leaves behind
        es, indices = fake_client(
            indices=["docs-abc", "docs-old"], aliases={"docs": ["docs-old"]}
        )

        hugo.check_index(es, "docs-abc")

        self.assertEqual(indices.deleted, ["docs-abc"])
        self.assertNotIn("docs-abc", indices.indices)

    def test_in_flight_index_is_left_alone(self) -> None:
        # a concurrent run is probably still filling it; deleting it would make
        # that run recreate it by auto-create with dynamic mappings
        es, indices = fake_client(
            indices=["docs-abc"],
            created={"docs-abc": datetime.now(timezone.utc) - timedelta(minutes=2)},
        )

        with self.assertRaises(SystemExit) as cm:
            hugo.check_index(es, "docs-abc")

        self.assertIn(cm.exception.code, (None, 0))
        self.assertEqual(indices.deleted, [])

    def test_unaliased_index_without_any_alias_is_deleted(self) -> None:
        es, indices = fake_client(indices=["docs-abc"])

        hugo.check_index(es, "docs-abc")

        self.assertEqual(indices.deleted, ["docs-abc"])


@mock.patch.object(hugo, "INDEX_NAME", "docs")
class TestSwitchAlias(unittest.TestCase):
    def test_first_run_adds_alias(self) -> None:
        es, indices = fake_client(indices=["docs-abc"])

        hugo.switch_alias(es, "docs-abc")

        self.assertEqual(indices.aliases["docs"], ["docs-abc"])
        self.assertEqual(indices.deleted, [])

    def test_previous_index_is_replaced_and_deleted(self) -> None:
        es, indices = fake_client(
            indices=["docs-abc", "docs-old"], aliases={"docs": ["docs-old"]}
        )

        hugo.switch_alias(es, "docs-abc")

        self.assertEqual(indices.aliases["docs"], ["docs-abc"])
        self.assertEqual(indices.deleted, ["docs-old"])

    def test_multiple_previous_indices_are_replaced_and_deleted(self) -> None:
        es, indices = fake_client(
            indices=["docs-abc", "docs-old", "docs-older"],
            aliases={"docs": ["docs-old", "docs-older"]},
        )

        hugo.switch_alias(es, "docs-abc")

        self.assertEqual(indices.aliases["docs"], ["docs-abc"])
        self.assertEqual(sorted(indices.deleted), ["docs-old", "docs-older"])

    def test_new_index_is_never_deleted(self) -> None:
        es, indices = fake_client(indices=["docs-abc"], aliases={"docs": ["docs-abc"]})

        hugo.switch_alias(es, "docs-abc")

        self.assertEqual(indices.aliases["docs"], ["docs-abc"])
        self.assertEqual(indices.deleted, [])

    def test_undeletable_previous_index_does_not_fail_the_run(self) -> None:
        es, indices = fake_client(
            indices=["docs-abc", "docs-old"], aliases={"docs": ["docs-old"]}
        )
        indices.delete = mock.Mock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        hugo.switch_alias(es, "docs-abc")

        self.assertEqual(indices.aliases["docs"], ["docs-abc"])


@mock.patch.object(hugo, "INDEX_NAME", "docs")
class TestPruneIncompleteIndices(unittest.TestCase):
    def setUp(self) -> None:
        self.new = f"docs-{'a' * 40}"
        self.live = f"docs-{'b' * 40}"
        self.orphan = f"docs-{'c' * 40}"

    def test_unaliased_indices_are_deleted(self) -> None:
        es, indices = fake_client(
            indices=[self.new, self.live, self.orphan],
            aliases={"docs": [self.live]},
        )

        hugo.prune_incomplete_indices(es, keep=self.new)

        self.assertEqual(indices.deleted, [self.orphan])

    def test_kept_index_survives(self) -> None:
        # the index for the commit being handled is the caller's business
        es, indices = fake_client(indices=[self.new])

        hugo.prune_incomplete_indices(es, keep=self.new)

        self.assertEqual(indices.deleted, [])

    def test_aliased_index_survives(self) -> None:
        es, indices = fake_client(indices=[self.live], aliases={"docs": [self.live]})

        hugo.prune_incomplete_indices(es, keep=self.new)

        self.assertEqual(indices.deleted, [])

    def test_indices_outside_our_naming_scheme_survive(self) -> None:
        es, indices = fake_client(indices=["docs-archive", "docs-2026-08-28"])

        hugo.prune_incomplete_indices(es, keep=self.new)

        self.assertEqual(indices.deleted, [])

    def test_other_index_sets_survive(self) -> None:
        es, indices = fake_client(indices=[f"handbook-{'c' * 40}"])

        hugo.prune_incomplete_indices(es, keep=self.new)

        self.assertEqual(indices.deleted, [])

    def test_undeletable_index_does_not_fail_the_run(self) -> None:
        es, indices = fake_client(indices=[self.orphan])
        indices.delete = mock.Mock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]

        hugo.prune_incomplete_indices(es, keep=self.new)


class TestIndexCompletenessRoundTrip(unittest.TestCase):
    @mock.patch.object(hugo, "INDEX_NAME", "docs")
    def test_index_counts_as_complete_only_after_the_alias_switch(self) -> None:
        es, indices = fake_client(indices=["docs-abc"])

        self.assertFalse(hugo.index_is_complete(es, "docs-abc"))

        hugo.switch_alias(es, "docs-abc")

        self.assertTrue(hugo.index_is_complete(es, "docs-abc"))


if __name__ == "__main__":
    unittest.main()
