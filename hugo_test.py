import os
import shutil
import tempfile
import unittest
from hugo import get_front_matter, markdown_to_text, get_pages, collect_properties_text

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

    def test_get_front_matter_yaml(self):
        data, text = get_front_matter(doc_with_yaml_front_matter, "yamlpath")
        self.assertEqual(data["title"], "Node Pools")
        self.assertEqual(text, "This is the YAML example's text")
    
    def test_get_front_matter_none(self):
        data, text = get_front_matter(doc_without_front_matter, "nonepath")
        self.assertIs(data, None)


class TestMarkdownToText(unittest.TestCase):

    def test_fenced_code_language_indicator_stripped(self):
        md = "Intro text.\n\n```nohighlight\nkubectl get pods\n```\n\nAfter text."
        text = markdown_to_text(md)
        self.assertNotIn("nohighlight", text)
        self.assertIn("kubectl get pods", text)

    def test_table_separators_stripped(self):
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

    def test_heading_anchor_stripped(self):
        md = "## Resource types {#types}\n\nSome content.\n\n### Flags {#flags}\n\nMore."
        text = markdown_to_text(md)
        self.assertNotIn("{#types}", text)
        self.assertNotIn("{#flags}", text)
        self.assertIn("Resource types", text)
        self.assertIn("Flags", text)

    def test_shortcodes_stripped(self):
        md = (
            "Install manually.\n\n"
            "{{< tabs >}}\n"
            "{{< tab name=\"Krew\" >}}\n"
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

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, *parts):
        """Create a file (and its parent dirs) at root/parts, with dummy content."""
        path = os.path.join(self.root, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("content")
        return path

    def test_uris_and_index_handling(self):
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

    def test_uri_is_lowercased(self):
        self._write("Advanced", "MyPage.md")

        pages = get_pages(self.root)
        by_uri = {p["uri"]: p for p in pages}

        self.assertIn("/advanced/mypage/", by_uri)
        # the URI is lowercased, but the path segments keep their original case
        self.assertEqual(by_uri["/advanced/mypage/"]["path"], ["Advanced", "MyPage"])

    def test_non_markdown_and_pruned_dirs_ignored(self):
        self._write("notes.txt")
        self._write("img", "diagram.md")
        self._write(".git", "config.md")
        self._write("real.md")

        pages = get_pages(self.root)
        uris = {p["uri"] for p in pages}

        self.assertEqual(uris, {"/real/"})


class TestCollectPropertiesText(unittest.TestCase):

    def test_empty_schema(self):
        self.assertEqual(collect_properties_text({}), [])

    def test_description_only(self):
        self.assertEqual(collect_properties_text({"description": "top"}), ["top"])

    def test_nested_properties_recursion(self):
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


if __name__ == '__main__':
    unittest.main()
