import unittest
from indexer import get_front_matter

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

doc_with_toml_front_matter = """+++
title = "The Giant Swarm App Catalog"
description = "Overview of the Giant Swarm App Catalog, how it works and what to expect."
date = "2019-02-11"
weight = 90
type = "page"
categories = ["basics"]
+++

This is the TOML example's text
"""

doc_without_front_matter = """# Headline 1

The _Giant Swarm App Catalog_ refers to a set of features and concepts that allow
you to browse, install and manage the configurations of apps (such as prometheus)
from a single place; the Control Plane.
"""



class TestFrontMatter(unittest.TestCase):

    def test_get_front_matter_toml(self):
        data, text = get_front_matter(doc_with_toml_front_matter, "tomlpath")
        self.assertEqual(data["title"], "The Giant Swarm App Catalog")
        self.assertEqual(text, "This is the TOML example's text")

    def test_get_front_matter_yaml(self):
        data, text = get_front_matter(doc_with_yaml_front_matter, "yamlpath")
        self.assertEqual(data["title"], "Node Pools")
        self.assertEqual(text, "This is the YAML example's text")
    
    def test_get_front_matter_none(self):
        data, text = get_front_matter(doc_without_front_matter, "nonepath")
        self.assertIs(data, None)


if __name__ == '__main__':
    unittest.main()
