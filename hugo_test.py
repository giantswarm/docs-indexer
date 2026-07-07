import unittest
from hugo import get_front_matter, markdown_to_text

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


if __name__ == '__main__':
    unittest.main()
